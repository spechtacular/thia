# haunt_ops/passage/passage_utils.py
import re
from contextlib import contextmanager
from urllib.parse import urlparse, urljoin

from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

try:
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
    USE_WDM = True
except Exception:
    USE_WDM = False

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
    if USE_WDM:
        return Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    return Chrome(options=opts)

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

def scrape_upcoming_events_paginated(driver, timeout: int = 25, max_pages: int | None = None):
    """
    Assumes you are already on /user_account/events/upcoming_events.
    Returns a list of dicts with event_date, event_name, event_id, event_time_id,
    start_time, end_time, tickets_purchased, tickets_remaining, revenue, notes.
    """
    wait = WebDriverWait(driver, timeout)
    base = _base(driver.current_url)

    results = []
    seen = set()  # dedupe by event_time_id if we have it; else by (event_id,event_name,start_time)

    def collect_current_page():
        # Ensure at least one UpcomingEventsTable has rendered
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div[data-react-class='UpcomingEventsTable']")
        ))

        containers = driver.find_elements(By.CSS_SELECTOR, "div[data-react-class='UpcomingEventsTable']")
        for c in containers:
            # Each container has an h2 date heading right inside it
            try:
                event_date = c.find_element(By.CSS_SELECTOR, "h2").get_text() if hasattr(c, "get_text") else c.find_element(By.CSS_SELECTOR, "h2").text
                event_date = event_date.strip()
            except Exception:
                event_date = None

            # Rows inside the table
            rows = c.find_elements(By.CSS_SELECTOR, "tbody > tr")
            for tr in rows:
                tds = tr.find_elements(By.TAG_NAME, "td")
                if len(tds) < 4:
                    continue

                # Event name + numeric event_id (if link is like /events/26952)
                event_name, event_id = None, None
                try:
                    link = tds[0].find_element(By.CSS_SELECTOR, "a[href*='/events/']")
                    event_name = link.text.strip()
                    href = link.get_attribute("href") or ""
                    m = re.search(r"/events/(\d+)", href)
                    if m:
                        event_id = int(m.group(1))
                except Exception:
                    event_name = (tds[0].text or "").strip()

                # Try to capture event_time_id from the Sell/Comp dropdown anchor id="widget-trigger-<id>"
                event_time_id = None
                try:
                    w = tr.find_element(By.CSS_SELECTOR, "a[id^='widget-trigger-']")
                    m = re.search(r"widget-trigger-(\d+)", w.get_attribute("id") or "")
                    if m:
                        event_time_id = int(m.group(1))
                except Exception:
                    # If private, there may be a "Private" link with /event_times/<id>
                    try:
                        priv = tds[0].find_element(By.CSS_SELECTOR, "a[href*='/event_times/']")
                        m = re.search(r"/event_times/(\d+)", priv.get_attribute("href") or "")
                        if m:
                            event_time_id = int(m.group(1))
                    except Exception:
                        pass

                start_time = (tds[1].text or "").strip()
                end_time   = (tds[2].text or "").strip()
                purchased  = _safe_int(tds[3].text)
                remaining  = _safe_int(tds[4].text)  # "N/A" → None
                revenue    = (tds[5].text or "").strip() if len(tds) > 5 else None
                notes      = (tds[6].text or "").strip() if len(tds) > 6 else None

                # Dedupe key
                key = event_time_id if event_time_id is not None else (event_id, event_name, start_time)
                if key in seen:
                    continue
                seen.add(key)

                results.append({
                    "event_date": event_date,
                    "event_name": event_name,
                    "event_id": event_id,
                    "event_time_id": event_time_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "tickets_purchased": purchased,
                    "tickets_remaining": remaining,
                    "revenue": revenue,
                    "notes": notes,
                })

    # page 1
    collect_current_page()
    pages_done = 1

    # Walk pages using the "Next →" link href (safer than clicking)
    while True:
        if max_pages and pages_done >= max_pages:
            break

        try:
            next_a = driver.find_element(By.CSS_SELECTOR, "div.pagination a.next_page[rel='next']")
            next_href = next_a.get_attribute("href")
            if not next_href:
                break
        except Exception:
            break

        prev_url = driver.current_url
        driver.get(next_href if next_href.startswith("http") else urljoin(base, next_href))

        # Wait for URL and page number to change
        try:
            wait.until(lambda d: d.current_url != prev_url)
            wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div[data-react-class='UpcomingEventsTable']")
            ))
        except Exception:
            # If something hiccups, stop to avoid loops
            break

        pages_done += 1
        collect_current_page()

    return results


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
      {"event_date": "YYYY-MM-DD", "event_name": "…", "tickets_purchased": int, "tickets_remaining": int}
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
            "tickets_remaining": remaining,
        })
    return out
