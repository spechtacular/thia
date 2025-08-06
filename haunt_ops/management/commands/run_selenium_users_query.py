"""
This command uses selenium to query the ivolunteer database user report.
It uses configuration data from a configuration file named ./config/selenium_config.yaml.
"""

import os
import time

import logging
import yaml
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from haunt_ops.management.commands.base_utils import BaseUtilsCommand

# pylint: disable=no-member

logger = logging.getLogger("haunt_ops")


class Command(BaseUtilsCommand):
    """
    start command
        python manage.py run_selenium_users_query
    or with custom config
        python manage.py run_selenium_users_query --config=config/custom_config.yaml

    """

    help = "Run Selenium query for user data from iVolunteer."

    def add_arguments(self, parser):
        parser.add_argument(
            "--config",
            type=str,
            default="config/selenium_config.yaml",
        )

    def handle(self, *args, **kwargs):
        config_file = kwargs.get("config", "config/selenium_config.yaml")

        # Load configuration from YAML file
        with open(config_file, encoding="UTF-8") as f:
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

        iv_password = config["login"]["password"]
        if iv_password == "ENV":
            iv_password = os.environ.get("IVOLUNTEER_PASSWORD")

        wait = WebDriverWait(driver, 30)

        try:
            logger.info("🔐 Logging in...")
            driver.get(config["login"]["url"])
            wait.until(EC.presence_of_element_located((By.ID, "org_admin_login")))
            driver.find_element(By.ID, "action0").send_keys(config["login"]["org_id"])
            driver.find_element(By.ID, "action1").send_keys(
                config["login"]["admin_email"]
            )
            driver.find_element(By.ID, "action2").send_keys(iv_password)
            driver.find_element(By.ID, "Submit").click()

            logger.info(
                "✅ Successfully logged in as %s ", config["login"]["admin_email"]
            )

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
                                "✅ Successfully selected DbParticipantReportExcel after wait"
                            )
                            break
                else:
                    time.sleep(1)
                    continue
                break

            else:
                raise RuntimeError("❌ 'DbParticipationReport' never became enabled.")

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
                logger.info(
                    "✅ 'List events for each participant' checkbox is now checked."
                )
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
                "//label[text()="
                "'All Database Participants']/"
                "preceding-sibling::input[@type='radio']",
            )

            driver.execute_script("arguments[0].checked = true;", radio_button)

            logger.info(
                "✅ Selected Run Report option, Radio button force-selected via JS"
            )

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

            logging.info("✅ Report File downloaded: %s", new_file_path)

            # Convert the downloaded file to CSV
            # and replace ivolunteer column names with postgresql column names
            self.convert_xls_to_csv(new_file_path)
            logger.info("✅ ivolunteer users report completed successfully.")

        except Exception as e:
            logger.error("❌ Error occurred: %s ", str(e))
        finally:
            driver.quit()
