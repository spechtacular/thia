# haunt_ops/passage/passage_utils.py
import re
import os
from contextlib import contextmanager
import json
import time as _pytime
from urllib.parse import urlparse, urljoin
from typing import Any, Dict, List
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import Chrome, ChromeOptions

from selenium.webdriver.chrome.service import Service

DEFAULT_TIMEOUT = 20

def build_driver(headless: bool = True) -> Chrome:
    opts = ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--blink-settings=imagesEnabled=false")

    chrome_binary = os.getenv("CHROME_BIN", "/usr/bin/chromium")
    chromedriver_binary = os.getenv("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")

    opts.binary_location = chrome_binary
    service = Service(executable_path=chromedriver_binary)

    return Chrome(service=service, options=opts)

@contextmanager
def chrome_session(headless: bool = True):
    d = build_driver(headless=headless)
    try:
        yield d
    finally:
        d.quit()

def login_passage(driver, username: str, password: str, login_url: str, timeout: int = 20):
    driver.get(login_url)
    wait = WebDriverWait(driver, timeout)

    # Optional: if you ever land on "/", click the Login link
    try:
        if driver.current_url.rstrip("/").endswith("app.gopassage.com"):
            login_link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href='/users/sign_in']")))
            login_link.click()
    except Exception:
        pass

    # Wait for the login form you pasted
    email = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#user_email[name='user[email]']")))
    pwd   = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#user_password[name='user[password]']")))

    email.clear(); email.send_keys(username)
    pwd.clear();   pwd.send_keys(password)

    # Try the exact submit input first
    clicked = False
    for sel in [
        "form#new_user input[type='submit'][value='Sign In']",
        "input[type='submit'][value='Sign In']",
        "form#new_user input[type='submit']",
        "input[type='submit']",
        ".btn.btn-primary[type='submit']",
    ]:
        try:
            submit = driver.find_element(By.CSS_SELECTOR, sel)
            if submit.is_displayed() and submit.is_enabled():
                submit.click()
                clicked = True
                break
        except Exception:
            continue

    if not clicked:
        # Fallback: submit via Enter key
        pwd.send_keys(Keys.RETURN)

    # Handle cookie bar if it pops up and blocks the page (rare, but cheap to try)
    try:
        cookie_accept = driver.find_element(By.CSS_SELECTOR, "#cookies-bar a.btn.btn-primary.btn-clear")
        if cookie_accept.is_displayed():
            cookie_accept.click()
    except Exception:
        pass

    # The form is AJAX (`data-remote="true"`); wait for a post-login signal
    # 1) URL changes away from /users/sign_in, or
    # 2) we see a sign-out link, or
    # 3) we land in dashboard/reports area
    try:
        wait.until(EC.any_of(
            EC.url_changes(login_url),
            EC.url_contains("/event_management"),
            EC.url_contains("/dashboard"),
            EC.url_contains("/reports"),
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/sign_out']"))
        ))
    except Exception:
        # If still on the login page, check if an error banner appeared
        try:
            err = driver.find_element(By.CSS_SELECTOR, "#login-error")
            if err.is_displayed():
                raise RuntimeError(f"Login failed: {err.text.strip() or 'Unknown error'}")
        except Exception:
            pass
        # Dump artifacts for inspection
        try:
            html_path = "/tmp/passage_login_fail.html"
            png_path = "/tmp/passage_login_fail.png"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            driver.save_screenshot(png_path)
            cur = driver.current_url
        except Exception:
            html_path = png_path = cur = "<unavailable>"
        raise RuntimeError(f"Login did not reach a post-login state (URL={cur}). "
                           f"Saved DOM: {html_path} Screenshot: {png_path}")


