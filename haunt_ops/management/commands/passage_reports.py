import os
import sys
import time
import csv
import traceback
import threading
from datetime import datetime
from typing import Optional, List, Dict
import re

"""
Passage Reports — Django management command (Selenium-based)

This version:
- Keeps the robust workaround for environments missing Python's built-in `ssl` module.
- **Starts directly at `https://app.gopassage.com/users/sign_in`** (skips home page).
- Adds navigation for **Events ▸ Upcoming** via the top navbar dropdown.
- Fixes a syntax error in `navigate_to_admin` and a test string literal.
- NEW: Scrape the **Upcoming Events** table across **all pagination pages**
  and optionally save to CSV with `--scrape-upcoming` and `--output-csv`.

NOTE: The SSL shim is a pragmatic fallback and not a security best practice.
"""

# ----------------------------- SSL shim -----------------------------
# If the Python runtime doesn't include the `ssl` module, Selenium import will
# fail early (e.g., `from ssl import CERT_NONE`). Provide a tiny shim so that
# imports succeed. This is enough for local ws:// DevTools connections which do
# not require TLS. Do NOT rely on this for real TLS.
SSL_SHIMMED = False
try:
    import ssl as _ssl  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    import types
    _ssl = types.ModuleType("ssl")
    # Minimal constants Selenium/websocket-client might touch
    _ssl.CERT_NONE = 0
    _ssl.CERT_REQUIRED = 2
    _ssl.PROTOCOL_TLS = 2

    class _DummySSLContext:
        def __init__(self, *args, **kwargs):
            pass
        def load_verify_locations(self, *args, **kwargs):
            pass
        def set_ciphers(self, *args, **kwargs):
            pass

    def _create_default_context(*args, **kwargs):
        return _DummySSLContext()

    _ssl.SSLContext = _DummySSLContext
    _ssl.create_default_context = _create_default_context

    sys.modules["ssl"] = _ssl
    SSL_SHIMMED = True


# -------------------------- Django imports --------------------------
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

# --------------------------- Selenium imports ---------------------------
# Import AFTER ssl shim so selenium can import ssl symbols.
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import TimeoutException

# Try webdriver_manager, but we disable it if SSL is shimmed (it needs HTTPS)
try:
    from webdriver_manager.chrome import ChromeDriverManager  # type: ignore
except Exception:  # pragma: no cover
    ChromeDriverManager = None  # type: ignore


############################################################
# ⚠️  IMPORTANT
# - This command is a robust scaffold with conservative selectors.
# - Update SELECTORS to match your account's DOM if needed.
# - Prefer running with --no-headless initially to validate selectors.
############################################################

