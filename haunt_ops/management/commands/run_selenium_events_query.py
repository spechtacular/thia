"""
copy_events.py — hardened login for iVolunteer (Firefox by default)

Key changes:
- Default browser: Firefox (manual login succeeded with Firefox).
- Sets Firefox UA + language similar to your successful session.
- Types with small delays and fires input/change events (GWT-friendly).
- Stricter success criteria: login form must disappear AND admin iframe appear.
- Logs an optional SHA-256 of the provided password (disabled by default).

Usage:
  python manage.py copy_events \
    --iv-url "https://the-haunt.ivolunteer.com/admin" \
    --email "$IV_ADMIN_EMAIL" \
    --password "$IVOLUNTEER_PASSWORD" \
    --browser firefox \
    --dump-frames

Add --navigate-events once login is confirmed.
"""

from __future__ import annotations
import json
import logging
import os
import re
import sys
import time
import hashlib
import yaml

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

from django.core.management.base import BaseCommand, CommandError

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException

# Browser options
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FFOptions

from haunt_ops.models import Events

# pylint: disable=no-member
# pylint: disable=syntax-error
logger = logging.getLogger("haunt_ops")  # Uses logger config from settings.py

#logger = logging.getLogger(__name__)
ADMIN_IFRAME_ID = "ivo__admin"

def ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def debug_dump_page(driver, prefix: str) -> None:
    base = f"/tmp/{prefix}_{ts()}"
    try:
        driver.save_screenshot(f"{base}.png")
        with open(f"{base}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.error("Saved debug artifacts: %s.png , %s.html", base, base)
    except Exception as e:
        logger.error("Failed to save debug artifacts: %s", e)

def wait_ready(driver, timeout: int = 30) -> None:
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )

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
    base_dir = f"/tmp/{prefix}_{ts()}"
    os.makedirs(base_dir, exist_ok=True)

    def recurse(path: List[int]):
        _switch_to_path(driver, path)
        html = driver.page_source
        name = "default" if not path else "-".join(map(str, path))
        fpath = os.path.join(base_dir, f"frame_{name}.html")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(html)
        logger.error("Saved DOM: %s", fpath)
        frames = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")
        for i in range(len(frames)):
            recurse(path + [i])

    recurse([])
    driver.switch_to.default_content()
    png = os.path.join(base_dir, "full.png")
    driver.save_screenshot(png)
    logger.error("Saved screenshot: %s", png)

def _body_text(driver) -> str:
    try:
        return driver.find_element(By.TAG_NAME, "body").text or ""
    except Exception:
        return ""

def normalize_login_url(iv_url: str) -> str:
    p = urlparse(iv_url.strip())
    path = p.path
    if path.startswith("/admin/"):
        path = "/admin"
    elif path == "/":
        path = "/admin"
    return urlunparse((p.scheme, p.netloc, path, "", "", ""))

def go_to_events_exact( driver, logger, timeout=20):
    """
    Select the 'Events' tab shown as:
    <td class="GKEPJM3CCVB [GKEPJM3CDVB]"><div class="gwt-Label">Events</div></td>
    - Switches into #ivo__admin if present
    - No-ops if already active (has GKEPJM3CDVB)
    """
    # enter admin frame if it exists
    try:
        WebDriverWait(driver, 5).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, "ivo__admin"))
        )
    except Exception:
        # fine: layout might be frameless
        pass

    wait = WebDriverWait(driver, timeout)
    td = wait.until(EC.presence_of_element_located((
        By.XPATH,
        "//td[contains(@class,'GKEPJM3CCVB')][.//div[@class='gwt-Label' and normalize-space()='Events']]"
    )))

    cls = (td.get_attribute("class") or "")
    if "GKEPJM3CDVB" in cls:
        logger.info("✅ Already on Events tab.")
        driver.switch_to.default_content()
        return True

    # prefer clicking the <td>; fallback to the inner <div>
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", td)
        try:
            td.click()
        except Exception:
            driver.execute_script("arguments[0].click();", td)
        time.sleep(0.3)
    except Exception:
        # fallback: inner label
        label = td.find_element(By.XPATH, ".//div[@class='gwt-Label' and normalize-space()='Events']")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", label)
        try:
            label.click()
        except Exception:
            driver.execute_script("arguments[0].click();", label)
        time.sleep(0.3)

    # verify it activated: class should now include GKEPJM3CDVB
    try:
        td_active = WebDriverWait(driver, 10).until(EC.presence_of_element_located((
            By.XPATH,
            "//td[contains(@class,'GKEPJM3CCVB') and contains(@class,'GKEPJM3CDVB')][.//div[@class='gwt-Label' and normalize-space()='Events']]"
        )))
        logger.info("✅ Navigated to Events.")
        return True
    finally:
        driver.switch_to.default_content()