def _base(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"

def go_to_events_upcoming(driver, timeout: int = 25):
    """
    Go straight to /user_account/events/upcoming_events.
    If that fails, try /user_account/events then click 'Upcoming'.
    As a last resort, open the Admin dropdown and try again.
    """
    wait = WebDriverWait(driver, timeout)

    # Ensure we actually have a logged-in shell: look for Logout somewhere
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href='/users/sign_out']")))
    except Exception:
        # we are not logged in; let the direct GETs below reveal that by redirecting to sign in
        pass

    base = _base(driver.current_url)

    # Try direct: Upcoming
    for path in ("/user_account/events/upcoming_events", "/user_account/events"):
        try:
            driver.get(urljoin(base, path))
            wait.until(EC.any_of(
                EC.url_contains(path),
                EC.presence_of_element_located((By.CSS_SELECTOR, "nav.navbar")),
            ))
            # If we're on /events, click the Upcoming link in the admin navbar (if present)
            if path.endswith("/events") and "/user_account/events/upcoming_events" not in driver.current_url:
                try:
                    # Navbar might be collapsed → expand hamburger
                    try:
                        burger = driver.find_element(By.CSS_SELECTOR, "button.navbar-toggle[data-target='#navbar-collapse-1']")
                        if burger.is_displayed():
                            burger.click()
                            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#navbar-collapse-1.in, #navbar-collapse-1")))
                    except Exception:
                        pass

                    # Open Events dropdown and click Upcoming
                    events_toggle = wait.until(EC.element_to_be_clickable((
                        By.XPATH, "//ul[contains(@class,'navbar-left')]//li[contains(@class,'dropdown')]"
                                  "/a[contains(@class,'dropdown-toggle') and contains(normalize-space(),'Events')]"
                    )))
                    try:
                        events_toggle.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", events_toggle)

                    # Force-open class if Bootstrap didn’t do it
                    try:
                        li = events_toggle.find_element(By.XPATH, "./ancestor::li[contains(@class,'dropdown')]")
                        driver.execute_script("arguments[0].classList.add('open');", li)
                    except Exception:
                        pass

                    upcoming = wait.until(EC.element_to_be_clickable((
                        By.CSS_SELECTOR, "ul.dropdown-menu a[href='/user_account/events/upcoming_events'], "
                                         "ul.dropdown-menu a[href='https://app.gopassage.com/user_account/events/upcoming_events']"
                    )))
                    try:
                        upcoming.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", upcoming)

                    wait.until(EC.url_contains("/user_account/events/upcoming_events"))
                except Exception:
                    # If the navbar click fails, just direct-nav again
                    driver.get(urljoin(base, "/user_account/events/upcoming_events"))
                    wait.until(EC.url_contains("/user_account/events/upcoming_events"))

            # Final settle: expect a table/grid on Upcoming page
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table, .table, [role='table']")))
            except Exception:
                pass
            return
        except Exception:
            continue

    # Last resort: use the Account dropdown once, then retry direct
    try:
        # Expand hamburger if needed
        try:
            burger = driver.find_element(By.CSS_SELECTOR, "button.navbar-toggle[data-target='#navbar-collapse-1']")
            if burger.is_displayed():
                burger.click()
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#navbar-collapse-1.in, #navbar-collapse-1")))
        except Exception:
            pass

        # Open Account dropdown and click Admin
        account_toggle = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR, "ul.navbar-nav.navbar-right li.dropdown > a.dropdown-toggle"
        )))
        try:
            account_toggle.click()
        except Exception:
            driver.execute_script("arguments[0].click();", account_toggle)

        # Ensure menu is open
        try:
            li = account_toggle.find_element(By.XPATH, "./ancestor::li[contains(@class,'dropdown')]")
            driver.execute_script("arguments[0].classList.add('open');", li)
        except Exception:
            pass

        admin_link = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR, "ul.dropdown-menu a[href='/user_account/events']"
        )))
        try:
            admin_link.click()
        except Exception:
            driver.execute_script("arguments[0].click();", admin_link)

        wait.until(EC.url_contains("/user_account/events"))
        # Then go to Upcoming
        driver.get(urljoin(base, "/user_account/events/upcoming_events"))
        wait.until(EC.url_contains("/user_account/events/upcoming_events"))
        return
    except Exception:
        # Dump artifacts so we can see what changed
        try:
            with open("/tmp/passage_admin_nav_fail.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            driver.save_screenshot("/tmp/passage_admin_nav_fail.png")
        except Exception:
            pass
        raise


def _safe_int(text):
    if not text:
        return None
    m = re.search(r"-?\d+", text)
    return int(m.group(0)) if m else None

def scrape_upcoming_events_paginated(
    driver, timeout: int = 30, max_pages: int = 20
) -> List[Dict[str, Any]]:
    """
    Scrape Upcoming Events tables across pages.

    - Reads counts from the DOM (not react props).
    - Finds columns by header name (robust to column order/visibility).
    - For 'Tickets Purchased', waits a bit for React hydration and prefers non-zero.
    """
    wait = WebDriverWait(driver, timeout)
    rows: List[Dict[str, Any]] = []
    page_num = 1

    def idx_of(headers: list[str], label: str) -> int | None:
        target = label.lower()
        for i, h in enumerate(headers):
            hh = (h or "").strip().lower()
            if hh == target or target in hh:
                return i
        return None

    def wait_for_purchased(td, per_cell_timeout: float = 8.0, stable_for: float = 0.5) -> str:
        """
        Poll the cell for up to per_cell_timeout seconds.
        - Prefer a non-zero integer if it appears.
        - Require 'stable_for' seconds of no change before accepting.
        - Fall back to whatever's there at timeout (possibly '0').
        """
        deadline = _pytime.time() + per_cell_timeout
        last_txt = (td.text or "").strip()
        last_change = _pytime.time()
        best_nonzero = None

        def is_inty(s: str) -> bool:
            return bool(re.fullmatch(r"[\d,]+", s))

        # scroll into view (some tables hydrate on visibility)
        try:
            td.parent.execute_script("arguments[0].scrollIntoView({block:'center'});", td)
        except Exception:
            pass

        while _pytime.time() < deadline:
            cur = (td.text or "").strip()
            if cur != last_txt:
                last_txt = cur
                last_change = _pytime.time()
                # track the first non-zero we see
                if is_inty(cur) and cur.replace(",", "") != "0" and best_nonzero is None:
                    best_nonzero = cur

            # If we’ve had a non-zero and it’s been stable for a moment, take it
            if best_nonzero and (_pytime.time() - last_change) >= stable_for:
                return best_nonzero

            # If we’ve seen *any* int and it’s stable for a bit, accept it (could be legit 0)
            if is_inty(cur) and (_pytime.time() - last_change) >= stable_for:
                # prefer returning a remembered non-zero if exists; else return cur
                return best_nonzero or cur

            _pytime.sleep(0.1)

        # Timeout: prefer the best non-zero we saw; else return whatever’s there
        return best_nonzero or last_txt

    while page_num <= max_pages:
        wait.until(EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, 'div[data-react-class="UpcomingEventsTable"]')
        ))
        containers = driver.find_elements(By.CSS_SELECTOR, 'div[data-react-class="UpcomingEventsTable"]')
        if not containers:
            break

        for container in containers:
            # Date label (e.g., "Friday, September 26, 2025")
            try:
                date_label = container.find_element(By.CSS_SELECTOR, "h2").text.strip()
            except Exception:
                date_label = None

            # Time zone label via react props
            tz_label = None
            try:
                props = container.get_attribute("data-react-props")
                if props:
                    tz_label = json.loads(props).get("timeZone")
            except Exception:
                pass

            table = container.find_element(By.CSS_SELECTOR, "table")
            header_cells = table.find_elements(By.CSS_SELECTOR, "thead tr td, thead tr th")
            headers = [hc.text.strip() for hc in header_cells]

            i_event = idx_of(headers, "Event") or 0
            i_start = idx_of(headers, "Start Time") or 1
            i_end   = idx_of(headers, "End Time") or 2
            i_pur   = idx_of(headers, "Tickets Purchased")

            for tr in table.find_elements(By.CSS_SELECTOR, "tbody tr"):
                tds = tr.find_elements(By.CSS_SELECTOR, "td")
                if len(tds) < 3:
                    continue

                event_name = (tds[i_event].text or "").strip() if i_event is not None else ""
                start_text = (tds[i_start].text or "").strip() if i_start is not None else ""
                end_text   = (tds[i_end].text or "").strip()   if i_end   is not None else ""

                purchased_text = ""
                if i_pur is not None and i_pur < len(tds):
                    # IMPORTANT: wait for hydration, prefer non-zero
                    purchased_text = wait_for_purchased(tds[i_pur])

                # Extract event_time_id from Sell/Comp widget button id
                event_time_id = None
                try:
                    widget = tr.find_element(By.CSS_SELECTOR, 'a[id^="widget-trigger-"]')
                    m = re.search(r"widget-trigger-(\d+)", widget.get_attribute("id") or "")
                    if m:
                        event_time_id = int(m.group(1))
                except Exception:
                    pass

                # If the purchased cell is still empty, skip rather than zeroing
                if purchased_text == "":
                    continue

                rows.append({
                    "event_time_id": event_time_id,
                    "event_name": event_name,
                    "event_date": date_label,
                    "start_time": start_text,
                    "end_time": end_text,
                    "tickets_purchased": purchased_text,
                    "time_zone": tz_label,
                })

        # Next page
        next_links = driver.find_elements(By.CSS_SELECTOR, 'a.next_page[rel="next"]')
        if next_links:
            old = containers[0]
            next_links[0].click()
            wait.until(EC.staleness_of(old))
            page_num += 1
        else:
            break

    return rows




