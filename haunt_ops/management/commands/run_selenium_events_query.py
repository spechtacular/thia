"""
run_selenium_events_query.py — hardened login for iVolunteer (Firefox by default)

Key changes:
- Default browser: Firefox (manual login succeeded with Firefox).
- Sets Firefox UA + language similar to your successful session.
- Types with small delays and fires input/change events (GWT-friendly).
- Stricter success criteria: login form must disappear AND admin iframe appear.
- Logs an optional SHA-256 of the provided password (disabled by default).

Usage:
  python manage.py run_selenium_events_query \
    --iv-url "https://the-haunt.ivolunteer.com/admin" \
    --email "$IV_ADMIN_EMAIL" \
    --password "$IVOLUNTEER_PASSWORD" \
    --browser firefox \
    --dump-frames

Add --navigate-events once login is confirmed.
"""

from __future__ import annotations
import os
import argparse

from dataclasses import dataclass
from django.core.management.base import BaseCommand, CommandError
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from django.conf import settings

from selenium.webdriver.support import expected_conditions as EC
from haunt_ops.utils.logging_utils import configure_rotating_logger
from haunt_ops.models import Events
from haunt_ops.utils.time_string_utils import convert_date_formats
from haunt_ops.utils.iv_core import (
    DriverConfig,
    build_driver,
    login_iv,
    click_top_tab,
    dump_all_frames,
    debug_dump_page,
    ADMIN_IFRAME_ID,
)


@dataclass
class CmdConfig:
    iv_url: str
    iv_admin_email: str
    iv_password: str
    iv_org: str
    headless: bool
    dump_frames: bool
    timeout: int
    browser: str
    log_pw_hash: bool


class Command(BaseCommand):
    help = "Login to iVolunteer admin, click Events tab, scrape events (Firefox default)."

    def add_arguments(self, parser):
        parser.add_argument("--iv-url", dest="iv_url", default=os.environ.get("IVOLUNTEER_URL", ""))
        parser.add_argument("--email", dest="iv_admin_email", default=os.environ.get("IVOLUNTEER_ADMIN_EMAIL", ""))
        parser.add_argument("--password", dest="iv_password", default=os.environ.get("IVOLUNTEER_PASSWORD", ""))
        parser.add_argument("--iv_org", dest="iv_org", default=os.environ.get("IVOLUNTEER_ORG", ""))
        parser.add_argument("--headless",action=argparse.BooleanOptionalAction,default=True)
        parser.add_argument("--log", type=str, default="INFO",
                            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                            help="Set the log level (default: INFO) ")
        parser.add_argument("--dump-frames", action="store_true", default=False)
        parser.add_argument("--timeout", type=int, default=60)
        parser.add_argument("--browser", choices=["firefox","chrome"], default=os.environ.get("BROWSER","chrome"))
        parser.add_argument("--log-pw-hash", action="store_true", default=False)
        parser.add_argument("--dry-run", action="store_true", help="Simulate updates without saving to database.")

    def _scrape_events(self, driver, timeout=20):
        driver.switch_to.default_content()
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, "//div[@__idx]"))
            )
            tiles = driver.find_elements(By.XPATH, "//div[@__idx]")
            events = []
            for tile in tiles:
                # Title
                try:
                    title_el = tile.find_element(By.XPATH, ".//div[contains(@style,'font-weight: bold')]")
                    title = title_el.text.splitlines()[0].strip()
                except Exception:
                    title = tile.find_element(By.XPATH, ".//div").text.splitlines()[0].strip()

                # Start + Status
                try:
                    start = tile.find_element(By.XPATH, ".//b[normalize-space()='Start:']/following-sibling::i[1]").text.strip()
                except Exception:
                    start = None
                try:
                    status = tile.find_element(By.XPATH, ".//b[normalize-space()='Status:']/following-sibling::i[1]").text.strip()
                except Exception:
                    status = None

                events.append({"title": title, "start": start, "status": status})
            return events
        finally:
            driver.switch_to.default_content()

    def handle(self, *args, **options):
        headless=options.get("headless", True)

        cfg = CmdConfig(
            iv_url=options["iv_url"],
            iv_admin_email=options["iv_admin_email"],
            iv_password=options["iv_password"],
            iv_org=options["iv_org"],
            headless=headless,
            dump_frames=options["dump_frames"],
            timeout=max(15, int(options["timeout"])),
            browser=options["browser"],
            log_pw_hash=options["log_pw_hash"],
        )
        dry_run = options["dry_run"]
        log_level=options.get("log", "INFO").upper()

         # Get a unique log file using __file__
        logger = configure_rotating_logger(
            __file__, log_dir=settings.LOG_DIR, log_level=log_level
        )

        logger.info("querying and parsing ivolunteer event list.")
        logger.info("Log level set to: %s", log_level)
        logger.info("Headless mode: %s", headless)
        logger.debug("Log directory: %s", settings.LOG_DIR)




        if not (cfg.iv_url and cfg.iv_admin_email and cfg.iv_password):
            missing = [k for k, v in [
                ("IVOLUNTEER_URL", cfg.iv_url),
                ("IVOLUNTEER_ADMIN_EMAIL", cfg.iv_admin_email),
                ("IVOLUNTEER_ORG", cfg.iv_org),
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

            if not click_top_tab(driver, "Events", timeout=cfg.timeout, logger=logger):
                dump_all_frames(driver, prefix="iv_events_click_fail_topdoc")
                raise CommandError("Could not activate the 'Events' tab from the landing page menu.")

            self.stdout.write(self.style.SUCCESS("✅ Events tab activated successfully."))

            logger.info("✅ Navigated to Events page.")
            created_count = 0
            updated_count = 0

            events = self._scrape_events(driver, timeout=cfg.timeout or 20)
            if not events:
                raise CommandError("❌ No events found on the page. Check the page structure or selectors.")

            total = len(events)
            logger.info("Found %d events to process.", total)

            if dry_run:
                logger.info("Dry-run mode enabled: no events will be saved to the database.")

            for ev in events:
                ev_name = (ev["title"] or "").strip()
                ev_start_raw = (ev["start"] or "").strip() if ev.get("start") else ""
                ev_status = (ev["status"] or "").strip()
                logger.info("Event Name: %s, Start: %s, Status: %s", ev_name, ev_start_raw, ev_status)

                parsed_event_date = convert_date_formats(ev_start_raw)
                if not parsed_event_date:
                    logger.error("❌ Missing or unparseable start date for '%s': %r", ev_name, ev_start_raw)
                    continue

                formatted_event_date = parsed_event_date.strftime("%Y-%m-%d")

                if dry_run:
                    event_exists = Events.objects.filter(event_name=ev_name).exists()
                    if event_exists:
                        updated_count += 1
                        logger.info("Would update event: %s", ev_name)
                    else:
                        created_count += 1
                        logger.info("Would create event: %s", ev_name)
                else:
                    event, created = Events.objects.update_or_create(
                        event_date=formatted_event_date,
                        defaults={
                            "event_name": ev_name,
                            "event_status": ev_status,
                        },
                    )
                    if created:
                        created_count += 1
                        logger.info("Created event: %s,%s", event.id, formatted_event_date)
                    else:
                        updated_count += 1
                        logger.info("Updated event: %s,%s", event.id, formatted_event_date)

            summary = f"✅ Processed: {total} events, Created: {created_count}, Updated: {updated_count}"
            logger.info("%s", summary)
            logger.info("✅ Event import from iVolunteer complete.")
            if dry_run:
                logger.info("✅ Dry-run mode enabled: no events were saved.")

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
