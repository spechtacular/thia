"""
ivcore.py — Reusable Selenium helpers for iVolunteer

Exports:
- build_driver(cfg) -> WebDriver
- login_iv(driver, iv_url, email, password, timeout=45, log_pw_hash=False) -> bool
- click_top_tab(driver, label_text, timeout=15, logger=None) -> bool
- dump_all_frames(driver, prefix) -> None
"""

from __future__ import annotations
import os
import time
import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FFOptions

logger = logging.getLogger("haunt_ops")

ADMIN_IFRAME_ID = "ivo__admin"

# ---------- Small utilities ----------

def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def _wait_ready(driver, timeout: int = 30) -> None:
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )

def debug_dump_page(driver, prefix: str) -> None:
    base = f"/tmp/{prefix}_{_ts()}"
    try:
        driver.save_screenshot(f"{base}.png")
        with open(f"{base}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.error("Saved debug artifacts: %s.png , %s.html", base, base)
    except Exception as e:
        logger.error("Failed to save debug artifacts: %s", e)

def _switch_to_path(driver, path: List[int]) -> None:
    driver.switch_to.default_content()
    for idx in path:
        frames = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")
        if idx >= len(frames):
            raise IndexError(f"Frame index {idx} out of {len(frames)} at path {path}")
        driver.switch_to.frame(frames[idx])

def frame_tree(driver, max_depth: int = 6, _path: Optional[List[int]] = None) -> List[dict]:
    if _path is None:
        _path = []
    nodes = []
    frames = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")
    for i, fr in enumerate(frames):
        node = {
            "path": _path + [i],
            "id": fr.get_attribute("id") or "",
            "name": fr.get_attribute("name") or "",
            "src": fr.get_attribute("src") or "",
        }
        nodes.append(node)
        if len(_path) + 1 < max_depth:
            driver.switch_to.frame(fr)
            nodes += frame_tree(driver, max_depth, _path + [i])
            driver.switch_to.parent_frame()
    return nodes

def dump_all_frames(driver, prefix: str) -> None:
    base_dir = f"/tmp/{prefix}_{_ts()}"
    os.makedirs(base_dir, exist_ok=True)

    def write_text(path, text):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def recurse(path: List[int]):
        try:
            _switch_to_path(driver, path)
        except Exception as e:
            name = "default" if not path else "-".join(map(str, path))
            note = f"<!-- switch failed for path={path}: {e} -->"
            write_text(os.path.join(base_dir, f"frame_{name}.html"), note)
            return

        try:
            meta = {
                "location": driver.execute_script("return document.location.href || ''"),
                "title": driver.title or "",
            }
        except Exception:
            meta = {"location": "", "title": ""}

        html = ""
        err = None
        try:
            html = driver.page_source or ""
        except Exception as e:
            err = f"page_source error: {e}"

        name = "default" if not path else "-".join(map(str, path))
        out_path = os.path.join(base_dir, f"frame_{name}.html")
        header = f"<!-- path={path} title={meta['title']!r} url={meta['location']!r} -->\n"
        if err:
            header += f"<!-- {err} -->\n"
        if not html.strip():
            html = "<!-- EMPTY BODY OR NOT YET RENDERED -->\n<html><head></head><body></body></html>"
        write_text(out_path, header + html)
        logger.error("Saved DOM: %s", out_path)

        try:
            frames = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")
        except Exception:
            frames = []
        for i in range(len(frames)):
            recurse(path + [i])

    recurse([])
    try:
        driver.switch_to.default_content()
        png = os.path.join(base_dir, "full.png")
        driver.save_screenshot(png)
        logger.error("Saved screenshot: %s", png)
    except Exception:
        pass


def _locate_login_in_context(driver) -> Tuple[object | None, object | None, object | None, object | None]:
    """
    Best-effort:
      1) If an 'org admin' gate is present, fill it from IVOLUNTEER_ORG and advance.
      2) Locate email input, password input, submit button.
      3) Optionally locate an error banner.
    Returns: (email_el, password_el, submit_el, error_banner_el)
    """
    # --- 1) Optional org gate ---
    try:
        # short wait so we don't stall when the gate isn't used
        WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.ID, "org_admin_login")))
        org_val = (os.environ.get("IVOLUNTEER_ORG") or "").strip()
        if org_val:
            org_input = None
            try:
                org_input = driver.find_element(By.ID, "action0")
            except Exception:
                # fallback selectors if ID changes
                cand = [
                    "input#action0",
                    "input[name='action0']",
                    "input[name='org']",
                    "input[type='text']",
                ]
                for sel in cand:
                    try:
                        elems = [e for e in driver.find_elements(By.CSS_SELECTOR, sel) if e.is_displayed()]
                        if elems:
                            org_input = elems[0]
                            break
                    except Exception:
                        pass
            if org_input:
                try:
                    org_input.clear()
                except Exception:
                    pass
                org_input.send_keys(org_val)

                # try a likely continue/submit on the org gate
                try:
                    cont = None
                    # common IDs or labels we've seen
                    ids = {"action1", "continue", "submit"}
                    for e in driver.find_elements(By.XPATH, "//button|//input[@type='submit' or @type='button']"):
                        if not e.is_displayed():
                            continue
                        eid = (e.get_attribute("id") or "").lower()
                        val = (e.get_attribute("value") or "").strip().lower()
                        txt = (e.text or "").strip().lower()
                        if eid in ids or val in {"go", "continue"} or txt in {"go", "continue"}:
                            cont = e
                            break
                    if cont:
                        cont.click()
                        # wait until org gate disappears or email field shows up
                        WebDriverWait(driver, 5).until(
                            lambda d: not d.find_elements(By.ID, "org_admin_login")
                            or d.find_elements(By.CSS_SELECTOR, "input[autocomplete='username']")
                        )
                except Exception:
                    # non-fatal; we'll still try to find the login fields
                    pass
    except Exception:
        # org gate not present; continue normally
        pass

    # --- 2) Find email, password, submit ---
    email = None; pwd = None; submit = None; err = None

    for sel in ["input[autocomplete='username']", "input[type='email']", "input[type='text']"]:
        try:
            elems = [e for e in driver.find_elements(By.CSS_SELECTOR, sel) if e.is_displayed()]
            if elems:
                email = elems[0]
                break
        except Exception:
            pass

    for sel in ["input[type='password'][autocomplete='current-password']", "input[type='password']"]:
        try:
            elems = [e for e in driver.find_elements(By.CSS_SELECTOR, sel) if e.is_displayed()]
            if elems:
                pwd = elems[0]
                break
        except Exception:
            pass

    for xp in [
        "//button[normalize-space()='Login']",
        "//input[@type='submit' or @type='button'][contains(@value,'Login')]",
        "//button[contains(@class,'gwt-Button')][normalize-space()='Login']",
        "//*[@role='button' and normalize-space()='Login']",
    ]:
        try:
            elems = [e for e in driver.find_elements(By.XPATH, xp) if e.is_displayed()]
            if elems:
                submit = elems[0]
                break
        except Exception:
            pass

    # --- 3) Optional error banner ---
    try:
        err = next(
            (e for e in driver.find_elements(By.CSS_SELECTOR, "div.gwt-Label.GKEPJM3CBJB") if e.is_displayed()),
            None
        )
    except Exception:
        err = None
    if not err:
        try:
            err = next(
                (
                    e for e in driver.find_elements(
                        By.XPATH,
                        "//*[contains(translate(normalize-space(.),"
                        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'invalid')]"
                    )
                    if e.is_displayed()
                ),
                None
            )
        except Exception:
            err = None

    return email, pwd, submit, err


