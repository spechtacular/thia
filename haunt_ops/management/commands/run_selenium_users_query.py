"""
This command uses selenium to query the ivolunteer database user report.
It uses configuration data from a configuration file named ./config/selenium_config.yaml.
It supports dry-run mode to simulate updates without saving to the local postgresql database.
"""
import os
import sys
import time
import shutil
from datetime import datetime
from pathlib import Path

import logging
import yaml
import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# pylint: disable=no-member

logger = logging.getLogger("haunt_ops")


class Command(BaseCommand):
    """
    start command
        python manage.py run_selenium_users_query
    or with custom config
        python manage.py run_selenium_users_query --config=config/custom_config.yaml
    or with dry-run
        python manage.py run_selenium_users_query --dry-run
    """

    help = "Run Selenium query for user data from iVolunteer."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate actions without saving excel file.",
        )

    def convert_xls_to_csv(self,input_path):
        """ 
        Converts an Excel file to a CSV file.
        This command reads an Excel file and writes its content to a file of the 
            same name with a csv extension.
        It supports specifying the sheet to convert and handles both .xlsx and .xls
        """
        sheet_name = 0

        # Convert sheet_name to int if it's digit
        if sheet_name.isdigit():
            sheet_name = int(sheet_name)

        try:
            df = pd.read_excel(input_path, sheet_name=sheet_name)
            output_path = Path(input_path).with_suffix(".csv")
            df.to_csv(output_path, index=False, encoding="utf-8")
            logger.info(
                    "✅ Successfully converted xls file: %s to csv file: %s ", 
                        input_path, output_path.name
            )
            
        except FileNotFoundError as exc:
            raise CommandError(f"❌ File not found: {input_path}") from exc
        except Exception as e:
            raise CommandError(f"❌ Error: {e}") from e



    def wait_for_new_download(self, download_dir, timeout=60, stable_secs=2):
        """
        Waits for a new file to appear in download_dir and for its size to stabilize.
        Renames it to <scriptname>-<YYYYmmdd-HHMMSS><ext> and returns the new path.
        """
        existing = set(os.listdir(download_dir))
        tmp_suffixes = (".crdownload", ".part", ".tmp")  # Chrome, Firefox, generic

        logger.info("⏳ Waiting for new file to download...")

        start = time.time()
        while time.time() - start < timeout:
            current = set(os.listdir(download_dir))
            new_files = current - existing
            if new_files:
                # Exclude temp/incomplete files
                candidates = [f for f in new_files if not f.endswith(tmp_suffixes)]
                if candidates:
                    # Most recently modified
                    paths = [os.path.join(download_dir, f) for f in candidates]
                    newest = max(paths, key=os.path.getmtime)

                    # Ensure fully written: wait until size is stable
                    last_size = -1
                    stable_start = time.time()
                    while time.time() - stable_start < stable_secs:
                        size = os.path.getsize(newest)
                        if size == last_size:
                            # ✅ Stable → rename and return
                            base_script = sys.argv[1]
                            # safe script name
                            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                            ext = os.path.splitext(newest)[1]  # keep original extension
                            new_name = f"{base_script}-{ts}{ext}"
                            new_path = os.path.join(download_dir, new_name)

                            # avoid collisions just in case
                            counter = 1
                            while os.path.exists(new_path):
                                new_name = f"{base_script}-{ts}-{counter}{ext}"
                                new_path = os.path.join(download_dir, new_name)
                                counter += 1

                            try:
                                # shutil.move works across filesystems and if file is still locked briefly
                                shutil.move(newest, new_path)
                            except Exception as e:
                                logger.warning("Rename failed (%s), returning original: %s", e, newest)
                                return newest

                            logger.info("✅ New file downloaded: %s", os.path.basename(new_path))
                            return new_path

                        last_size = size
                        time.sleep(0.5)
            time.sleep(0.5)

        raise TimeoutError(f"❌ No completed download detected within {timeout} seconds.")



    def handle(self, *args, **kwargs):
        dry_run = kwargs["dry_run"]

        if dry_run:
            logger.info("Running in DRY RUN mode. No files will be downloaded.")

        # Load configuration from YAML file
        with open("config/selenium_config.yaml", encoding="UTF-8") as f:
            config = yaml.safe_load(f)

        #  --- browser options ---
        download_directory = config["browser_config"]["download_directory"]

        options = Options()
        for arg in config["browser_config"]["chrome_options"]:
            options.add_argument(arg)

        # preferences used
        prefs = {
            "download.default_directory": download_directory,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        }
        options.add_experimental_option("prefs", prefs)

        # initialize webdriver with options and preferences
        driver = webdriver.Chrome(options=options)

        # optional driver specification
        # driver = webdriver.Chrome(service=webdriver.ChromeService(
        #   executable_path='/path/to/chromedriver'), options=options)

        # --- login ---
        LOGIN_URL = config["login"]["url"]
        ORG_ID = config["login"]["org_id"]
        ADMIN_EMAIL = config["login"]["admin_email"]
        PASSWORD = config["login"]["password"]
        if PASSWORD == "ENV":
            PASSWORD = os.environ.get("IVOLUNTEER_PASSWORD")


        wait = WebDriverWait(driver, 30)

        try:
            logger.info("🔐 Logging in...")
            driver.get(LOGIN_URL)
            wait.until(EC.presence_of_element_located((By.ID, "org_admin_login")))
            driver.find_element(By.ID, "action0").send_keys(ORG_ID)
            driver.find_element(By.ID, "action1").send_keys(ADMIN_EMAIL)
            driver.find_element(By.ID, "action2").send_keys(PASSWORD)
            driver.find_element(By.ID, "Submit").click()

            # Wait for Dashboard
            database_menu = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//div[@class='gwt-Label' and contains(text(), 'Database')]",
                    )
                )
            )
            database_menu.click()

            menu_items = driver.find_elements(By.XPATH, "//div[@class='gwt-Label']")
            for item in menu_items:
                logger.debug("Dashboard MENU ITEM: %s", item.text)

            logger.info("📂 Navigating to Reports...")

            reports_tab = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//div[@class='gwt-TabLayoutPanelTabInner']/div[text()='Reports']",
                    )
                )
            )
            reports_tab.click()

            logger.info("selecting dropdowns")

            logger.info("📑 Selecting Report type...")

            wait.until(
                EC.element_to_be_clickable((By.XPATH, "//div[text()='Reports']"))
            ).click()

            # Select Report Type
            wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "GKEPJM3CLLB"))
            )
            dropdowns = driver.find_elements(By.CLASS_NAME, "GKEPJM3CLLB")
            if len(dropdowns) < 5:
                raise ValueError(
                    "Expected at least 5 dropdowns, found: " + str(len(dropdowns))
                )

            report_dropdown_elem = dropdowns[4]

            report_dropdown = Select(report_dropdown_elem)

            # Find the option you want
            for i in range(10):  # retry for up to 10 seconds
                for option in report_dropdown.options:
                    if option.get_attribute("value") == "DbParticipantReportExcel":
                        if option.is_enabled():
                            report_dropdown.select_by_value("DbParticipantReportExcel")
                            logger.info(
                                "✅ Successfully selected DbParticipantReportExcel after wait")
                            break
                else:
                    time.sleep(1)
                    continue
                break

            else:
                raise RuntimeError(
                    "❌ 'DbParticipationReport' never became enabled."
                )

            # Sort/Group
            sort_group_dropdown = driver.find_element(
                By.XPATH, "//span[text()='Sort/Group:']/following::select[1]"
            )
            Select(sort_group_dropdown).select_by_value("EMAIL_NAME")

            logger.info("📑 Selecting page size option")

            # After selecting Report & Sort/Group, re-query the dropdowns 
            # because the options may have changed
            wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//option[contains(text(), 'Infinitely Wide & Tall')]")
                )
            )

            page_size_dropdown = driver.find_element(
                By.XPATH, "//span[text()='Page Size:']/following::select[1]"
            )

            # Use XPath directly for the dropdown
            page_size_dropdown = driver.find_element(
                By.XPATH, "//select[@class='GKEPJM3CLLB'][option[@value='INFINITE']]"
            )
            Select(page_size_dropdown).select_by_value("INFINITE")

            logger.info("Select each participant")

            # XPATH finds the value with exact text
            checkbox = driver.find_element(
                By.XPATH, "//input[@type='checkbox' and @value='INCLUDE_EVENTS']"
            )

            if not checkbox.is_selected():
                checkbox.click()
                logger.info("✅ 'List events for each participant' checkbox is now checked.")
            else:
                logger.info(
                    "ℹ️ 'List events for each participant' checkbox was already checked."
                )

            # Select "All Database Participants"
            logger.info("Selected all database participants")

            # XPath Finds the <label> with that exact text. 
            # Then targets the radio <input> before the label
            radio_button = driver.find_element(
                By.XPATH,
                "//label[text()='All Database Participants']/preceding-sibling::input[@type='radio']",
            )

            driver.execute_script("arguments[0].checked = true;", radio_button)

            logger.info("✅ Selected Run Report option, Radio button force-selected via JS")

            # Wait until the button is clickable
            # locate by title
            run_report_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[@title='Run the selected report']")
                )
            )
            run_report_button.click()
            logger.info("✅ 'Run Report' button clicked via text match.")

            # the POST triggers a new tab — Selenium doesn't auto-switch to new tabs/windows.
            logger.info("📤 Submitting report form...")
            new_file_path = self.wait_for_new_download(
                download_directory, timeout=60
            )  # Wait for the file to download

            logging.info("✅ File downloaded: %s", new_file_path)

        except Exception as e:
            logger.error("❌ Error occurred: %s ", str(e))
        finally:
            driver.quit()
            logger.info( "✅ Selenium users query completed successfully.")

