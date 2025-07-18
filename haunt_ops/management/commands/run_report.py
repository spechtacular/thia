from playwright.sync_api import sync_playwright
import time

USERNAME = "tedspecht@gmail.com"
PASSWORD = "P&c$76$y"
LOGIN_URL = "https://ivolunteer.com/login"
REPORT_TRIGGER_TEXT = "Run Report"  # adjust if button says something else

def run_report():
    with sync_playwright() as p:
        #browser = p.chromium.launch(headless=True)
        browser = p.chromium.launch(headless=False, slow_mo=100)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        print("🔗 Opening login page...")
        page.goto(LOGIN_URL)

        print("⏳ Waiting for login...")
        page.wait_for_selector("input[type='text']", timeout=15000)
        page.fill("input[type='text']", USERNAME)
        page.fill("input[type='password']", PASSWORD)
        page.click("Login")  # Adjust if multiple buttons

        # You may need to adjust these selectors based on actual input fields
        #print("🔐 Logging in...")
        #page.fill("input[name='username']", USERNAME)
        #page.fill("input[name='password']", PASSWORD)
        #page.click("button[type='submit']")


        print("✅ Logged in, waiting for dashboard...")
        page.wait_for_timeout(5000)



        print("📊 Triggering report...")
        page.click("text=Run Report")  # Adjust to match your report button
        page.wait_for_timeout(5000)
        # Wait for report UI to load
        page.wait_for_load_state("networkidle")
        time.sleep(2)


        print("⬇️ Downloading Excel report...")
        with page.expect_download() as download_info:
            page.click("text=Download Excel")  # Change text to match download button
        download = download_info.value
        download.save_as("ivolunteer_report.xlsx")

        # Wait for report to be processed
        time.sleep(5)  # adjust this based on actual report generation time

        print("📷 Capturing screenshot of the report page...")
        page.screenshot(path="report.png")
        print("✅ Report saved to report.png")

        browser.close()

if __name__ == "__main__":
    run_report()