def _normalize_login_url(iv_url: str) -> str:
    p = urlparse(iv_url.strip())
    path = p.path
    if path.startswith("/admin/"):
        path = "/admin"
    elif path == "/":
        path = "/admin"
    return urlunparse((p.scheme, p.netloc, path, "", "", ""))

def _body_text(driver) -> str:
    try:
        return driver.find_element(By.TAG_NAME, "body").text or ""
    except Exception:
        return ""

# ---------- Login helpers ----------

def _locate_login_in_context_save(driver) -> Tuple[object | None, object | None, object | None, object | None]:
    email = None; pwd = None; submit = None; err = None
    for sel in ["input[autocomplete='username']", "input[type='email']", "input[type='text']"]:
        try:
            elems = [e for e in driver.find_elements(By.CSS_SELECTOR, sel) if e.is_displayed()]
            if elems: email = elems[0]; break
        except Exception: pass
    for sel in ["input[type='password'][autocomplete='current-password']", "input[type='password']"]:
        try:
            elems = [e for e in driver.find_elements(By.CSS_SELECTOR, sel) if e.is_displayed()]
            if elems: pwd = elems[0]; break
        except Exception: pass
    for xp in [
        "//button[normalize-space()='Login']",
        "//input[@type='submit' or @type='button'][contains(@value,'Login')]",
        "//button[contains(@class,'gwt-Button')][normalize-space()='Login']",
        "//*[@role='button' and normalize-space()='Login']",
    ]:
        try:
            elems = [e for e in driver.find_elements(By.XPATH, xp) if e.is_displayed()]
            if elems: submit = elems[0]; break
        except Exception: pass
    # optional error banner
    try:
        err = next((e for e in driver.find_elements(By.CSS_SELECTOR, "div.gwt-Label.GKEPJM3CBJB") if e.is_displayed()), None)
    except Exception:
        err = None
    if not err:
        try:
            err = next((e for e in driver.find_elements(By.XPATH, "//*[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'invalid')]") if e.is_displayed()), None)
        except Exception:
            err = None
    return email, pwd, submit, err