# ------- Logical selectors (refine as you inspect the site) -------
SELECTORS = {
    # Top-level nav → Login
    "nav_login_link": [
        'css=a[href="/users/sign_in"]',
        'xpath=//a[normalize-space()="Login" and contains(@href, "/users/sign_in")]',
    ],

    # Cookies bar accept (optional)
    "cookie_accept": [
        'css=#cookies-bar a[data-action*="allowCookies"]',
    ],

    # The login form itself (scope our searches to this form)
    "login_form": [
        'css=form[action*="/users/sign_in"]',
        'css=form#new_user',  # Devise default id
        'xpath=//form[contains(@action, "/users/sign_in")]',
    ],

    # Login fields (scoped under login_form when possible)
    "login_email": [
        'css=input#user_email',
        'css=input[name="user[email]"]',
        'css=input[type="email"]',
    ],
    "login_password": [
        'css=input#user_password',
        'css=input[name="user[password]"]',
        'css=input[type="password"]',
    ],
    "login_submit": [
        'css=input[type="submit"][name="commit"]',
        'css=input[type="submit"]',
        'xpath=//button[normalize-space()="Log in" or normalize-space()="Login" or normalize-space()="Sign in"]',
        'xpath=//input[@type="submit" and (contains(@value, "Log in") or contains(@value, "Login") or contains(@value, "Sign in"))]',
    ],

    # Post-login markers
    "post_login_marker": [
        'css=a[href="/users/sign_out"]',
        'xpath=//a[contains(@href, "/user_account")]',
    ],

    # Admin link after login (via Account ▸ Admin)
    "nav_admin_link": [
        'css=a[href*="/event_management"]',
        'css=a[href*="/user_account"]',
        'css=a[href*="/admin"]',
        'xpath=//a[normalize-space()="Admin"]',
        'xpath=//a[contains(normalize-space(.), "Admin")]',
        'xpath=//a[contains(normalize-space(.), "Dashboard")]',
    ],
    "account_menu_toggle": [
        'xpath=//nav//a[contains(@class, "dropdown-toggle")][normalize-space()="Account"]',
        'css=nav .navbar-right .dropdown > a.dropdown-toggle',
        'xpath=//a[@data-toggle="dropdown" and normalize-space()="Account"]',
    ],
    "account_admin_link": [
        'xpath=//ul[contains(@class, "dropdown-menu")]//a[normalize-space()="Admin" or contains(normalize-space(), "Go to Admin")]',
        'css=a[href*="/event_management"]',
        'css=a[href*="/user_account"]',
        'css=a[href*="/admin"]',
    ],

    # Reports dropdown toggle in header
    "reports_menu_toggle": [
        'xpath=//nav//a[contains(@class, "dropdown-toggle")][normalize-space()="Reports"]',
        'css=nav .navbar-left .dropdown > a.dropdown-toggle',
    ],

    # "Events" entry inside the Reports dropdown
    "reports_events_link": [
        'css=a[href="https://app.gopassage.com/user_account/event_reports"]',
        'xpath=//a[contains(@href, "/user_account/event_reports")][normalize-space()="Events"]',
    ],

    # Events dropdown toggle and Upcoming link
    "events_menu_toggle": [
        'xpath=//nav//a[contains(@class, "dropdown-toggle")][normalize-space()="Events"]',
        'css=nav .navbar-left li.dropdown > a.dropdown-toggle',
    ],
    "events_upcoming_link": [
        'css=a[href="https://app.gopassage.com/user_account/events/upcoming_events"]',
        'xpath=//ul[contains(@class, "dropdown-menu")]//a[contains(@href, "/user_account/events/upcoming_events") and normalize-space()="Upcoming"]',
        'xpath=//a[normalize-space()="Upcoming" and contains(@href, "upcoming_events")]',
    ],

    # Generic "Reports" link (kept for backwards compatibility)
    "nav_reports_link": [
        'css=a[href*="/reports"]',
        'css=a[href*="/user_account"][href*="reports"]',
        'xpath=//a[contains(., "Reports")]',
    ],

    # Report filters — placeholders to refine for your chosen report
    "date_start": [
        'css=input[name="start_date"]',
        'css=#start_date',
    ],
    "date_end": [
        'css=input[name="end_date"]',
        'css=#end_date',
    ],
    "report_type_select": [
        'css=select[name="report"]',
        'css=#report',
    ],
    "run_report": [
        'xpath=//button[.//text()[contains(., "Run") or contains(., "Generate") or contains(., "Apply")]]',
        'css=button[type="submit"]',
    ],
    "export_button": [
        'xpath=//a[contains(., "Export") or contains(., "CSV")] | //button[contains(., "Export") or contains(., "CSV")]',
    ],
}


# ---------------------- Utility helpers ----------------------