def click_admin_from_account(driver, timeout: int = 20):
    wait = WebDriverWait(driver, timeout)

    # Wait until we’re definitely logged in (Logout link present)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href='/users/sign_out']")))

    # If the navbar is collapsed (mobile), expand it
    try:
        burger = driver.find_element(By.CSS_SELECTOR, "button.navbar-toggle[data-target='#navbar-collapse-1']")
        if burger.is_displayed():
            burger.click()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#navbar-collapse-1.in, #navbar-collapse-1.collapsing, #navbar-collapse-1")))
    except Exception:
        pass  # not collapsed / not present

    # Try to click Admin from the dropdown, robustly
    try:
        # Find the Account toggle (don’t depend on exact text)
        toggle = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR, "ul.nav.navbar-nav li.dropdown > a.dropdown-toggle"
        )))
        try:
            toggle.click()
        except Exception:
            driver.execute_script("arguments[0].click();", toggle)

        # Make sure the menu is open
        try:
            li = toggle.find_element(By.XPATH, "./ancestor::li[contains(@class,'dropdown')]")
            driver.execute_script("arguments[0].classList.add('open');", li)
        except Exception:
            pass

        # Click the Admin link
        admin_locator = (By.CSS_SELECTOR, "ul.dropdown-menu a[href='/user_account/events']")
        admin = wait.until(EC.element_to_be_clickable(admin_locator))
        try:
            admin.click()
        except Exception:
            driver.execute_script("arguments[0].click();", admin)

        wait.until(EC.url_contains("/user_account/events"))
        return
    except Exception:
        # Direct navigation fallback
        base = _base_of(driver.current_url)
        driver.get(urljoin(base, "/user_account/events"))
        wait.until(EC.url_contains("/user_account/events"))
        return