def _find_login_fields(driver, timeout=30):
    deadline = time.time() + timeout
    def search_here(path):
        _switch_to_path(driver, path)
        email, pwd, submit, err_el = _locate_login_in_context(driver)
        if email and pwd:
            return path, (email, pwd, submit, err_el)
        frames = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")
        for i in range(len(frames)):
            res = search_here(path + [i])
            if res: return res
        return None
    while time.time() < deadline:
        res = search_here([])
        if res: return res
        time.sleep(0.3)
    dump_all_frames(driver, prefix="iv_no_login_fields")
    raise TimeoutException("Login fields not found in page or any frame")

def _type_and_fire(driver, el, text, delay=0.05):
    driver.execute_script("arguments[0].focus();", el)
    try:
        el.clear()
    except Exception:
        driver.execute_script("arguments[0].value='';", el)
    for ch in text:
        el.send_keys(ch)
        time.sleep(delay)
    driver.execute_script("""
        arguments[0].dispatchEvent(new Event('input', {bubbles:true}));
        arguments[0].dispatchEvent(new Event('change', {bubbles:true}));
    """, el)

# ---------- Public API ----------

@dataclass
class DriverConfig:
    browser: str = "firefox"        # "firefox" or "chrome"
    headless: bool = False
    ua_firefox: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:141.0) Gecko/20100101 Firefox/141.0"
    ua_chrome: str = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/119.0.0.0 Safari/537.36")
    lang: str = "en-US, en"
    page_load_timeout: int = 60
    download_dir: str = "/tmp"

def build_driver(cfg: DriverConfig):
    if cfg.browser == "chrome":
        opts = ChromeOptions()
        if cfg.headless: opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1280,900")
        opts.add_argument("--disable-gpu"); opts.add_argument("--no-sandbox"); opts.add_argument("--disable-dev-shm-usage")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_argument(f"--lang={cfg.lang}")
        opts.add_argument(f"--user-agent={cfg.ua_chrome}")
        opts.add_experimental_option("prefs", {"download.default_directory": cfg.download_dir})
        drv = webdriver.Chrome(options=opts)
    else:
        opts = FFOptions()
        if cfg.headless: opts.add_argument("-headless")
        opts.set_preference("general.useragent.override", cfg.ua_firefox)
        opts.set_preference("intl.accept_languages", cfg.lang)
        opts.set_preference("javascript.enabled", True)
        opts.set_preference("browser.download.folderList", 2)
        opts.set_preference("browser.download.dir", cfg.download_dir)
        opts.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        drv = webdriver.Firefox(options=opts)
    drv.set_page_load_timeout(cfg.page_load_timeout)
    return drv