def _chrome(download_dir: str, headless: bool) -> webdriver.Chrome:
    opts = ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,1000")
    # Loosen cert checks; helpful in CI/sandboxes
    opts.add_argument("--ignore-certificate-errors")
    opts.add_argument("--allow-insecure-localhost")
    opts.add_argument("--ignore-ssl-errors")
    opts.set_capability("acceptInsecureCerts", True)

    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    opts.add_experimental_option("prefs", prefs)

    # Prefer local chromedriver when SSL is shimmed (webdriver-manager needs HTTPS)
    use_manager = (ChromeDriverManager is not None) and (not SSL_SHIMMED) and (
        os.environ.get("SELENIUM_FORCE_LOCAL", "0") != "1"
    )

    if use_manager:
        try:
            service = ChromeService(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=opts)
        except Exception:
            # Fall back to system chromedriver if manager fails (e.g., no SSL / no internet)
            pass

    return webdriver.Chrome(options=opts)


def _find(driver: webdriver.Chrome, selector: str):
    """Find one element by CSS (default) or XPath if prefixed.
    Use prefixes: 'css=...' or 'xpath=...'. If no prefix, CSS is assumed.
    """
    if selector.startswith("xpath="):
        return driver.find_element(By.XPATH, selector.split("=", 1)[1])
    if selector.startswith("css="):
        return driver.find_element(By.CSS_SELECTOR, selector.split("=", 1)[1])
    return driver.find_element(By.CSS_SELECTOR, selector)


def _click_el(driver: webdriver.Chrome, el):
    try:
        el.click()
    except Exception:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
            driver.execute_script("arguments[0].click();", el)
        except Exception:
            raise


def _first_visible(driver: webdriver.Chrome, selectors: List[str], timeout: int = 15):
    """Return the first visible element matching any provided selector."""
    end = time.time() + timeout
    last_err = None
    while time.time() < end:
        for sel in selectors:
            try:
                el = _find(driver, sel)
                if el.is_displayed():
                    return el
            except Exception as e:
                last_err = e
                continue
        time.sleep(0.25)
    raise TimeoutException("No visible element found for any of: " + str(selectors) + "\nLast error: " + str(last_err))


def _first_visible_in(container, selectors: List[str], timeout: int = 15):
    """Like _first_visible, but restrict search to a container WebElement."""
    end = time.time() + timeout
    last_err = None
    while time.time() < end:
        for sel in selectors:
            try:
                if isinstance(sel, str) and sel.startswith("xpath="):
                    el = container.find_element(By.XPATH, sel.split("=", 1)[1])
                else:
                    css = sel.split("=", 1)[1] if sel.startswith("css=") else sel
                    el = container.find_element(By.CSS_SELECTOR, css)
                if el.is_displayed():
                    return el
            except Exception as e:
                last_err = e
                continue
        time.sleep(0.25)
    raise TimeoutException("No visible child element found for any of: " + str(selectors) + "\nLast error: " + str(last_err))


def _type(driver: webdriver.Chrome, selectors: List[str], text: str, clear: bool = True, timeout: int = 15):
    el = _first_visible(driver, selectors, timeout)
    if clear:
        try:
            el.clear()
        except Exception:
            pass
    el.send_keys(text)


def _click(driver: webdriver.Chrome, selectors: List[str], timeout: int = 15):
    el = _first_visible(driver, selectors, timeout)
    _click_el(driver, el)


def _wait_download(download_dir: str, timeout: int = 120) -> str:
    """Wait for a *new* file to appear in download_dir (non-.crdownload)."""
    baseline = set(os.listdir(download_dir))
    end = time.time() + timeout
    while time.time() < end:
        current = set(os.listdir(download_dir))
        new_files = [f for f in (current - baseline) if not f.endswith(".crdownload")]
        if new_files:
            paths = [os.path.join(download_dir, f) for f in new_files]
            paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            return paths[0]
        time.sleep(1)
    raise TimeoutError(
        f"No new downloaded file detected within {timeout} seconds in {download_dir}."
    )