def open_admin_via_account_menu(driver, timeout: int = 15):
    wait = WebDriverWait(driver, timeout)

    # 0) If a cookie bar can cover the navbar, click Accept first (if present)
    try:
        cookie_accept = driver.find_element(By.CSS_SELECTOR, "#cookies-bar a.btn.btn-primary.btn-clear")
        if cookie_accept.is_displayed():
            cookie_accept.click()
    except Exception:
        pass

    # 1) Find the Account dropdown toggle
    toggle = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "ul.nav.navbar-nav li.dropdown > a.dropdown-toggle")
    ))

    # 2) Ensure the dropdown menu is open (click or hover fallback)
    def menu_is_open():
        try:
            menu = driver.find_element(By.CSS_SELECTOR, "ul.nav.navbar-nav li.dropdown.open > ul.dropdown-menu")
            return menu.is_displayed()
        except Exception:
            return False

    try:
        toggle.click()
    except Exception:
        # fallback to JS click
        driver.execute_script("arguments[0].click();", toggle)

    if not menu_is_open():
        try:
            ActionChains(driver).move_to_element(toggle).perform()
        except Exception:
            pass
        # if still not open, click again
        if not menu_is_open():
            try:
                toggle.click()
            except Exception:
                driver.execute_script("arguments[0].click();", toggle)

    # 3) Click the Admin link inside the dropdown
    admin_link = None
    for locator in [
        (By.CSS_SELECTOR, "ul.nav.navbar-nav li.dropdown.open ul.dropdown-menu a[href='/user_account/events']"),
        (By.XPATH, "//ul[contains(@class,'dropdown-menu')]//a[normalize-space()='Admin']"),
        (By.XPATH, "//a[contains(@href,'/user_account/events')]"),
    ]:
        try:
            admin_link = wait.until(EC.element_to_be_clickable(locator))
            if admin_link.is_displayed():
                break
        except Exception:
            continue

    if not admin_link:
        # Dump artifacts for quick inspection
        try:
            html_path = "/tmp/passage_admin_menu_missing.html"
            png_path = "/tmp/passage_admin_menu_missing.png"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            driver.save_screenshot(png_path)
        except Exception:
            html_path = png_path = "<unavailable>"
        raise RuntimeError(f"Admin link not found/clickable. Saved DOM: {html_path} Screenshot: {png_path}")

    try:
        admin_link.click()
    except Exception:
        driver.execute_script("arguments[0].click();", admin_link)

    # 4) Wait for navigation to the Admin area
    wait.until(EC.any_of(
        EC.url_contains("/user_account/events"),
        EC.url_contains("/event_management"),
        EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, "Reports")),
    ))