def locate_login_in_context(driver) -> Tuple[Optional[object], Optional[object], Optional[object], Optional[object]]:
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
    # error banner
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

def find_login_fields(driver, timeout=30):
    deadline = time.time() + timeout
    def search_here(path):
        _switch_to_path(driver, path)
        email, pwd, submit, err_el = locate_login_in_context(driver)
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

def type_and_fire(driver, el, text, delay=0.05):
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

    wait = WebDriverWait(driver, 30)
    login_url = normalize_login_url(iv_url)
    logger.info("🔐 Navigating to login: %s", login_url)
    driver.get(login_url)
    wait_ready(driver, 30)

    try:
        path, (email_el, pass_el, submit_el, err_el) = find_login_fields(driver, timeout=30)
        logger.info("Found login fields in context path=%s", path if path else "default")
    except TimeoutException:
        debug_dump_page(driver, "iv_login_form_missing")
        logger.error("❌ Could not locate login fields (email/password).")
        return False

    _switch_to_path(driver, path)

    # Fill with human-like typing and GWT-friendly events
    type_and_fire(driver, email_el, iv_admin_email.strip(), delay=0.03)
    time.sleep(0.15)
    type_and_fire(driver, pass_el, iv_password, delay=0.03)
    time.sleep(0.2)

    # Submit: press Enter then click Login
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

        # Re-check original login context for an error banner or persistent form
        try:
            _switch_to_path(driver, path)
            # inline error?
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
            # did the form disappear?
            have_email = any(e.is_displayed() for e in driver.find_elements(By.CSS_SELECTOR, "input[autocomplete='username'], input[type='email'], input[type='text']"))
            have_pwd   = any(e.is_displayed() for e in driver.find_elements(By.CSS_SELECTOR, "input[type='password']"))
            form_gone = not (have_email and have_pwd)
        except Exception:
            form_gone = False
        finally:
            driver.switch_to.default_content()

        if form_gone and iframe_seen:
            # sanity: peek inside iframe; ensure it isn't a login prompt
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

def score_current_context(driver) -> Tuple[int, int, int]:
    try:
        text_len = len((driver.execute_script("return document.body && document.body.innerText || ''") or ""))
    except Exception:
        text_len = 0
    try:
        links = len(driver.find_elements(By.XPATH, "//a[@href]"))
    except Exception:
        links = 0
    try:
        buttons = len(driver.find_elements(By.XPATH, "//button|//input[@type='button' or @type='submit']"))
    except Exception:
        buttons = 0
    return text_len, links, buttons

def resolve_app_context(driver, logger) -> List[int]:
    tree = frame_tree(driver, max_depth=6)
    logger.info("Frame tree: %s", json.dumps(tree, indent=2))
    candidates = [([], 0, 0, 0, 0)]
    t, l, b = score_current_context(driver); candidates[0] = ([], t, l, b, 0)
    for node in tree:
        path = node["path"]
        try:
            _switch_to_path(driver, path)
            tt, ll, bb = score_current_context(driver)
            bonus = 5 if (node.get("id") == ADMIN_IFRAME_ID) else 0
            candidates.append((path, tt, ll, bb, bonus))
        except Exception: pass
    def keyfn(c): path, t, l, b, bonus = c; return (t + bonus, l, b, len(path))
    best = max(candidates, key=keyfn)
    best_path = best[0]
    logger.info("Selected app context path=%s score=%s", best_path if best_path else "default", best[1:])
    return best_path