def login_iv(
    driver,
    iv_url: str,
    iv_admin_email: str,
    iv_password: str,
    *,
    timeout: int = 45,
    log_pw_hash: bool = False,
) -> bool:
    if log_pw_hash:
        try:
            h = hashlib.sha256(iv_password.encode("utf-8")).hexdigest()
            logger.info("pw_sha256=%s", h)
        except Exception:
            pass

    login_url = _normalize_login_url(iv_url)
    logger.info("🔐 Navigating to login: %s", login_url)
    driver.get(login_url)
    _wait_ready(driver, 30)

    try:
        path, (email_el, pass_el, submit_el, _err_el) = _find_login_fields(driver, timeout=30)
        logger.info("Found login fields in context path=%s", path if path else "default")
    except TimeoutException:
        debug_dump_page(driver, "iv_login_form_missing")
        logger.error("❌ Could not locate login fields (email/password).")
        return False

    _switch_to_path(driver, path)
    _type_and_fire(driver, email_el, iv_admin_email.strip(), delay=0.03)
    time.sleep(0.15)
    _type_and_fire(driver, pass_el, iv_password, delay=0.03)
    time.sleep(0.2)

    try: pass_el.send_keys(Keys.RETURN)
    except Exception: pass
    time.sleep(0.2)
    try:
        if submit_el:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", submit_el)
            driver.execute_script("arguments[0].click();", submit_el)
    except Exception: pass

    driver.switch_to.default_content()

    start = time.time()
    iframe_seen = False
    last_err_text = ""

    while time.time() - start < timeout:
        try:
            iframe_present = EC.presence_of_element_located((By.ID, ADMIN_IFRAME_ID))(driver)
            iframe_seen = iframe_seen or bool(iframe_present)
        except Exception:
            pass

        try:
            _switch_to_path(driver, path)
            err_nodes = [e for e in driver.find_elements(By.CSS_SELECTOR, "div.gwt-Label.GKEPJM3CBJB") if e.is_displayed()]
            if not err_nodes:
                err_nodes = [e for e in driver.find_elements(By.XPATH, "//*[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'invalid')]") if e.is_displayed()]
            if err_nodes:
                txt = (err_nodes[0].text or "").strip()
                if txt and txt != last_err_text:
                    last_err_text = txt
                    logger.error("❌ Login error banner: %s", txt)
                driver.switch_to.default_content()
                debug_dump_page(driver, "iv_login_error")
                return False
            have_email = any(e.is_displayed() for e in driver.find_elements(By.CSS_SELECTOR, "input[autocomplete='username'], input[type='email'], input[type='text']"))
            have_pwd   = any(e.is_displayed() for e in driver.find_elements(By.CSS_SELECTOR, "input[type='password']"))
            form_gone = not (have_email and have_pwd)
        except Exception:
            form_gone = False
        finally:
            driver.switch_to.default_content()

        if form_gone and iframe_seen:
            try:
                WebDriverWait(driver, 10).until(EC.frame_to_be_available_and_switch_to_it((By.ID, ADMIN_IFRAME_ID)))
                inner_text = (_body_text(driver) or "").lower()
            except Exception:
                inner_text = ""
            finally:
                driver.switch_to.default_content()
            if not any(k in inner_text for k in ["administrator login", "log in", "sign in", "password"]):
                logger.info("✅ Login success (form gone & admin iframe present). URL=%s title=%s", driver.current_url, driver.title)
                return True

        time.sleep(0.3)

    debug_dump_page(driver, "iv_login_timeout")
    logger.error("❌ Login timed out; could not confirm success.")
    return False