def _base_url(u: str) -> str:
    p = urlparse(u)
    return f"{p.scheme}://{p.netloc}"

def navigate_to_ticket_sales_report(driver, timeout: int = 25):
    """
    Be robust:
      1) Click a 'Reports' nav if present (left/top).
      2) Click a 'Ticket Sales' (or similar) tile/link.
      3) Fallback: hit likely report URLs directly.
    """
    wait = WebDriverWait(driver, timeout)

    # 0) If you’re still on the public shell, try going straight to user admin reports later.
    cur = driver.current_url

    # 1) Try to click "Reports" somewhere in admin
    reports_locators = [
        (By.PARTIAL_LINK_TEXT, "Reports"),
        (By.XPATH, "//a[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'reports')]"),
        (By.CSS_SELECTOR, "a[href*='/reports']"),
        # sometimes a side menu item
        (By.XPATH, "//nav//a[contains(@href,'/reports')]"),
    ]
    clicked_reports = False
    for by, sel in reports_locators:
        try:
            el = wait.until(EC.element_to_be_clickable((by, sel)))
            if el.is_displayed():
                el.click()
                clicked_reports = True
                break
        except Exception:
            continue

    # If we didn't click it, we might already be on a reports overview; continue anyway.
    # Wait until we look like we're on a reports page (best-effort)
    try:
        wait.until(EC.any_of(
            EC.url_contains("/reports"),
            EC.presence_of_element_located((By.XPATH, "//h1[contains(.,'Report') or contains(.,'Reports')]")),
            EC.presence_of_element_located((By.XPATH, "//a[contains(.,'Ticket') and contains(.,'Sales')]")),
        ))
    except Exception:
        pass

    # 2) Click the "Ticket Sales" entry (be generous with selectors)
    sales_locators = [
        # exact link you might have
        (By.PARTIAL_LINK_TEXT, "Ticket Sales"),
        (By.XPATH, "//a[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'ticket sales')]"),
        # cards/tiles with titles
        (By.XPATH, "//*[self::a or self::button or self::div]\
                    [contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'ticket') \
                     and contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sale')]"),
        # href patterns
        (By.CSS_SELECTOR, "a[href*='ticket'][href*='sale']"),
        (By.CSS_SELECTOR, "a[href*='tickets'][href*='report']"),
        (By.CSS_SELECTOR, "a[href*='/reports'][href*='ticket']"),
    ]

    for by, sel in sales_locators:
        try:
            el = wait.until(EC.element_to_be_clickable((by, sel)))
            if el.is_displayed():
                try:
                    el.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", el)
                # after click, wait for a table-ish page
                wait.until(EC.any_of(
                    EC.url_contains("ticket"),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table, .report-table, [role='table']")),
                    EC.presence_of_element_located((By.XPATH, "//th|//td"))
                ))
                break
        except Exception:
            continue
    else:
        # 3) Fallback: try direct URLs that Passage commonly uses
        base = _base_url(driver.current_url or cur)
        candidates = [
            "/event_management/reports/ticket_sales",
            "/event_management/reports/tickets",
            "/user_account/reports/ticket_sales",
            "/user_account/reports/tickets",
            "/reports/ticket_sales",
            "/reports/tickets",
        ]
        hit = False
        for path in candidates:
            try:
                driver.get(urljoin(base, path))
                wait.until(EC.any_of(
                    EC.url_contains("ticket"),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table, .report-table, [role='table']")),
                    EC.presence_of_element_located((By.XPATH, "//th|//td"))
                ))
                hit = True
                break
            except Exception:
                continue

        if not hit:
            # dump artifacts
            try:
                html_path = "/tmp/passage_reports_nav_fail.html"
                png_path = "/tmp/passage_reports_nav_fail.png"
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                driver.save_screenshot(png_path)
                current = driver.current_url
            except Exception:
                html_path = png_path = current = "<unavailable>"
            raise RuntimeError(
                f"Couldn't reach Ticket Sales. URL={current}. "
                f"Saved DOM: {html_path} Screenshot: {png_path}"
            )

    # 4) Final settle: ensure the table exists before parse
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table, .report-table, [role='table']")))

