"""
haunt_ops/management/commands/run_selenium_groups_query.py
Command to load or update groups from ivolunteers Groups section of
the Database page using Selenium.
It supports dry-run mode to simulate updates without saving to the database.
"""

from __future__ import annotations
import logging
import os

from dataclasses import dataclass
from django.core.management.base import BaseCommand, CommandError
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from haunt_ops.models import Groups
from haunt_ops.utils.iv_core import (
    DriverConfig,
    build_driver,
    login_iv,
    click_top_tab,
    click_inner_tabpanel_tab,
    dump_all_frames,
    debug_dump_page,
    ADMIN_IFRAME_ID,
    scrape_groups_from_filter_dropdown,
    scrape_database_group_list,
    click_database_group_by_name,
    wait_for_overlay_to_clear,
)


logger = logging.getLogger("haunt_ops")


@dataclass
class CmdConfig:
    iv_url: str
    iv_admin_email: str
    iv_password: str
    headless: bool
    dump_frames: bool
    timeout: int
    browser: str
    log_pw_hash: bool


class Command(BaseCommand):
    help = "Login to iVolunteer admin, click Groups tab, scrape groups (Firefox default)."

    def add_arguments(self, parser):
        parser.add_argument("--iv-url", dest="iv_url", default=os.environ.get("IVOLUNTEER_URL", ""))
        parser.add_argument("--email", dest="iv_admin_email", default=os.environ.get("IVOLUNTEER_ADMIN_EMAIL", ""))
        parser.add_argument("--password", dest="iv_password", default=os.environ.get("IVOLUNTEER_PASSWORD", ""))
        parser.add_argument("--headless", action="store_true", default=False)
        parser.add_argument("--dump-frames", action="store_true", default=False)
        parser.add_argument("--timeout", type=int, default=60)
        parser.add_argument("--browser", choices=["firefox","chrome"], default=os.environ.get("BROWSER","firefox"))
        parser.add_argument("--log-pw-hash", action="store_true", default=False)
        parser.add_argument("--dry-run", action="store_true", help="Simulate updates without saving to database.")


    def handle(self, *args, **options):
        cfg = CmdConfig(
            iv_url=options["iv_url"],
            iv_admin_email=options["iv_admin_email"],
            iv_password=options["iv_password"],
            headless=options["headless"],
            dump_frames=options["dump_frames"],
            timeout=max(15, int(options["timeout"])),
            browser=options["browser"],
            log_pw_hash=options["log_pw_hash"],
        )
        dry_run = options["dry_run"]

        if not (cfg.iv_url and cfg.iv_admin_email and cfg.iv_password):
            missing = [k for k, v in [
                ("IVOLUNTEER_URL", cfg.iv_url),
                ("IVOLUNTEER_ADMIN_EMAIL", cfg.iv_admin_email),
                ("IVOLUNTEER_PASSWORD", cfg.iv_password),
            ] if not v]
            raise CommandError(f"❌ Missing required inputs: {', '.join(missing)}. Provide flags or set env vars.")

        logger.info("▶ Starting with email=%s pw_len=%s headless=%s browser=%s",
                    cfg.iv_admin_email, len(cfg.iv_password or ''), cfg.headless, cfg.browser)

        driver = None
        try:
            driver = build_driver(DriverConfig(
                browser=cfg.browser,
                headless=cfg.headless,
            ))

            ok = login_iv(
                driver,
                cfg.iv_url,
                cfg.iv_admin_email,
                cfg.iv_password,
                timeout=cfg.timeout,
                log_pw_hash=cfg.log_pw_hash,
            )
            if not ok:
                raise CommandError("Login failed — see logs and /tmp/iv_login_* dumps.")

            if cfg.dump_frames:
                dump_all_frames(driver, prefix="iv_after_login")

            self.stdout.write(self.style.SUCCESS("✅ Login completed successfully."))

            logger.info("Operating in top document; ignoring hidden %s iframe.", ADMIN_IFRAME_ID)

            if not click_top_tab(driver, "Database", timeout=cfg.timeout, logger=logger):
                dump_all_frames(driver, prefix="iv_database_click_fail_topdoc")
                raise CommandError("Could not activate the 'Database' tab from the landing page menu.")

            self.stdout.write(self.style.SUCCESS("✅ Database tab activated successfully."))

            self.stdout.write(self.style.SUCCESS("ℹ️ Using 'Filter Group' dropdown on Participants tab to get group names."))

            wait_for_overlay_to_clear(driver, timeout=cfg.timeout)
            try:
                click_inner_tabpanel_tab(driver, "Participants", timeout=cfg.timeout, logger=logger)
                wait_for_overlay_to_clear(driver, timeout=cfg.timeout)
            except Exception:
                # Not fatal; Participants is usually default
                pass


            created_count = 0
            updated_count = 0

            groups = scrape_database_group_list(driver, timeout=cfg.timeout, logger=logger)

            # 2) Fallback: Participants tab "Filter Group" dropdown if the Groups list is empty
            if not groups:
                logger.info("Groups tab list empty; falling back to 'Filter Group' dropdown on Participants tab.")
                groups = scrape_groups_from_filter_dropdown(driver, timeout=cfg.timeout, logger=logger)

            if not groups:
                dump_all_frames(driver, prefix="iv_groups_scrape_fail")
                raise CommandError("❌ No groups found on the page. Check the page structure or selectors.")


            for g in groups:
                print(f"{g['idx']:>2}: {g['name']}")

            total = len(groups)
            logger.info("Found %d groups to process.", total)

            if dry_run:
                logger.info("Dry-run mode enabled: no groups will be saved to the database.")

            for g in groups:
                group_name = (g["name"] or "").strip()

                logger.info("Group Name: %s", group_name)

                if dry_run:
                    group_exists = Groups.objects.filter(group_name=group_name).exists()
                    if group_exists:
                        updated_count += 1
                        logger.info("Would update group: %s", group_name)
                    else:
                        created_count += 1
                        logger.info("Would create group: %s", group_name)
                else:
                    group, created = Groups.objects.update_or_create(
                        group_name=group_name,
                        defaults={
                            "group_points": 1,  # Default points, adjust as needed
                        },
                    )
                    if created:
                        created_count += 1
                        logger.info("Created group: %s,%s", group.id, group.group_name)
                    else:
                        updated_count += 1
                        logger.info("Updated group: %s,%s", group.id, group.group_name)

            summary = f"✅ Processed: {total} groups, Created: {created_count}, Updated: {updated_count}"
            logger.info("%s", summary)
            logger.info("✅ Group import from iVolunteer complete.")
            if dry_run:
                logger.info("✅ Dry-run mode enabled: no groups were saved.")

        except Exception as e:
            logger.error("❌ Error during command execution: %s", e)
            if driver:
                debug_dump_page(driver, "iv_command_error")
            raise CommandError(f"❌ Command failed: {e}") from e
        finally:
            try:
                if driver is not None:
                    driver.quit()
            except Exception:
                pass