def click_top_tab(driver, label_text: str, timeout=15, logger=None) -> bool:
    """Click a top nav tab in the top document and verify activation/content."""
    driver.switch_to.default_content()

    wait = WebDriverWait(driver, timeout)
    td = wait.until(EC.presence_of_element_located((
        By.XPATH,
        f"//table[contains(@class,'GKEPJM3CFVB')]"
        f"//td[contains(@class,'GKEPJM3CCVB')][.//div[@class='gwt-Label' and normalize-space()='{label_text}']]"
    )))

    cls = td.get_attribute("class") or ""
    if "GKEPJM3CDVB" in cls:
        if logger: logger.info("✅ '%s' tab already active.", label_text)
        return True

    label_el = td.find_element(By.XPATH, ".//div[@class='gwt-Label']")

    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", td)
    except Exception:
        pass

    actions = ActionChains(driver)
    try:
        actions.move_to_element(td).pause(0.05).perform()
    except Exception:
        pass

    clicked = False
    for el in (td, label_el):
        if not el: continue
        try:
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable(el))
            try:
                el.click()
                clicked = True
                break
            except Exception:
                driver.execute_script("arguments[0].click();", el)
                clicked = True
                break
        except Exception:
            continue

    if not clicked:
        if logger: logger.warning("Click didn’t fire; forcing hash to #%s", label_text)
        driver.execute_script("window.location.hash = arguments[0];", label_text)
        time.sleep(0.3)

    def tab_active(d):
        try:
            el = d.find_element(By.XPATH,
                f"//table[contains(@class,'GKEPJM3CFVB')]"
                f"//td[contains(@class,'GKEPJM3CCVB') and contains(@class,'GKEPJM3CDVB')]"
                f"[.//div[@class='gwt-Label' and normalize-space()='{label_text}']]"
            )
            return el is not None
        except Exception:
            return False

    ok = False
    try:
        WebDriverWait(driver, 8).until(
            lambda d: (
                tab_active(d)
                or bool(d.find_elements(By.XPATH, "//div[@__idx]"))  # Events tiles appear when on Events
                or (d.execute_script("return window.location.hash || ''") == f"#{label_text}")
            )
        )
        ok = True
    except TimeoutException:
        ok = False

    if logger:
        if ok: logger.info("✅ '%s' tab activated.", label_text)
        else:  logger.error("❌ Failed to activate '%s' tab.", label_text)

    return ok





def _js_click(driver, el):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    driver.execute_script("arguments[0].click();", el)

def click_inner_tabpanel_tab(driver, tab_text: str, *, timeout: int = 20, logger=None) -> bool:
    """
    Click a GWT inner tab (e.g., Participants, Groups, Send Email, Reports) on the Database page.
    - Finds the visible TabLayoutPanel header row
    - Clicks the matching label or its parent tab container
    - Waits until the tab shows the 'selected' state
    """
    driver.switch_to.default_content()
    wait = WebDriverWait(driver, timeout)

    # 1) Find a visible GWT Tab header row on the page
    #    It looks like: <div class="gwt-TabLayoutPanelTabs"> ... <div class="gwt-TabLayoutPanelTab"><div><div class="gwt-Label">Reports</div></div></div> ...
    tabs_row_xpath = "//div[contains(@class,'gwt-TabLayoutPanelTabs') and not(ancestor::*[@aria-hidden='true'])]"
    tabs_row = wait.until(EC.presence_of_element_located((By.XPATH, tabs_row_xpath)))

    # 2) Find the label with the requested text under that row
    label_xpath = (
        f"{tabs_row_xpath}//div[contains(@class,'gwt-Label') and normalize-space(text())={repr(tab_text)}]"
    )
    try:
        label_el = wait.until(EC.presence_of_element_located((By.XPATH, label_xpath)))
    except Exception:
        if logger:
            logger.error("❌ Could not find inner tab label with text '%s'", tab_text)
        return False

    # 3) The clickable “tab” container is the nearest ancestor with class gwt-TabLayoutPanelTab
    tab_container = label_el.find_element(By.XPATH, "./ancestor::div[contains(@class,'gwt-TabLayoutPanelTab')]")

    # 4) Click attempts: label → container → JS click
    clicked = False
    for candidate in (label_el, tab_container):
        try:
            _js_click(driver, candidate)
            clicked = True
            break
        except Exception:
            try:
                candidate.click()
                clicked = True
                break
            except Exception:
                continue

    if not clicked:
        if logger:
            logger.error("❌ Failed to click inner tab '%s'", tab_text)
        return False

    # 5) Wait for the tab to show as selected (class 'gwt-TabLayoutPanelTab-selected')
    try:
        wait.until(lambda d: "gwt-TabLayoutPanelTab-selected" in tab_container.get_attribute("class"))
    except Exception:
        if logger:
            logger.warning("⚠️ Clicked '%s' but did not observe selected class; continuing anyway.", tab_text)

    if logger:
        logger.info("✅ Inner tab '%s' selected (or appears selected).", tab_text)
    return True