def list_visible_texts(driver, max_items=60):
    try:
        items = driver.execute_script("""
const out = [];
function vis(el){const s=getComputedStyle(el);return s && s.display!=='none' && s.visibility!=='hidden' && +s.opacity>0.01;}
for (const el of document.querySelectorAll('*')){
  if(!vis(el)) continue;
  const t=(el.innerText||'').trim();
  if(t && t.length<=80) out.push(t);
}
return out.slice(0, %d);
""" % max_items)
        return items or []
    except Exception:
        return []

def click_text_candidates(driver, words: List[str], logger: logging.Logger) -> int:
    clicked = 0
    for w in words:
        xp = (
            "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '"
            + w.lower() + "')]"
        )
        elems = driver.find_elements(By.XPATH, xp)
        for el in elems:
            try:
                if not el.is_displayed(): continue
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                try: el.click()
                except Exception: driver.execute_script("arguments[0].click();", el)
                clicked += 1
                logger.info("Clicked candidate containing: %s", w)
                time.sleep(0.25)
            except Exception:
                continue
    return clicked

def navigate_to_events(driver, logger: logging.Logger, total_timeout: int = 45) -> bool:
    app_path = resolve_app_context(driver, logger)
    _switch_to_path(driver, app_path)
    labels = list_visible_texts(driver, max_items=80)
    if labels: logger.info("Visible short labels in app context (sample): %s", labels[:30])
    start = time.time()
    opened = click_text_candidates(driver, ["menu", "administration", "admin", "manage", "management", "setup", "modules", "navigation"], logger)
    if opened: time.sleep(0.5)
    _ = click_text_candidates(driver, ["events", "event", "schedule", "scheduling", "calendar"], logger)
    def ctx_has_events(d) -> bool:
        try:
            t = (d.title or "") + " " + (d.execute_script("return document.body && document.body.innerText || ''") or "")
            return bool(re.search(r"\\bevent", t, flags=re.I))
        except Exception:
            return False
    while time.time() - start < total_timeout:
        if ctx_has_events(driver):
            logger.info("✅ Seems on an Events-related view. (Heuristic)")
            driver.switch_to.default_content()
            return True
        time.sleep(0.4)
    driver.switch_to.default_content(); dump_all_frames(driver, prefix="iv_after_nav_fail"); return False

@dataclass
class CmdConfig:
    iv_url: str
    iv_admin_email: str
    iv_password: str
    headless: bool
    dump_frames: bool
    navigate_events: bool
    timeout: int
    browser: str
    log_pw_hash: bool