def _safe_dump(driver: Optional[webdriver.Chrome], prefix: str = "passage") -> None:
    """Dump HTML and screenshot to /tmp for debugging."""
    if not driver:
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        with open(f"/tmp/{prefix}_{ts}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
    except Exception:
        pass
    try:
        driver.save_screenshot(f"/tmp/{prefix}_{ts}.png")
    except Exception:
        pass


# ---------------------- Site-specific flow ----------------------

def _signin_url(base_url: str) -> str:
    """Return the canonical sign-in URL on app.gopassage.com with a cache-buster.
    - Accepts 'https://gopassage.com' and normalizes it to 'https://app.gopassage.com'.
    - Ensures HTTPS and app subdomain even if a bare domain or 'http' is passed.
    - Preserves any existing query params, adding ts=...
    """
    from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl

    raw = (base_url or "").strip()
    if not raw:
        raw = "https://app.gopassage.com/users/sign_in"

    # Ensure scheme for parsing
    if "://" not in raw:
        raw = "https://" + raw.lstrip("/")

    parsed = urlparse(raw)

    # Normalize host
    host = (parsed.netloc or "").lower()
    if host in {"gopassage.com", "www.gopassage.com", ""}:
        host = "app.gopassage.com"

    # Normalize path
    path = parsed.path or ""
    if "users/sign_in" not in path:
        if not path.endswith("/"):
            path += "/"
        path += "users/sign_in"

    # Build query with cache-buster
    q = dict(parse_qsl(parsed.query))
    q["ts"] = str(int(time.time()))

    new_parsed = parsed._replace(scheme="https", netloc=host, path=path, query=urlencode(q), fragment="")
    return urlunparse(new_parsed)

def login_gopassage(
    driver: webdriver.Chrome,
    base_url: str,
    email: str,
    password: str,
    timeout: int = 30,
):
    # Force-start directly at the sign-in URL and skip any home-page navigation.
    sign_in_url = _signin_url(base_url)

    try:
        driver.delete_all_cookies()
    except Exception:
        pass

    driver.get(sign_in_url)
    wait = WebDriverWait(driver, timeout)
    driver.switch_to.default_content()

    # Optional cookie bar accept (non-fatal)
    try:
        _click(driver, SELECTORS["cookie_accept"], timeout=3)
    except Exception:
        pass

    # If we got bounced somewhere else (e.g., Turbo cache), force the sign-in URL again once.
    if "users/sign_in" not in driver.current_url:
        driver.get(sign_in_url)
        time.sleep(0.5)

    # Scope to the sign-in form; if not found, bail with a debug dump.
    try:
        form = _first_visible(driver, SELECTORS["login_form"], timeout=timeout)
    except Exception:
        _safe_dump(driver, "gopassage_login_form_not_found")
        raise CommandError("Sign-in form not found — update selectors or verify the URL is accessible.")

    # Fill credentials
    el = _first_visible_in(form, SELECTORS["login_email"], timeout)
    try:
        el.clear()
    except Exception:
        pass
    el.send_keys(email)

    el = _first_visible_in(form, SELECTORS["login_password"], timeout)
    try:
        el.clear()
    except Exception:
        pass
    el.send_keys(password)

    # Submit
    try:
        _first_visible_in(form, SELECTORS["login_submit"], timeout).click()
    except Exception:
        driver.execute_script("arguments[0].submit();", form)

    # Wait until we leave the sign_in page or a post-login marker appears
    try:
        wait.until(lambda d: ("sign_in" not in d.current_url.lower()))
        try:
            _first_visible(driver, SELECTORS["post_login_marker"], timeout=5)
        except Exception:
            pass
    except TimeoutException:
        _safe_dump(driver, "gopassage_login_fail")
        raise CommandError("Login may have failed — update selectors or credentials.")


def navigate_to_admin(driver: webdriver.Chrome, timeout: int = 20):
    """Navigate to the Admin/Dashboard area after login via Account ▸ Admin.
    Tries Account dropdown first, then visible Admin links, then direct URLs.
    """
    # 1) Explicit Account ▸ Admin path
    try:
        _click(driver, SELECTORS["account_menu_toggle"], timeout=5)
        time.sleep(0.2)
        _click(driver, SELECTORS["account_admin_link"], timeout=5)
        WebDriverWait(driver, timeout).until(
            lambda d: any(k in d.current_url for k in ("/event_management", "/user_account", "/admin"))
        )
        # Best-effort: ensure admin navbar (Events dropdown) is visible; non-fatal
        try:
            _first_visible(driver, SELECTORS["events_menu_toggle"], timeout=5)
        except Exception:
            pass
        return
    except Exception:
        pass

    # 2) Fallback: any visible Admin link
    try:
        _click(driver, SELECTORS["nav_admin_link"], timeout=5)
        WebDriverWait(driver, timeout).until(
            lambda d: any(k in d.current_url for k in ("/event_management", "/user_account", "/admin"))
        )
        return
    except Exception:
        pass

    # 3) Last resort: try canonical admin URLs
    for url in [
        "https://app.gopassage.com/event_management",
        "https://app.gopassage.com/user_account",
        "https://app.gopassage.com/admin",
    ]:
        try:
            driver.get(url)
            if any(k in driver.current_url for k in ("event_management", "user_account", "/admin")):
                return
        except Exception:
            continue

    _safe_dump(driver, "gopassage_admin_nav_fail")
    raise CommandError("Admin link not found; adjust SELECTORS for Account ▸ Admin or provide a stable URL.")

def navigate_to_events_upcoming(driver: webdriver.Chrome, timeout: int = 20):
    """Open the top navbar Events dropdown and click Upcoming.
    Falls back to the direct URL if the dropdown isn't interactable.
    """
    try:
        # Open the Events dropdown
        toggle = _first_visible(driver, SELECTORS["events_menu_toggle"], timeout=timeout)
        _click_el(driver, toggle)
        time.sleep(0.2)
        # Click the Upcoming item
        link = _first_visible(driver, SELECTORS["events_upcoming_link"], timeout=timeout)
        _click_el(driver, link)
        # Verify navigation
        WebDriverWait(driver, timeout).until(
            lambda d: "/user_account/events/upcoming_events" in d.current_url
        )
        return
    except Exception:
        # Fallback: go directly by URL
        try:
            driver.get("https://app.gopassage.com/user_account/events/upcoming_events")
            WebDriverWait(driver, timeout).until(
                lambda d: "/user_account/events/upcoming_events" in d.current_url
            )
            return
        except Exception:
            _safe_dump(driver, "gopassage_events_upcoming_fail")
            raise CommandError("Could not open Events ▸ Upcoming — adjust selectors or verify access.")


# ---------------------- Upcoming Events scraping ----------------------
REQUIRED_FIELDS = [
    "Event",
    "Event URL",
    "Event ID",
    "Start Time",
    "End Time",
    "Tickets Purchased",
    "Tickets Remaining",
    "Revenue",
    "Notes",
]

_HEADER_ALIASES = {
    "event": "Event",
    "start time": "Start Time",
    "end time": "End Time",
    "tickets purchased": "Tickets Purchased",
    "tickets remaining": "Tickets Remaining",
    "revenue": "Revenue",
    "revenue generated": "Revenue",
    "notes": "Notes",
}

def _normalize_header(text: str) -> str:
    t = (text or "").strip().lower()
    return _HEADER_ALIASES.get(t, text.strip())


def _map_header_indexes(table_el) -> Dict[str, int]:
    """Given a <table> element, return a mapping of REQUIRED_FIELDS -> column index.
    Uses header cell text and alias table above. Missing fields are skipped.
    """
    headers = []
    try:
        ths = table_el.find_elements(By.CSS_SELECTOR, "thead tr:first-child > *")
    except Exception:
        ths = []
    for h in ths:
        headers.append(_normalize_header(h.text))

    index_map: Dict[str, int] = {}
    for i, h in enumerate(headers):
        norm = _normalize_header(h)
        if norm in _HEADER_ALIASES.values():
            index_map[_HEADER_ALIASES.get(norm.lower(), norm)] = i
    return index_map


def _cell_text(cells, idx: int) -> str:
    try:
        if idx < 0:
            return ""
        if idx >= len(cells):
            return ""
        return (cells[idx].text or "").strip()
    except Exception:
        return ""


def scrape_upcoming_events(driver: webdriver.Chrome, timeout: int = 20) -> List[Dict[str, str]]:
    """Scrape rows from the Upcoming Events page, following pagination to the end.
    Returns a list of dicts with keys in REQUIRED_FIELDS order.
    """
    from urllib.parse import urljoin

    rows: List[Dict[str, str]] = []
    seen_pages = set()

    def _scrape_current_page():
        # There can be multiple tables on a page (one per date block)
        tables = driver.find_elements(By.CSS_SELECTOR, 'div[data-react-class="UpcomingEventsTable"] table.table')
        for t in tables:
            idx_map = _map_header_indexes(t)
            if not idx_map:
                continue
            tbody_rows = t.find_elements(By.CSS_SELECTOR, "tbody > tr")
            for tr in tbody_rows:
                tds = tr.find_elements(By.CSS_SELECTOR, "td")
                # Derive Event URL + ID from the first cell's anchor
                event_name = _cell_text(tds, idx_map.get("Event", -1))
                event_url = ""
                event_id = ""
                try:
                    event_td_idx = idx_map.get("Event", -1)
                    if event_td_idx >= 0 and event_td_idx < len(tds):
                        a = tds[event_td_idx].find_element(By.CSS_SELECTOR, 'a[href]')
                        href = a.get_attribute("href") or ""
                        event_url = urljoin(driver.current_url, href)
                        m = re.search(r"/events/(\d+)", href)
                        if m:
                            event_id = m.group(1)
                except Exception:
                    pass

                record = {
                    "Event": event_name,
                    "Event URL": event_url,
                    "Event ID": event_id,
                    "Start Time": _cell_text(tds, idx_map.get("Start Time", -1)),
                    "End Time": _cell_text(tds, idx_map.get("End Time", -1)),
                    "Tickets Purchased": _cell_text(tds, idx_map.get("Tickets Purchased", -1)),
                    "Tickets Remaining": _cell_text(tds, idx_map.get("Tickets Remaining", -1)),
                    "Revenue": _cell_text(tds, idx_map.get("Revenue", -1)),
                    "Notes": _cell_text(tds, idx_map.get("Notes", -1)),
                }
                rows.append(record)

    # Wait for at least one table to be present
    WebDriverWait(driver, timeout).until(
        lambda d: len(d.find_elements(By.CSS_SELECTOR, 'div[data-react-class="UpcomingEventsTable"] table.table')) > 0
    )

    while True:
        cur = driver.current_url
        if cur in seen_pages:
            break
        seen_pages.add(cur)

        _scrape_current_page()

        # Find a visible "Next" link in pagination (top or bottom). If none, we're done.
        next_links = driver.find_elements(By.CSS_SELECTOR, "div.pagination a.next_page[rel='next'], div.pagination a[rel='next']")
        next_links = [a for a in next_links if a.is_displayed()]
        if not next_links:
            break
        next_el = next_links[-1]  # last pagination bar on the page
        href = next_el.get_attribute("href") or ""
        if not href:
            break
        abs_href = urljoin(driver.current_url, href)
        if abs_href in seen_pages:
            break
        # Navigate to next page via direct GET for reliability
        driver.get(abs_href)
        WebDriverWait(driver, timeout).until(
            lambda d: d.current_url != cur and len(d.find_elements(By.CSS_SELECTOR, 'div[data-react-class="UpcomingEventsTable"] table.table')) > 0
        )
        time.sleep(0.2)  # small settle

    return rows


def navigate_to_reports(driver: webdriver.Chrome, timeout: int = 20):
    _click(driver, SELECTORS["nav_reports_link"], timeout=timeout)
    try:
        _first_visible(driver, SELECTORS["report_type_select"], timeout=timeout)
    except TimeoutException:
        _safe_dump(driver, "gopassage_reports_nav_fail")
        raise CommandError("Failed to reach Reports page — adjust nav selector.")


def set_report_filters_and_run(
    driver: webdriver.Chrome,
    report_type: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    timeout: int = 20,
):
    if report_type:
        try:
            sel = _first_visible(driver, SELECTORS["report_type_select"], timeout=timeout)
            from selenium.webdriver.support.ui import Select
            Select(sel).select_by_visible_text(report_type)
        except Exception:
            pass

    if start_date:
        _type(driver, SELECTORS["date_start"], start_date, clear=True, timeout=timeout)
    if end_date:
        _type(driver, SELECTORS["date_end"], end_date, clear=True, timeout=timeout)

    _click(driver, SELECTORS["run_report"], timeout=timeout)
    time.sleep(2)


def export_report(driver: webdriver.Chrome, timeout: int = 20):
    _click(driver, SELECTORS["export_button"], timeout=timeout)


# ---------------------- Django management command ----------------------
class Command(BaseCommand):
    help = "Automate GoPassage via Selenium: login, open Events ▸ Upcoming, scrape it, or download a report."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=os.environ.get("GOPASSAGE_EMAIL"),
                            help="Login email (or set GOPASSAGE_EMAIL)")
        parser.add_argument("--password", default=os.environ.get("GOPASSAGE_PASSWORD"),
                            help="Login password (or set GOPASSAGE_PASSWORD)")
        parser.add_argument("--base-url",
                            default=os.environ.get("GOPASSAGE_URL", "https://app.gopassage.com/users/sign_in"),
                            help="Base URL or sign-in URL for GoPassage")
        parser.add_argument("--report-type", default=os.environ.get("GOPASSAGE_REPORT", None),
                            help="Visible text of the report selector (if applicable)")
        parser.add_argument("--start-date", default=None, help="Report start date (e.g., 2025-09-01)")
        parser.add_argument("--end-date", default=None, help="Report end date (e.g., 2025-09-10)")
        parser.add_argument("--download-dir", default=os.environ.get("SELENIUM_DOWNLOAD_DIR"),
                            help="Directory to save the downloaded file")
        parser.add_argument("--timeout", type=int, default=int(os.environ.get("SELENIUM_TIMEOUT", 60)))
        parser.add_argument("--headless", action="store_true", default=False, help="Run Chrome headless")
        parser.add_argument("--no-headless", action="store_true", default=False, help="Force GUI Chrome")
        parser.add_argument("--parse-csv", action="store_true", default=False,
                            help="Parse the downloaded CSV and print row count")
        parser.add_argument("--open-upcoming", action="store_true", default=False,
                            help="After login, open Events ▸ Upcoming and exit.")
        parser.add_argument("--scrape-upcoming", action="store_true", default=False,
                            help="Scrape Events ▸ Upcoming across all pages and print a summary.")
        parser.add_argument("--output-csv", default=os.environ.get("GOPASSAGE_UPCOMING_CSV", None),
                            help="If set, save scraped Upcoming Events to this CSV path.")

    def handle(self, *args, **opts):
        email = opts["email"]
        password = opts["password"]
        base_url = opts["base_url"]
        report_type = opts["report_type"]
        start_date = opts["start_date"]
        end_date = opts["end_date"]
        timeout = int(opts["timeout"]) or 60

        # Determine headless
        headless = opts["headless"]
        if opts["no_headless"]:
            headless = False

        # Download directory
        download_dir = opts["download_dir"]
        if not download_dir:
            base_dir = getattr(settings, "BASE_DIR", None) or os.getcwd()
            download_dir = os.path.join(base_dir, "tmp", "selenium_downloads")
        os.makedirs(download_dir, exist_ok=True)

        if not email or not password:
            raise CommandError("Provide --email/--password or set GOPASSAGE_EMAIL/GOPASSAGE_PASSWORD.")

        driver = None
        downloaded_path = None
        try:
            driver = _chrome(download_dir, headless=headless)
            driver.set_page_load_timeout(timeout)

            # --- Login ---
            login_gopassage(driver, base_url, email, password, timeout=timeout)

            # --- Primary flows ---
            if opts.get("open_upcoming") or opts.get("scrape_upcoming"):
                # Admin first so the admin navbar (Events dropdown) is present
                navigate_to_admin(driver, timeout=timeout)
                navigate_to_events_upcoming(driver, timeout=timeout)

                if opts.get("open_upcoming") and not opts.get("scrape_upcoming"):
                    self.stdout.write(self.style.SUCCESS("Opened Events ▸ Upcoming successfully."))
                    return

                # Scrape all pages
                rows = scrape_upcoming_events(driver, timeout=timeout)
                self.stdout.write(f"Scraped {len(rows)} upcoming rows.")

                out_csv = opts.get("output_csv")
                if out_csv:
                    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
                    with open(out_csv, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=REQUIRED_FIELDS)
                        writer.writeheader()
                        for r in rows:
                            writer.writerow({k: r.get(k, "") for k in REQUIRED_FIELDS})
                    self.stdout.write(self.style.SUCCESS(f"Wrote CSV: {out_csv}"))
                else:
                    # Print the first few rows for quick verification
                    for r in rows[:5]:
                        preview = ", ".join(
                            f"{k}={r.get(k, '')}" for k in ("Event", "Start Time", "Tickets Purchased")
                        )
                        self.stdout.write(" - " + preview)
                return

            # Reports flow (only if filters provided)
            if report_type or start_date or end_date:
                navigate_to_admin(driver, timeout=timeout)
                navigate_to_reports(driver, timeout=timeout)
                set_report_filters_and_run(
                    driver,
                    report_type=report_type,
                    start_date=start_date,
                    end_date=end_date,
                    timeout=timeout,
                )
                # Optionally export and wait for a download if caller uses this script for reports
                if opts.get("export_report"):
                    export_report(driver, timeout=timeout)
                    downloaded_path = _wait_download(download_dir, timeout=120)
                    self.stdout.write(self.style.SUCCESS(f"Downloaded: {downloaded_path}"))

                if opts.get("parse_csv") and downloaded_path:
                    try:
                        with open(downloaded_path, newline="", encoding="utf-8") as f:
                            reader = csv.reader(f)
                            count = sum(1 for _ in reader)
                        self.stdout.write(f"Downloaded CSV rows: {count}")
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"Failed to parse CSV: {e}"))
                return

            # Default behavior: just land in Admin to prove login/navigation works
            navigate_to_admin(driver, timeout=timeout)
            self.stdout.write(self.style.SUCCESS("Login + Admin navigation successful."))

        finally:
            try:
                if driver:
                    driver.quit()
            except Exception:
                pass


# ---------------------- Lightweight unit tests (optional) ----------------------
def _test_event_id_regex():
    samples = [
        "/events/26952",
        "https://app.gopassage.com/events/12345",
        "https://app.gopassage.com/events/98765?foo=bar",
    ]
    expected = ["26952", "12345", "98765"]
    for s, e in zip(samples, expected):
        m = re.search(r"/events/(\d+)", s)
        assert m and m.group(1) == e, f"Regex failed for {s}"


def _test_signin_url_normalization():
    u = _signin_url("https://gopassage.com")
    assert "app.gopassage.com" in u and "/users/sign_in" in u
    u2 = _signin_url("gopassage.com")
    assert "app.gopassage.com" in u2


if __name__ == "__main__":
    # Run mini-tests when executing this file directly (not via Django manage)
    try:
        _test_event_id_regex()
        _test_signin_url_normalization()
        print("Mini-tests passed.")
    except AssertionError as err:
        print("Mini-tests failed:", err)
        sys.exit(1)

