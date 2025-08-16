"""
Command: run_selenium_users_query
Generates the iVolunteer Database > Reports "Participants" Excel report via Selenium.

Report settings:
- Report by: DbParticipantReportExcel
- Format: EXCEL
- Page Size: INFINITE
- Sort by: EMAIL_NAME
- Include Participants: All Database Participants
- List Events for each participant: INCLUDE_EVENTS (checked)

Optionally waits for the download to complete in --download-dir.
"""

from __future__ import annotations
import os
import time
import glob
import logging
from dataclasses import dataclass
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from haunt_ops.utils.iv_core import (
    DriverConfig,
    build_driver,
    login_iv,
    click_top_tab,
    click_inner_tabpanel_tab,
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
    dump_frames: bool
    download_dir: Optional[str]
    wait_download: bool
    download_timeout: int


# ---------------------------
# Generic DOM helper utilities
# ---------------------------

def _label_following_select_xpath(label_text: str) -> str:
    # iVolunteer (GWT) tends to render labels in a span with class like GKEPJM3CEWB,
    # with the <select> in the same small table below it.
    return (
        "//span[contains(@class,'GKEPJM3CEWB') and normalize-space(text())=$L]"
        "/ancestor::table[1]//select"
    ).replace("$L", f"'{label_text}'")


def _click_tab(driver, tab_text: str, *, timeout: int):
    if not click_inner_tabpanel_tab(driver, tab_text, timeout=timeout, logger=logger):
        dump_all_frames(driver, prefix=f"iv_fail_click_inner_tab_{tab_text.lower()}")
        raise CommandError(f"❌ Failed to select inner tab '{tab_text}'.")


def _select_dropdown_by_label_text(driver, label_text: str, *, option_value: str = "", option_text: str = "", timeout: int = 20):
    """
    Selects a dropdown <select> that is rendered under a label (span) whose visible text equals `label_text`.
    You can provide either `option_value` (preferred) or `option_text`.

    Works against GWT structure:
      <span class="...">Label</span>
      <select class="GKEPJM3CLLB">
        <option value="...">Text</option>
      </select>
    """
    driver.switch_to.default_content()
    wait = WebDriverWait(driver, timeout)
    select_xpath = _label_following_select_xpath(label_text)
    sel = wait.until(EC.presence_of_element_located((By.XPATH, select_xpath)))

    if option_value:
        opt = sel.find_element(By.XPATH, f".//option[@value={repr(option_value)}]")
    else:
        opt = sel.find_element(By.XPATH, f".//option[normalize-space(text())={repr(option_text)}]")

    # Use JS click to avoid any overlay issues
    driver.execute_script("arguments[0].selected = true; arguments[0].dispatchEvent(new Event('change', {bubbles: true}));", opt)
    logger.info("Set '%s' to %s", label_text, option_value or option_text)


def _click_button_by_text(driver, *texts: str, timeout: int = 20):
    """
    Clicks the first visible <button> (gwt-Button) whose text equals any of `texts`.
    """
    driver.switch_to.default_content()
    wait = WebDriverWait(driver, timeout)
    for t in texts:
        try:
            btn = wait.until(EC.element_to_be_clickable((
                By.XPATH,
                f"//button[contains(@class,'gwt-Button') and normalize-space(text())={repr(t)}]"
            )))
            try:
                btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", btn)
            logger.info("Clicked button '%s'", t)
            return True
        except Exception:
            continue
    raise CommandError(f"❌ Unable to find a clickable button among: {', '.join(texts)}")


def _click_radio_by_option_text(driver, option_text: str, *, timeout: int = 20):
    """
    Click a radio input associated with a visible label that matches option_text.
    This tries common GWT patterns: a text node near an <input type='radio'> or a sibling label.
    """
    driver.switch_to.default_content()
    wait = WebDriverWait(driver, timeout)

    # Option A: label text node, preceding sibling input
    xpaths = [
        # label text within same table cell (most common)
        f"//td[normalize-space(.)={repr(option_text)}]//preceding::input[@type='radio'][1]",
        # label element linked to radio
        f"//label[normalize-space(.)={repr(option_text)}]/preceding::input[@type='radio'][1]",
        # any radio whose following-sibling text matches
        f"//input[@type='radio']/following::text()[normalize-space(.)={repr(option_text)}]/preceding::input[@type='radio'][1]",
    ]
    for xp in xpaths:
        try:
            el = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
            try:
                el.click()
            except Exception:
                driver.execute_script("arguments[0].click();", el)
            logger.info("Selected radio option '%s'", option_text)
            return True
        except Exception:
            continue
    raise CommandError(f"❌ Could not select radio with option text '{option_text}'")


def _set_checkbox_by_label_contains(driver, label_contains: str, checked: bool = True, *, timeout: int = 20):
    """
    Find a checkbox by a nearby label whose text contains `label_contains`, and set it to desired state.
    """
    driver.switch_to.default_content()
    wait = WebDriverWait(driver, timeout)

    # Find a label/span cell that contains the marker text, then locate a checkbox in the same small table
    # This is tolerant of typical GWT table-based forms.
    container = wait.until(EC.presence_of_element_located((
        By.XPATH,
        f"//span[contains(@class,'GKEPJM3CEWB') and contains(normalize-space(.), {repr(label_contains)})]/ancestor::table[1]"
    )))
    try:
        checkbox = container.find_element(By.XPATH, ".//input[@type='checkbox']")
    except Exception:
        # fallback: any checkbox near that label within the section
        checkbox = wait.until(EC.presence_of_element_located((
            By.XPATH,
            f"//input[@type='checkbox' and not(ancestor::*[@aria-hidden='true'])][1]"
        )))

    is_checked = checkbox.is_selected()
    if checked != is_checked:
        try:
            checkbox.click()
        except Exception:
            driver.execute_script("arguments[0].click();", checkbox)
        logger.info("Set checkbox '%s' => %s", label_contains, checked)
    else:
        logger.info("Checkbox '%s' already %s", label_contains, "checked" if checked else "unchecked")


def _wait_for_gwt_loader_to_clear(driver, *, timeout: int = 60):
    """
    Simple wait for GWT 'glass' or spinners to go away after clicking Run/Export.
    """
    driver.switch_to.default_content()
    wait = WebDriverWait(driver, timeout)
    end = time.time() + timeout
    # Known overlay class used by ivolunteer admin: gwt-PopupPanelGlass (shown while busy)
    while time.time() < end:
        try:
            glass = driver.find_elements(By.CSS_SELECTOR, ".gwt-PopupPanelGlass")
            visible = [g for g in glass if g.is_displayed()]
            if not visible:
                return
        except Exception:
            return
        time.sleep(0.3)
    # If we get here, we timed out—but the export could still be initiated; don't hard fail.
    logger.warning("Timed out waiting for GWT loader to clear; continuing.")


def _wait_for_download(download_dir: str, *, since_ts: float, timeout: int = 120) -> Optional[str]:
    """
    Wait for a new .xls/.xlsx file to appear in `download_dir` after timestamp `since_ts`.
    Returns the path or None if not found.
    """
    end = time.time() + timeout
    patterns = ["*.xls", "*.xlsx", "*.csv"]
    while time.time() < end:
        for pat in patterns:
            for path in glob.glob(os.path.join(download_dir, pat)):
                try:
                    st = os.stat(path)
                    if st.st_mtime >= since_ts and not path.endswith(".crdownload") and not path.endswith(".part"):
                        return path
                except FileNotFoundError:
                    continue
        time.sleep(0.5)
    return None


# ---------------------------
# Command
# ---------------------------

class Command(BaseCommand):
    help = "Run the iVolunteer Database > Reports 'Participants (Excel)' export via Selenium."

    def add_arguments(self, parser):
        parser.add_argument("--iv-url", dest="iv_url", default=os.environ.get("IVOLUNTEER_URL", ""))
        parser.add_argument("--email", dest="iv_admin_email", default=os.environ.get("IVOLUNTEER_ADMIN_EMAIL", ""))
        parser.add_argument("--password", dest="iv_password", default=os.environ.get("IVOLUNTEER_PASSWORD", ""))
        parser.add_argument("--headless", action="store_true", default=False)
        parser.add_argument("--timeout", type=int, default=60)
        parser.add_argument("--browser", choices=["firefox","chrome"], default=os.environ.get("BROWSER","firefox"))
        parser.add_argument("--log-pw-hash", action="store_true", default=False)
        parser.add_argument("--dump-frames", action="store_true", default=False)
        parser.add_argument("--download-dir", default=os.environ.get("IVOLUNTEER_DOWNLOAD_DIR", "/tmp"),
                            help="Directory where the browser will save the exported Excel file.")
        parser.add_argument("--wait-download", action="store_true", default=False,
                            help="Wait for the Excel file to appear in --download-dir and print the path.")
        parser.add_argument("--download-timeout", type=int, default=180,
                            help="Seconds to wait for the Excel download when --wait-download is set.")

    def handle(self, *args, **options):
        cfg = CmdConfig(
            iv_url=options["iv_url"],
            iv_admin_email=options["iv_admin_email"],
            iv_password=options["iv_password"],
            headless=options["headless"],
            timeout=max(20, int(options["timeout"])),
            browser=options["browser"],
            log_pw_hash=options["log_pw_hash"],
            dump_frames=options["dump_frames"],
            download_dir=options["download_dir"],
            wait_download=options["wait_download"],
            download_timeout=int(options["download_timeout"]),

        )

        if not (cfg.iv_url and cfg.iv_admin_email and cfg.iv_password):
            missing = [k for k, v in [
                ("IVOLUNTEER_URL", cfg.iv_url),
                ("IVOLUNTEER_ADMIN_EMAIL", cfg.iv_admin_email),
                ("IVOLUNTEER_PASSWORD", cfg.iv_password),
            ] if not v]
            raise CommandError(f"❌ Missing required inputs: {', '.join(missing)}. Provide flags or set env vars.")

        # Ensure the download dir exists if we plan to wait for downloads
        if cfg.wait_download and cfg.download_dir:
            os.makedirs(cfg.download_dir, exist_ok=True)

        logger.info(
            "▶ Starting (users report) with email=%s pw_len=%s headless=%s browser=%s download_dir=%s wait_download=%s",
            cfg.iv_admin_email, len(cfg.iv_password or ''), cfg.headless, cfg.browser, cfg.download_dir, cfg.wait_download
        )

        driver = None
        try:
            # If your build_driver supports download_dir in DriverConfig, pass it here.
            # (If not, your existing utility can be extended to set browser prefs to save to that folder.)
            driver = build_driver(DriverConfig(
                browser=cfg.browser,
                headless=cfg.headless,
                download_dir=cfg.download_dir,   # safe to pass; no-op if not supported by your helper
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
                dump_all_frames(driver, prefix="iv_users_after_login")

            self.stdout.write(self.style.SUCCESS("✅ Login completed successfully."))
            logger.info("Operating in top document; ignoring hidden %s iframe.", ADMIN_IFRAME_ID)

            # Navigate to Database -> Reports
            if not click_top_tab(driver, "Database", timeout=cfg.timeout, logger=logger):
                dump_all_frames(driver, prefix="iv_users_database_click_fail")
                raise CommandError("Could not activate the 'Database' tab.")

            _click_tab(driver, "Reports", timeout=cfg.timeout)
            self.stdout.write(self.style.SUCCESS("✅ Reports tab opened."))

            # -------- Configure report --------
            # Report by: DbParticipantReportExcel
            # Label might be "Report" or "Report by" depending on environment; try both.
            try:
                _select_dropdown_by_label_text(driver, "Report", option_value="DbParticipantReportExcel", timeout=cfg.timeout)
            except Exception:
                _select_dropdown_by_label_text(driver, "Report by", option_value="DbParticipantReportExcel", timeout=cfg.timeout)

            # Format: EXCEL
            _select_dropdown_by_label_text(driver, "Format", option_value="EXCEL", timeout=cfg.timeout)

            # Page Size: INFINITE
            # Some UIs render "Page Size" or "Page size"; try both casing
            try:
                _select_dropdown_by_label_text(driver, "Page Size", option_value="INFINITE", timeout=cfg.timeout)
            except Exception:
                _select_dropdown_by_label_text(driver, "Page size", option_value="INFINITE", timeout=cfg.timeout)

            # Sort by: EMAIL_NAME
            _select_dropdown_by_label_text(driver, "Sort by", option_value="EMAIL_NAME", timeout=cfg.timeout)

            # Include Participants: All Database Participants (radio)
            # Exact visible text tends to be "All Database Participants"
            _click_radio_by_option_text(driver, "All Database Participants", timeout=cfg.timeout)

            # List Events for each participant: INCLUDE_EVENTS (checkbox ON)
            # The left label typically reads like "List Events for each participant"
            _set_checkbox_by_label_contains(driver, "List Events for each participant", checked=True, timeout=cfg.timeout)

            if cfg.dump_frames:
                dump_all_frames(driver, prefix="iv_users_report_configured")

            # -------- Run / Export --------
            # Buttons seen in the wild: "Run", "Export", "Download"
            ts_before = time.time()
            _click_button_by_text(driver, "Run", "Export", "Download", timeout=cfg.timeout)

            _wait_for_gwt_loader_to_clear(driver, timeout=max(20, cfg.timeout))

            self.stdout.write(self.style.SUCCESS("✅ Report triggered."))

            # -------- Wait for download (optional) --------
            if cfg.wait_download and cfg.download_dir:
                self.stdout.write("⏳ Waiting for download to complete...")
                path = _wait_for_download(cfg.download_dir, since_ts=ts_before, timeout=cfg.download_timeout)
                if path:
                    logger.info("✅ Downloaded: %s", path)
                    self.stdout.write(self.style.SUCCESS(f"✅ Downloaded: {path}"))
                else:
                    logger.warning("⚠️ No new file detected in %s within %ss.", cfg.download_dir, cfg.download_timeout)
                    self.stdout.write(self.style.WARNING(
                        f"⚠️ No new file detected in {cfg.download_dir} within {cfg.download_timeout}s."
                    ))

            self.stdout.write(self.style.SUCCESS("✅ Users report complete."))

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