def wait_for_reports_panel(driver, *, timeout: int = 20, logger=None) -> bool:
    """
    After clicking 'Reports', wait for a hallmark of the Reports UI to be visible.
    We check a few likely anchors:
      - A top title 'Reports'
      - A label 'Report by' (the dropdown label)
      - A dropdown near 'Format' or 'Include Participants'
    """
    driver.switch_to.default_content()
    wait = WebDriverWait(driver, timeout)

    anchors = [
        # Title 'Reports'
        "//div[contains(@class,'GKEPJM3CMUB') and normalize-space(text())='Reports' and not(ancestor::*[@aria-hidden='true'])]",
        # 'Report by' label text
        "//span[contains(@class,'GKEPJM3CEWB') and contains(normalize-space(.),'Report') and not(ancestor::*[@aria-hidden='true'])]",
        # A 'Format' label near a select
        "//span[contains(@class,'GKEPJM3CEWB') and normalize-space(.)='Format:' and not(ancestor::*[@aria-hidden='true'])]",
        # 'Include Participants' label
        "//span[contains(@class,'GKEPJM3CEWB') and contains(normalize-space(.),'Include Participants') and not(ancestor::*[@aria-hidden='true'])]",
    ]
    try:
        wait.until(EC.presence_of_element_located((By.XPATH, "|".join(anchors))))
        if logger:
            logger.info("✅ Reports panel UI detected.")
        return True
    except Exception:
        if logger:
            logger.error("❌ Reports panel UI markers not found after selecting 'Reports'.")
        return False


def scrape_groups_from_filter_dropdown(driver, timeout=15, logger=None):
    """
    Reads group names from the 'Filter Group:' <select> on the Participants tab.
    Returns: list[dict] => [{ "idx": 1, "name": "Build Team" }, ...]
    """
    if logger:
        logger.info("Scraping groups from 'Filter Group' dropdown...")

    wait = WebDriverWait(driver, timeout)

    # Ensure the Participants tab is active (it usually is by default, but be explicit & robust)
    try:
        click_inner_tabpanel_tab(driver, "Participants", timeout=timeout, logger=logger)
    except Exception:
        pass
    wait_for_overlay_to_clear(driver, timeout=timeout)

    # Find the specific <select> that follows the "Filter Group:" label
    dropdown_xpath = (
        "(//span[normalize-space()='Filter Group:']"
        "/ancestor::table/following::select[contains(@class,'GKEPJM3CLLB')])[1]"
    )
    sel = wait.until(EC.element_to_be_clickable((By.XPATH, dropdown_xpath)))

    # Click/focus to trigger lazy population
    try:
        sel.click()
    except Exception:
        driver.execute_script("arguments[0].click();", sel)

    # Wait until options are actually present (lazy-loaded)
    def _options_present(drv):
        opts = sel.find_elements(By.XPATH, "./option")
        return opts if len(opts) > 0 else False

    try:
        option_elems = WebDriverWait(driver, timeout).until(_options_present)
    except Exception:
        if logger:
            logger.warning("Filter Group dropdown did not populate with any <option> elements.")
        option_elems = []

    # Collect names, skipping the "All Participants" default if present
    names = []
    seen = set()
    for opt in option_elems:
        txt = (opt.text or "").strip()
        if txt and txt != "All Participants" and txt not in seen:
            seen.add(txt)
            names.append(txt)

    groups = [{"idx": i + 1, "name": n} for i, n in enumerate(names)]
    if logger:
        logger.info("Found %d groups via dropdown", len(groups))
    return groups



