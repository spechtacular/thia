"""
This command uses a configuration file named ./config/selenium_config.yaml.
It supports dry-run mode to simulate updates without saving to the database.
"""
import os
import time
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
        python manage.py run_selenium_participation_query --dry-run
    or with custom config
        python manage.py run_selenium_participation_query --config=config/custom_config.yaml --dry-run
    or without dry-run
        python manage.py run_selenium_participation_query
    """
    help = 'Run Selenium query for participation data from iVolunteer.'
    help = 'Query participants from iVolunteer and optionally download Excel report.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Simulate actions without saving.')

    def handle(self, *args, **kwargs):
        dry_run = kwargs['dry_run']

        try:
            with open("config/selenium_config.yaml") as f:
                config = yaml.safe_load(f)

            # Browser config
            download_directory = config['browser_config']['download_directory']
            options = Options()
            for arg in config['browser_config']['chrome_options']:
                options.add_argument(arg)

            prefs = {
                "download.default_directory": download_directory,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True
            }
            options.add_experimental_option("prefs", prefs)
            driver = webdriver.Chrome(options=options)

            try:
                # Login
                LOGIN_URL = config['login']['url']
                ORG_ID = config['login']['org_id']
                ADMIN_EMAIL = config['login']['admin_email']
                PASSWORD = config['login']['password']
                if PASSWORD == 'ENV':
                    PASSWORD = os.environ.get('IVOLUNTEER_PASSWORD')

                wait = WebDriverWait(driver, 30)
                driver.get(LOGIN_URL)
                wait.until(EC.presence_of_element_located((By.ID, "org_admin_login")))
                driver.find_element(By.ID, "action0").send_keys(ORG_ID)
                driver.find_element(By.ID, "action1").send_keys(ADMIN_EMAIL)
                driver.find_element(By.ID, "action2").send_keys(PASSWORD)
                driver.find_element(By.ID, "Submit").click()

                # Navigate
                wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@class='gwt-Label' and contains(text(), 'Database')]"))).click()
                wait.until(EC.element_to_be_clickable((By.XPATH, "//div[text()='Reports']"))).click()

                # Select Report Type
                wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'GKEPJM3CLLB')))
                dropdowns = driver.find_elements(By.CLASS_NAME, 'GKEPJM3CLLB')
                if len(dropdowns) < 5:
                    raise Exception("Expected at least 5 dropdowns, found: " + str(len(dropdowns)))

                report_dropdown_elem = dropdowns[4]
                report_dropdown = Select(report_dropdown_elem)

                # Find the option you want
                target_option = None
                for i in range(10):  # retry for up to 10 seconds
                    for option in report_dropdown.options:
                        if option.get_attribute("value") == "DbParticipationReport":
                            if option.is_enabled():
                                report_dropdown.select_by_value("DbParticipationReport")
                                print("✅ Successfully selected after wait")
                                break
                    else:
                        time.sleep(1)
                        continue
                    break
                            

                    
                else:
                    raise Exception("❌ 'DbParticipationReport' never became enabled.")

                # Sort/Group
                sort_group_dropdown = driver.find_element(By.XPATH, "//span[text()='Sort/Group:']/following::select[1]")
                Select(sort_group_dropdown).select_by_value('EMAIL')

                # Format
                format_select = driver.find_element(
                    By.XPATH,
                    "//span[contains(text(), 'Format:')]/ancestor::tr/following-sibling::tr[1]//select"
                )
                Select(format_select).select_by_value("EXCEL")

                # Page Size (safe fallback)
                page_size_dropdown = driver.find_element(
                    By.XPATH,
                    "//select[@class='GKEPJM3CLLB'][option[@value='LTR']]"
                )
                Select(page_size_dropdown).select_by_value('LTR')

                # Date Range
                date_range_select = driver.find_element(
                            By.XPATH,
                            "//span[text()='Date Range:']/ancestor::tr/following-sibling::tr[1]//select"
                )
                Select(date_range_select).select_by_visible_text("All Dates")

                
                # Check options
                labels = driver.find_elements(By.XPATH, "//span[contains(@class,'gwt-CheckBox')]")
                for label_span in labels:
                    checkbox = label_span.find_element(By.TAG_NAME, "input")
                    label_text = label_span.text.strip()
                    if label_text in ["Include emails", "Only show signed-in participants"] and not checkbox.is_selected():
                        checkbox.click()

                # All Database Participants
                radio = driver.find_element(By.XPATH, "//label[text()='All Database Participants']/preceding-sibling::input[@type='radio']")
                driver.execute_script("arguments[0].checked = true;", radio)

                # Run Report
                run_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@title='Run the selected report']"))
                )
                run_button.click()

                # Wait for download
                downloaded_file = self.wait_for_new_download(download_directory, timeout=60)
                self.stdout.write(self.style.SUCCESS(f"✅ File downloaded: {downloaded_file}"))

            except Exception as e:
                logger.error(f"❌ Error during Selenium execution: {e}")
                raise
            finally:
                driver.quit()

        except Exception as e:
            raise Exception(f"Failed during command execution: {str(e)}")

    def wait_for_new_download(self, download_dir, timeout=30):
        existing_files = set(os.listdir(download_dir))
        elapsed = 0
        while elapsed < timeout:
            current_files = set(os.listdir(download_dir))
            new_files = current_files - existing_files
            completed = [f for f in new_files if not f.endswith('.crdownload')]
            if completed:
                return os.path.join(download_dir, completed[0])
            time.sleep(1)
            elapsed += 1
        raise TimeoutError("❌ No new file detected within timeout.")