def parse_ticket_sales_table(driver):
    """
    Return list of dicts:
      {"event_date": "YYYY-MM-DD", "event_name": "…", "tickets_purchased": int}
    Adjust header matching if Passage labels differ.
    """
    table = driver.find_element(By.CSS_SELECTOR, "table, .report-table, [role='table']")
    header_cells = table.find_elements(By.CSS_SELECTOR, "thead th, thead td")
    if not header_cells:
        header_cells = table.find_elements(By.CSS_SELECTOR, "tr:first-child th, tr:first-child td")
    headers = [h.text.strip().lower() for h in header_cells]

    def col(*aliases):
        for a in aliases:
            if a in headers:
                return headers.index(a)
        return None

    i_date = col("date", "event date", "sale date")
    i_name = col("event", "event name", "name")
    i_purc = col("tickets purchased", "tickets sold", "sold", "qty")
    i_rem = col("tickets remaining", "remaining", "unsold")

    if i_date is None or i_name is None or i_purc is None:
        raise RuntimeError(f"Could not map required columns. Headers: {headers}")

    rows = table.find_elements(By.CSS_SELECTOR, "tbody tr") or table.find_elements(By.CSS_SELECTOR, "tr")[1:]
    out = []
    from datetime import datetime
    for r in rows:
        tds = r.find_elements(By.CSS_SELECTOR, "td")
        if not tds:
            continue

        raw_date = tds[i_date].text.strip()
        raw_name = tds[i_name].text.strip()
        raw_purc = tds[i_purc].text.strip().replace(",", "")
        raw_rem = tds[i_rem].text.strip().replace(",", "") if i_rem is not None else "0"

        # Parse date to YYYY-MM-DD
        parsed = None
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y"):
            try:
                parsed = datetime.strptime(raw_date, fmt).date()
                break
            except ValueError:
                pass
        if not parsed:
            try:
                from dateutil.parser import parse as dtparse
                parsed = dtparse(raw_date).date()
            except Exception:
                continue

        try:
            purchased = int(raw_purc) if raw_purc else 0
        except Exception:
            purchased = 0
        try:
            remaining = int(raw_rem) if raw_rem else 0
        except Exception:
            remaining = 0

        out.append({
            "event_date": parsed.isoformat(),
            "event_name": raw_name,
            "tickets_purchased": purchased,
        })
    return out