def scrape_database_group_list(driver, timeout=15, logger=None):
    """
    Scrape group names from the Database > Groups tab's left list.
    Returns: list[dict] with keys: idx (1-based), name (str)
    """
    if logger:
        logger.info("Scraping group names from Groups tab...")

    wait = WebDriverWait(driver, timeout)

    # Make sure the Groups tab is selected and the header is present
    try:
        click_inner_tabpanel_tab(driver, "Groups", timeout=timeout, logger=logger)
    except Exception:
        if logger:
            logger.warning("Could not click 'Groups' tab (might already be selected).")

    # Wait for the "Groups" header text in the visible content
    groups_header_xpath = (
        "//div[contains(@class,'gwt-TabLayoutPanelContent') and not(ancestor::*[@aria-hidden='true'])]"
        "//div[contains(@class,'gwt-Label') and contains(@class,'GKEPJM3CMUB') and normalize-space(text())='Groups']"
    )
    wait.until(EC.presence_of_element_located((By.XPATH, groups_header_xpath)))

    # Find the left-side list container in the same visible content section
    container_xpath = (
        "//div[contains(@class,'gwt-TabLayoutPanelContent') and not(ancestor::*[@aria-hidden='true'])]"
        "//div[contains(@class,'GKEPJM3CCEB')]"
    )
    container = wait.until(EC.presence_of_element_located((By.XPATH, container_xpath)))

    # The groups are the divs with __idx attribute (visible text = group name)
    entry_xpath = ".//div[@__idx and normalize-space(string())]"
    elems = container.find_elements(By.XPATH, entry_xpath)

    names = []
    seen = set()
    for el in elems:
        try:
            txt = el.text.strip()
        except Exception:
            txt = ""
        if txt and txt not in seen:
            seen.add(txt)
            names.append(txt)

    if not names:
        if logger:
            logger.error("No group entries found under the Groups tab list.")
        return []

    groups = [{"idx": i + 1, "name": n} for i, n in enumerate(names)]
    if logger:
        logger.info("Found %d groups on Groups tab", len(groups))
        for g in groups[:10]:
            logger.debug("Group: %s", g)
    return groups


def click_database_group_by_name(
    driver,
    group_name: str,
    *,
    timeout: int = 15,
    logger=None
) -> bool:
    """
    Click a specific group in the left Groups list by its visible name.
    """
    driver.switch_to.default_content()
    wait = WebDriverWait(driver, timeout)
    container_xpath = "//div[contains(@class,'GKEPJM3CCEB') and not(ancestor::*[@aria-hidden='true'])]"
    wait.until(EC.presence_of_element_located((By.XPATH, container_xpath)))

    # Find entry by exact text match
    entry_xpath = (
        f"{container_xpath}//div[@__idx and normalize-space(text())="
        f"normalize-space('{group_name}')]"
    )
    try:
        el = wait.until(EC.element_to_be_clickable((By.XPATH, entry_xpath)))
        try:
            el.click()
        except Exception:
            driver.execute_script("arguments[0].click();", el)
        if logger:
            logger.info("✅ Clicked group '%s'", group_name)
        return True
    except Exception:
        if logger:
            logger.error("❌ Could not click group '%s'", group_name)
        return False

def wait_for_overlay_to_clear(driver, timeout=30):
    """
    Wait until the GWT 'glass' overlay, spinner panel, and 'Loading...' placeholder disappear.
    Safe to call after any tab click.
    """
    wait = WebDriverWait(driver, timeout)
    # Glass overlay
    try:
        wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".gwt-PopupPanelGlass")))
    except Exception:
        pass
    # Spinner panel
    try:
        wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".GKEPJM3CBUB")))
    except Exception:
        pass
    # "Loading..." placeholder
    try:
        wait.until(EC.invisibility_of_element_located((By.XPATH, "//span[normalize-space()='Loading...']")))
    except Exception:
        pass



__all__ = [
    "DriverConfig",
    "build_driver",
    "login_iv",
    "click_top_tab",
    "click_inner_tabpanel_tab",
    "dump_all_frames",
    "debug_dump_page",
    "ADMIN_IFRAME_ID",
    "scrape_database_group_list",
    "scrape_groups_from_filter_dropdown",
    "click_database_group_by_name",
    "wait_for_overlay_to_clear",
    "frame_tree",
    "_normalize_login_url",
    "_wait_ready",
    "_ts",
    "_switch_to_path",
    "_locate_login_in_context",
    "_find_login_fields",
    "_type_and_fire",
    "_body_text",
]
