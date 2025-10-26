#!/usr/bin/env python3
"""
website_monitor.py
Checks a list of websites, and emails admins if any are down.
Designed for cron use.
"""

import smtplib
import requests
from email.mime.text import MIMEText
from datetime import datetime

# --- Configuration ---
WEBSITES = [
    "https://thehauntinatascadero.com",
    "https://ivolunteer.com",
    "https://gopassage.com",
]

ADMINS = [
    "tedspecht@gmail.com",
    "spechtacular@yahoo.com",
]

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "tedspecht@gmail.com"
SMTP_PASS = "your_app_password_here"  # use an App Password, not your real Gmail password

TIMEOUT = 10  # seconds
LOG_FILE = "/home/zack/thia/logs/website_monitor.log"

# --- Check function ---
def check_site(url):
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code == 200:
            return True
        else:
            return False
    except Exception:
        return False

# --- Main ---
def main():
    down_sites = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for site in WEBSITES:
        ok = check_site(site)
        with open(LOG_FILE, "a") as log:
            log.write(f"[{timestamp}] {site} -> {'UP' if ok else 'DOWN'}\n")
        if not ok:
            down_sites.append(site)

    if down_sites:
        subject = f"[ALERT] {len(down_sites)} site(s) down"
        body = f"The following sites are unreachable as of {timestamp}:\n\n"
        body += "\n".join(down_sites)

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = ", ".join(ADMINS)

        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, ADMINS, msg.as_string())
        except Exception as e:
            with open(LOG_FILE, "a") as log:
                log.write(f"[{timestamp}] ERROR sending email: {e}\n")

if __name__ == "__main__":
    main()

