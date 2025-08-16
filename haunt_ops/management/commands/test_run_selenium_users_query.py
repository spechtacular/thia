# haunt_ops/management/commands/run_selenium_users_query.py

from __future__ import annotations
import logging
import os
from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from haunt_ops.utils.iv_core import (
    DriverConfig,
    build_driver,
    login_iv,
    click_top_tab,
    click_inner_tabpanel_tab,  # make sure you have the robust version
    dump_all_frames,
    debug_dump_page,
    ADMIN_IFRAME_ID,
)

logger = logging.getLogger("haunt_ops")


@dataclass
class CmdConfig:
    iv_url: str
    iv_admin_email: str
    iv_password: str
    headless: bool
    timeout: int
    browser: str
    log_pw_hash: bool


class Command(BaseCommand):
    help = "Run iVolunteer Database → Reports: DbParticipantReportExcel (EXCEL, INFINITE, EMAIL_NAME, All Participants, INCLUDE_EVENTS)."

    def add_arguments(self, parser):
        parser.add_argument("--iv-url", dest="iv_url", default=os.environ.get("IVOLUNTEER_URL", ""))
        parser.add_argument("--email", dest="iv_admin_email", default=os.environ.get("IVOLUNTEER_ADMIN_EMAIL", ""))
        parser.add_argument("--password", dest="iv_password", default=os.environ.get("IVOLUNTEER_PASSWORD", ""))
        parser.add_argument("--headless", action="store_true", default=False)
        parser.add_argument("--timeout", type=int, default=20)
        parser.add_argument("--browser", choices=["firefox","chrome"], default=os.environ.get("BROWSER","firefox"))
        parser.add_argument("--log-pw-hash", action="store_true", default=False)
        parser.add_argument("--dry-run", action="store_true", help="Set up the report UI but do not click Run/Export.")

    # ----------------------------
    # Helpers (local to this command)
    # ----------------------------
    def _wait_for_reports_panel(self, driver, timeout: int) -> bool:
        """
        Wait for any hallmark of the 'Reports' UI to be visible.
        """
        driver.switch_to.default_content()
        wait = WebDriverWait(driver, timeout)
        anchors = [
            # Title 'Reports'
            "//div[contains(@class,'GKEPJM3CMUB') and normalize-space(text())='Reports' and not(ancestor::*[@aria-hidden='true'])]",
            # 'Report by' label text
            "//span[contains(@class,'GKEPJM3CEWB') and contains(normalize-space(.),'Report') and not(ancestor::*[@aria-hidden='true'])]",
            # 'Format:' label
            "//span[contains(@class,'GKEPJM3CEWB') and normalize-space(.)='Format:' and not(ancestor::*[@aria-hidden='true'])]",
            # 'Include Participants' label
            "//span[contains(@class,'GKEPJM3CEWB') and contains(normalize-space(.),'Include Participants') and not(ancestor::*[@aria-hidden='true'])]",
        ]
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, "|".join(anchors))))
            logger.info("✅ Reports panel UI detected.")
            return True
        except TimeoutException:
            logger.error("❌ Reports panel UI markers not found after selecting 'Reports'.")
            return False

    def _find_labeled_select(self, driver, label_text: str, timeout: int):
        """
        Locate the <select> that belongs to a visible label span (class GKEPJM3CEWB) with specific text.
        The pattern on this UI is usually:
          <table> <span class='GKEPJM3CEWB'>Label:</span> ... <select class='GKEPJM3CLLB'>...</select>
        We look within the same small table area (ancestor::table[1]).
        """
        driver.switch_to.default_content()
        wait = WebDriverWait(driver, timeout)
        label_xpath = (
            "//span[contains(@class,'GKEPJM3CEWB') and "
            f"normalize-space(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'))="
            f"normalize-space(translate('{label_text}', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')) and "
            "not(ancestor::*[@aria-hidden='true'])]"
        )
        label_el = wait.until(EC.presence_of_element_located((By.XPATH, label_xpath)))
        container_table = label_el.find_element(By.XPATH, "./ancestor::table[1]")
        try:
            sel = container_table.find_element(By.XPATH, ".//select[not(ancestor::*[@aria-hidden='true'])]")
            return Select(sel)
        except NoSuchElementException:
            # Fallback: a nearby select in same row/next row
            near_sel = label_el.find_element(By.XPATH, "./ancestor::tr[1]/following::select[1]")
            return Select(near_sel)

    def _select_option(self, sel: Select, *, value: str | None = None, text: str | None = None, contains: bool = False) -> bool:
        """
        Try to select an option either by exact @value, or by visible text (exact/contains).
        """
        try:
            if value is not None:
                sel.select_by_value(value)
                return True
        except Exception:
            pass

        try:
            if text is not None and not contains:
                sel.select_by_visible_text(text)
                return True
        except Exception:
            pass

        if text is not None and contains:
            # Scan options and choose the first that contains the text fragment (case-insensitive).
            low = text.strip().lower()
            for opt in sel.options:
                if (opt.text or "").strip().lower().find(low) >= 0:
                    sel._el.click()  # focus select
                    opt.click()
                    return True

        return False

    def _ensure_checkbox_state(self, driver, label_text: str, *, check: bool, timeout: int) -> bool:
        """
        If 'List Events for each participant' is a checkbox on your instance,
        this will find it by label text and ensure it is checked/unchecked.
        If it's a select (as on some skins), you'll simply use _find_labeled_select instead.
        """
        driver.switch_to.default_content()
        wait = WebDriverWait(driver, timeout)
        # Find a label-like span with text, then nearest checkbox input
        label_xpath = (
            "//span[contains(@class,'GKEPJM3CEWB') and "
            f"contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
            f"translate('{label_text}', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')) and "
            "not(ancestor::*[@aria-hidden='true'])]"
        )
        try:
            label_el = wait.until(EC.presence_of_element_located((By.XPATH, label_xpath)))
        except TimeoutException:
            return False
        # Walk up to a small container and look for input[type=checkbox]
        container = label_el.find_element(By.XPATH, "./ancestor::table[1]")
        try:
            cb = container.find_element(By.XPATH, ".//input[@type='checkbox' and not(ancestor::*[@aria-hidden='true'])]")
        except NoSuchElementException:
            # fallback: next input checkbox nearby
            try:
                cb = label_el.find_element(By.XPATH, "./following::input[@type='checkbox'][1]")
            except NoSuchElementException:
                return False

        is_checked = cb.is_selected()
        if check and not is_checked:
            try:
                cb.click()
            except Exception:
                driver.execute_script("arguments[0].click();", cb)
        elif (not check) and is_checked:
            try:
                cb.click()
            except Exception:
                driver.execute_script("arguments[0].click();", cb)
        return True

    def _click_run_or_export(self, driver, timeout: int) -> bool:
        """
        Try a few common button labels to run/export the report.
        """
        driver.switch_to.default_content()
        wait = WebDriverWait(driver, timeout)

        # Common GWT buttons are <button class='gwt-Button ...'>TEXT</button>
        candidates = [
            "Run", "Run Report",
            "Export", "Export Report",
            "Download", "Generate", "Create Report",
            "Excel", "Export to Excel",
        ]
        for label in candidates:
            try:
                btn = wait.until(EC.element_to_be_clickable((
                    By.XPATH,
                    f"//button[contains(@class,'gwt-Button') and normalize-space(text())={repr(label)} and not(ancestor::*[@aria-hidden='true'])]"
                )))
                try:
                    btn.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", btn)
                logger.info("✅ Clicked report action button: %s", label)
                return True
            except TimeoutException:
                continue

        # Fallback: any visible button with 'Excel' in it
        try:
            btn = wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//button[contains(@class,'gwt-Button') and contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'excel') and not(ancestor::*[@aria-hidden='true'])]"
            )))
            try:
                btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", btn)
            logger.info("✅ Clicked report fallback action button containing 'Excel'.")
            return True
        except TimeoutException:
            logger.error("❌ Could not find a Run/Export/Download button.")
            return False

    # ----------------------------
    # Command logic
    # ----------------------------
    def handle(self, *args, **options):
        cfg = CmdConfig(
            iv_url=options["iv_url"],
            iv_admin_email=options["iv_admin_email"],
            iv_password=options["iv_password"],
            headless=options["headless"],
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
            # Build driver (no custom download_dir; DriverConfig doesn't support it)
            driver = build_driver(DriverConfig(browser=cfg.browser, headless=cfg.headless))

            # Login
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
            self.stdout.write(self.style.SUCCESS("✅ Login completed successfully."))
            logger.info("Operating in top document; ignoring hidden %s iframe.", ADMIN_IFRAME_ID)

            # Top tab: Database
            if not click_top_tab(driver, "Database", timeout=cfg.timeout, logger=logger):
                dump_all_frames(driver, prefix="iv_users_db_click_fail")
                raise CommandError("Could not activate the 'Database' top tab.")

            # Inner tab: Reports
            if not click_inner_tabpanel_tab(driver, "Reports", timeout=cfg.timeout, logger=logger):
                dump_all_frames(driver, prefix="iv_fail_click_inner_tab_reports")
                raise CommandError("❌ Failed to select inner tab 'Reports'.")

            if not self._wait_for_reports_panel(driver, timeout=cfg.timeout):
                dump_all_frames(driver, prefix="iv_reports_panel_not_loaded")
                raise CommandError("❌ Reports panel did not load.")

            # ----------------------------
            # Configure the report options
            # ----------------------------

            # Report by: DbParticipantReportExcel
            try:
                sel = self._find_labeled_select(driver, "Report by:", timeout=cfg.timeout)
                if not self._select_option(sel, value="DbParticipantReportExcel"):
                    # fallback to visible text contains
                    ok_sel = self._select_option(sel, text="DbParticipantReportExcel", contains=True)
                    if not ok_sel:
                        raise CommandError("Could not set 'Report by' to DbParticipantReportExcel.")
                logger.info("✅ Report by set to DbParticipantReportExcel")
            except Exception as e:
                dump_all_frames(driver, prefix="iv_users_report_select_reportby_fail")
                raise CommandError(f"Failed to set 'Report by': {e}") from e

            # Format: EXCEL
            try:
                sel = self._find_labeled_select(driver, "Format:", timeout=cfg.timeout)
                if not self._select_option(sel, value="EXCEL"):
                    _ok = self._select_option(sel, text="EXCEL") or self._select_option(sel, text="Excel", contains=True)
                    if not _ok:
                        raise CommandError("Could not set 'Format' to EXCEL.")
                logger.info("✅ Format set to EXCEL")
            except Exception as e:
                dump_all_frames(driver, prefix="iv_users_report_select_format_fail")
                raise CommandError(f"Failed to set 'Format': {e}") from e

            # Page Size: INFINITE
            try:
                sel = self._find_labeled_select(driver, "Page Size:", timeout=cfg.timeout)
                if not self._select_option(sel, value="INFINITE"):
                    _ok = self._select_option(sel, text="INFINITE") or self._select_option(sel, text="All", contains=True)
                    if not _ok:
                        raise CommandError("Could not set 'Page Size' to INFINITE.")
                logger.info("✅ Page Size set to INFINITE")
            except Exception as e:
                dump_all_frames(driver, prefix="iv_users_report_select_pagesize_fail")
                raise CommandError(f"Failed to set 'Page Size': {e}") from e

            # Sort by: EMAIL_NAME
            try:
                sel = self._find_labeled_select(driver, "Sort by:", timeout=cfg.timeout)
                if not self._select_option(sel, value="EMAIL_NAME"):
                    # fallback to any option containing 'Email' or 'Name' appropriately
                    _ok = self._select_option(sel, text="EMAIL_NAME") or self._select_option(sel, text="Email", contains=True)
                    if not _ok:
                        raise CommandError("Could not set 'Sort by' to EMAIL_NAME.")
                logger.info("✅ Sort by set to EMAIL_NAME")
            except Exception as e:
                dump_all_frames(driver, prefix="iv_users_report_select_sortby_fail")
                raise CommandError(f"Failed to set 'Sort by': {e}") from e

            # Include Participants: All Database Participants
            try:
                sel = self._find_labeled_select(driver, "Include Participants", timeout=cfg.timeout)
                # Try exact visible text first (most likely)
                ok_inc = self._select_option(sel, text="All Database Participants") \
                         or self._select_option(sel, value="ALL_DATABASE_PARTICIPANTS") \
                         or self._select_option(sel, text="All", contains=True)
                if not ok_inc:
                    raise CommandError("Could not set 'Include Participants' to 'All Database Participants'.")
                logger.info("✅ Include Participants set to 'All Database Participants'")
            except Exception as e:
                dump_all_frames(driver, prefix="iv_users_report_select_include_participants_fail")
                raise CommandError(f"Failed to set 'Include Participants': {e}") from e

            # List Events for each participant: INCLUDE_EVENTS
            # Some skins show this as a select; some as a checkbox.
            try:
                # Try select first
                try:
                    sel = self._find_labeled_select(driver, "List Events", timeout=5)
                    ok_events = self._select_option(sel, value="INCLUDE_EVENTS") \
                               or self._select_option(sel, text="INCLUDE_EVENTS") \
                               or self._select_option(sel, text="Include", contains=True)
                    if ok_events:
                        logger.info("✅ 'List Events for each participant' set to INCLUDE_EVENTS (select).")
                    else:
                        raise NoSuchElementException("Select present but matching option not found.")
                except Exception:
                    # Try checkbox fallback
                    cb_ok = self._ensure_checkbox_state(driver, "List Events", check=True, timeout=5)
                    if cb_ok:
                        logger.info("✅ 'List Events for each participant' enabled (checkbox).")
                    else:
                        raise CommandError("Could not set 'List Events for each participant' to INCLUDE_EVENTS.")
            except Exception as e:
                dump_all_frames(driver, prefix="iv_users_report_select_list_events_fail")
                raise CommandError(f"Failed to set 'List Events for each participant': {e}") from e

            # ----------------------------
            # Run / Export the report
            # ----------------------------
            if dry_run:
                logger.info("🧪 Dry-run enabled: skipping Run/Export click.")
                self.stdout.write(self.style.SUCCESS("✅ Report options configured (dry-run)."))
                return

            if not self._click_run_or_export(driver, timeout=cfg.timeout):
                dump_all_frames(driver, prefix="iv_users_report_click_run_fail")
                raise CommandError("❌ Could not find a Run/Export/Download button to click.")

            self.stdout.write(self.style.SUCCESS("✅ Report initiated (browser should handle the Excel download)."))

        except Exception as e:
            logger.error("❌ Error during users report command: %s", e)
            if driver:
                debug_dump_page(driver, "iv_users_command_error")
            raise CommandError(f"❌ Command failed: {e}") from e
        finally:
            try:
                if driver is not None:
                    driver.quit()
            except Exception:
                pass
