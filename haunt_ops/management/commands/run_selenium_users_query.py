"""
This command uses a configuration file named ./config/selenium_config.yaml.
It supports dry-run mode to simulate updates without saving to the database.
"""
import os
from datetime import datetime
import logging
import yaml
from django.core.management.base import BaseCommand
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


logger = logging.getLogger('haunt_ops')

class Command(BaseCommand):
    """
    start command
        python manage.py run_selenium_users_query --dry-run
    or with custom config
        python manage.py run_selenium_users_query --config=config/custom_config.yaml --dry-run
    or without dry-run
        python manage.py run_selenium_users_query
    """
    
    help = 'Run Selenium query for user data from iVolunteer.'


    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Simulate actions without saving excel file.')

    def handle(self, *args, **kwargs):
        dry_run = kwargs['dry_run']

        if dry_run:
            print("Running in DRY RUN mode. No files will be downloaded.")

        # Load configuration from YAML file
        with open("config/selenium_config.yaml") as f:
            config = yaml.safe_load(f)

        #  --- browser options ---
        download_directory=config['browser_config']['download_directory']

        options = Options()
        for arg in config['browser_config']['chrome_options']:
            print(f"adding yaml parameter {arg} to driver options")
            options.add_argument(arg)

        # preferences used
        prefs = {
            "download.default_directory": download_directory,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)

        # initialize webdriver with options and preferences
        driver = webdriver.Chrome(options=options)

        # optional driver specification
        #driver = webdriver.Chrome(service=webdriver.ChromeService(executable_path='/path/to/chromedriver'), options=options)

        # --- login ---
        LOGIN_URL = config['login']['url']
        ORG_ID = config['login']['org_id']
        ADMIN_EMAIL = config['login']['admin_email']
        PASSWORD = config['login']['password']
        if PASSWORD == 'ENV':
            PASSWORD = os.environ.get('IVOLUNTEER_PASSWORD')
                
        print(f"password is {PASSWORD}")

        wait = WebDriverWait(driver, 30)

        try:
            print("🔐 Logging in...")
            driver.get(LOGIN_URL)
            wait.until(EC.presence_of_element_located((By.ID, "org_admin_login")))
            driver.find_element(By.ID, "action0").send_keys(ORG_ID)
            driver.find_element(By.ID, "action1").send_keys(ADMIN_EMAIL)
            driver.find_element(By.ID, "action2").send_keys(PASSWORD)
            driver.find_element(By.ID, "Submit").click()

            # Wait for Dashboard
            database_menu = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//div[@class='gwt-Label' and contains(text(), 'Database')]"))
            )
            database_menu.click()

            menu_items = driver.find_elements(By.XPATH, "//div[@class='gwt-Label']")
            for item in menu_items:
                print("Dashboard MENU ITEM:", item.text)

            print("📂 Navigating to Reports...")

            reports_tab = wait.until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//div[@class='gwt-TabLayoutPanelTabInner']/div[text()='Reports']"
                ))
            )
            reports_tab.click()

            print("selecting dropdowns")

            print("📑 Selecting Report type...")

            # wait for options to be refreshed
            wait = WebDriverWait(driver, 30)

            # Wait for the report dropdown to be present (replace 'GKEPJM3CLLB' if needed)
            wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, 'GKEPJM3CLLB'))
            )
            dropdowns = driver.find_elements(By.CLASS_NAME, 'GKEPJM3CLLB')

            # Safely ensure dropdown index exists
            # Wait for the Reports tab to become clickable
            report_dropdown_elem=None;
            if len(dropdowns) > 4:
                report_dropdown_elem = dropdowns[4]
            else:
                raise Exception("Report dropdown index 4 does not exist yet. Dropdowns found: " + str(len(dropdowns)))

            report_dropdown = Select(report_dropdown_elem)


            for opt in report_dropdown.options:
                print(f"Option: text={opt.text}, value={opt.get_attribute('value')}, enabled={opt.is_enabled()}")

            # Now attempt the selection
            report_dropdown.select_by_value('DbParticipantReportExcel')


            print("selecting Sort/Group")


            sg_dropdowns = driver.find_elements(By.CLASS_NAME, 'GKEPJM3CLLB')
            for idx, dropdown in enumerate(sg_dropdowns):
                print(f"Sort/Group Dropdown {idx} has options:")
                for option in Select(dropdown).options:
                    print(f"- text: {option.text}, value: {option.get_attribute('value')}, enabled: {option.is_enabled()}")
                    wait.until(
                        EC.presence_of_element_located((By.XPATH, "//option[@value='EMAIL_NAME']"))
                    )

            sort_group_dropdown = driver.find_element( By.XPATH,
                                                        "//span[text()='Sort/Group:']/following::select[1]"
            )
            Select(sort_group_dropdown).select_by_value('EMAIL_NAME')

            # get the psge size
            print("📑 Selecting page size...")
        
            # After selecting Report & Sort/Group, re-query the dropdowns becaujse the options may have changed
            wait.until(
                EC.presence_of_element_located((By.XPATH, "//option[contains(text(), 'Infinitely Wide & Tall')]"))
            )

            page_size_dropdown = driver.find_element(
                By.XPATH,
                "//span[text()='Page Size:']/following::select[1]"
            )

            # Use XPath directly for the dropdown
            page_size_dropdown = driver.find_element(
                                                    By.XPATH,
                                                    "//select[@class='GKEPJM3CLLB'][option[@value='INFINITE']]"
                                                    )
            Select(page_size_dropdown).select_by_value('INFINITE')


            print("selecting each participant")

            # XPATH finds the value with exact text
            checkbox = driver.find_element(
                                        By.XPATH,
                                        "//input[@type='checkbox' and @value='INCLUDE_EVENTS']"
            )

            if not checkbox.is_selected():
                checkbox.click()
                print("✅ 'List events for each participant' checkbox is now checked.")
            else:
                print("ℹ️ 'List events for each participant' checkbox was already checked.")

            # Select "All Database Participants"
            print("selecting all database participants")


            # XPath Finds the <label> with that exact text. Then targets the radio <input> before the label
            radio_button = driver.find_element(
                By.XPATH,
                "//label[text()='All Database Participants']/preceding-sibling::input[@type='radio']"
            )

            driver.execute_script("arguments[0].checked = true;", radio_button)
            print("✅ Radio button force-selected via JS")

            print("Run Report")

            # Wait until the button is clickable
            # locate by title 
            run_report_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@title='Run the selected report']"))
            )
            run_report_button.click()
            print("✅ 'Run Report' button clicked via text match.")

            # the POST triggers a new tab — Selenium doesn't auto-switch to new tabs/windows.
            print("📤 Submitting report form...")
            new_file_path = wait_for_new_download(download_directory, timeout=60)  # Adjust this keyword

            print(f"File downloaded to: {new_file_path}") 
        except Exception as e:
            print("❌ Error occurred:", e)
        finally:
            driver.quit()

        

    # watch for new downloaded file
    def wait_for_new_download(download_dir, timeout=30):
        # Record existing files in download dir
        existing_files = set(os.listdir(download_dir))

        print("⏳ Waiting for new file to download...")

        elapsed = 0
        while elapsed < timeout:
            current_files = set(os.listdir(download_dir))
            new_files = current_files - existing_files

        # Filter out incomplete downloads
        completed_files = [f for f in new_files if not f.endswith('.crdownload')]

        if completed_files:
            downloaded_file = completed_files[0]  # If multiple, grab the first
            print(f"✅ New file downloaded: {downloaded_file}")
            return os.path.join(download_dir, downloaded_file)

        time.sleep(1)
        elapsed += 1

        raise TimeoutError(f"❌ No new file detected in {timeout} seconds.")


        # If we reach here, the command was successful

        