class Command(BaseCommand):
    help = "Login to iVolunteer admin, verify success, optionally navigate to Events (Firefox default)."

    def add_arguments(self, parser):
        parser.add_argument("--iv-url", dest="iv_url", default=os.environ.get("IVOLUNTEER_URL", ""))
        parser.add_argument("--email", dest="iv_admin_email", default=os.environ.get("IVOLUNTEER_ADMIN_EMAIL", ""))
        parser.add_argument("--password", dest="iv_password", default=os.environ.get("IVOLUNTEER_PASSWORD", ""))
        parser.add_argument("--headless", action="store_true", default=False)
        parser.add_argument("--dump-frames", action="store_true", default=False)
        parser.add_argument("--navigate-events", action="store_true", default=False)
        parser.add_argument("--timeout", type=int, default=60)
        parser.add_argument("--browser", choices=["firefox","chrome"], default=os.environ.get("BROWSER","firefox"))
        parser.add_argument("--log-pw-hash", action="store_true", default=False)

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate updates without saving to database.",
        )


    def build_driver(self, cfg: CmdConfig):
        if cfg.browser == "chrome":
            opts = ChromeOptions()
            if cfg.headless: opts.add_argument("--headless=new")
            opts.add_argument("--window-size=1280,900")
            opts.add_argument("--disable-gpu"); opts.add_argument("--no-sandbox"); opts.add_argument("--disable-dev-shm-usage")
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option("useAutomationExtension", False)
            # Try to look less bot-like
            opts.add_argument("--lang=en-US,en")
            opts.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
            drv = webdriver.Chrome(options=opts)
        else:
            opts = FFOptions()
            if cfg.headless: opts.add_argument("-headless")
            # Match the server log fingerprint (Firefox on macOS)
            opts.set_preference("general.useragent.override",
                                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:141.0) Gecko/20100101 Firefox/141.0")
            opts.set_preference("intl.accept_languages", "en-US, en")
            opts.set_preference("javascript.enabled", True)
            drv = webdriver.Firefox(options=opts)
        drv.set_page_load_timeout(60)
        return drv



    def handle(self, *args, **options):
        cfg = CmdConfig(
            iv_url=options["iv_url"],
            iv_admin_email=options["iv_admin_email"],
            iv_password=options["iv_password"],
            headless=options["headless"],
            dump_frames=options["dump_frames"],
            navigate_events=options["navigate_events"],
            timeout=max(15, int(options["timeout"])),
            browser=options["browser"],
            log_pw_hash=options["log_pw_hash"],
        )
        dry_run = options["dry_run"]



        if not (cfg.iv_url and cfg.iv_admin_email and cfg.iv_password):
            missing = [k for k, v in [
                ("IVOLUNTEER_URL", cfg.iv_url), ("IVOLUNTEER_ADMIN_EMAIL", cfg.iv_admin_email), ("IVOLUNTEER_PASSWORD", cfg.iv_password)
            ] if not v]
            raise CommandError(f"❌ Missing required inputs: {', '.join(missing)}. Provide flags or set env vars.")

        logger.info("▶ Starting with email=%s pw_len=%s headless=%s browser=%s",
                    cfg.iv_admin_email, len(cfg.iv_password or ''), cfg.headless, cfg.browser)

        driver = None
        try:
            driver = self.build_driver(cfg)

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

            if cfg.navigate_events:
                success = self.navigate_to_events(driver, logger, total_timeout=cfg.timeout)
                if not success:
                    raise CommandError("Could not reach an Events view — dumps saved for analysis.")

            self.stdout.write(self.style.SUCCESS("✅ Login Completed successfully."))

            if cfg.navigate_events:
                ok = go_to_events_exact(driver, logger, timeout=cfg.timeout)
                if not ok:
                    raise CommandError("Could not activate the Events tab.")
            self.stdout.write(self.style.SUCCESS("✅ Events tab activated successfully."))

            logger.info("✅ Navigated to Events page.")
            created_count = 0
            updated_count = 0
            action = None
            total = 0

            # Locate all divs with __idx attribute (event blocks)
            event_blocks = driver.find_elements(By.XPATH, "//div[@__idx]")

            # read each event in the web page
            for block in event_blocks:
                total += 1
                event_name = block.find_element(
                    By.XPATH, ".//div[@style='font-weight: bold; font-size: 12pt;']"
                ).text
                event_date = block.find_element(
                    By.XPATH, ".//b[text()='Start:']/following-sibling::i[1]"
                ).text
                event_status = block.find_element(
                    By.XPATH, ".//b[text()='Status:']/following-sibling::i[1]"
                ).text

                logger.info(
                    "Event Name: %s, Start: %s, Status: %s",
                    event_name,
                    event_date,
                    event_status,
                )

                # Parse postgresql date format
                parsed_event_date = datetime.strptime(event_date, "%m/%d/%Y")

                # Reformat to django YYYY-MM-DD
                formatted_event_date = parsed_event_date.strftime("%Y-%m-%d")

                if dry_run:
                    event_exists = Events.objects.filter(
                        event_name=event_name
                    ).exists()
                    if event_exists:
                        updated_count += 1
                        action = "Updated"
                    else:
                        created_count += 1
                        action = "Created"
                    dry_run_action = (
                        "Would create" if not event_exists else "Would update"
                    )
                    message = f"{dry_run_action} event: {event_name}"
                    logging.info(message)

                else:
                    event, created = Events.objects.update_or_create(
                        event_date=formatted_event_date,
                        defaults={
                            "event_date": formatted_event_date,
                            "event_name": event_name.strip(),
                            "event_status": event_status.strip(),
                        },
                    )
                    if created:
                        created_count += 1
                        action = "Created"
                    else:
                        updated_count += 1
                        action = "Updated"

                    message = f"{action} event: {event.id},{formatted_event_date}"
                    logging.info(message)
            summary = f"✅Processed: {total} events, Created: {created_count}, Updated: {updated_count}"

            logger.info("%s", summary)
            logger.info("✅event import form ivolunteer complete.")
            if dry_run:
                logger.info("✅Dry-run mode enabled: no events were saved.")


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
