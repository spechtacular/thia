"""
This command uses selenium to query the ivolunteer database user report.
It uses configuration data from a configuration file named ./config/selenium_config.yaml.
"""

import os
import time
import argparse
import yaml
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from haunt_ops.management.commands.base_utils import BaseUtilsCommand
from haunt_ops.utils.logging_utils import configure_rotating_logger

# pylint: disable=no-member


class Command(BaseUtilsCommand):
    """
    start command using default config file and default headless mode on and log level INFO
        python manage.py run_selenium_users_query
    or with custom config
        python manage.py run_selenium_users_query --config=config/custom_config.yaml
    or with headless off
        python manage.py run_selenium_users_query --no-headless
    or with headless on (default)
        python manage.py run_selenium_users_query --headless
    or with log level DEBUG
        python manage.py run_selenium_users_query --log DEBUG

    """

    help = "Run Selenium query for user data from iVolunteer."

    def add_arguments(self, parser):
        parser.add_argument(
            "--config",
            type=str,
            default="config/selenium_config.yaml",
        )
        parser.add_argument("--headless",action=argparse.BooleanOptionalAction,default=True)
        parser.add_argument("--log", type=str, default="INFO",
                            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                            help="Set the log level (default: INFO) ")

    def handle(self, *args, **kwargs):
        config_file = kwargs.get("config", "config/selenium_config.yaml")
        headless=kwargs.get("headless", True)
        log_level=kwargs.get("log", "INFO").upper()

                 # Get a unique log file using __file__
        logger = configure_rotating_logger(
            __file__, log_dir=settings.LOG_DIR, log_level=log_level
        )

        logger.info("querying and parsing ivolunteer user data.")
        logger.info("Log level set to: %s", log_level)
        logger.info("Headless mode: %s", headless)
        logger.debug("Log directory: %s", settings.LOG_DIR)



        # Load configuration from YAML file
        with open(config_file, encoding="UTF-8") as f:
            config = yaml.safe_load(f)

        #  --- browser options ---
        download_directory = config["browser_config"]["download_directory"]
        download_dir = os.path.join(settings.BASE_DIR, download_directory)
        os.makedirs(download_dir, exist_ok=True)

        options = Options()
        for arg in config["browser_config"]["chrome_options"]:
            options.add_argument(arg)

        if headless:
            options.add_argument("--headless=new")

        # preferences used
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        }
        options.add_experimental_option("prefs", prefs)

        # initialize webdriver with options and preferences
        # Use hardcoded paths for container environment
        options.binary_location = "/usr/bin/chromium"
        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)

        wait = WebDriverWait(driver, 30)

        try:
            logger.debug("🔐 Logging in...")
            iv_password = os.environ.get("IVOLUNTEER_PASSWORD")
            driver.get(os.environ.get("IVOLUNTEER_URL"))
            wait.until(EC.presence_of_element_located((By.ID, "org_admin_login")))
            driver.find_element(By.ID, "action0").send_keys(os.environ.get("IVOLUNTEER_ORG"))
            driver.find_element(By.ID, "action1").send_keys(
                os.environ.get("IVOLUNTEER_ADMIN_EMAIL")
            )
            driver.find_element(By.ID, "action2").send_keys(iv_password)
            driver.find_element(By.ID, "Submit").click()

            logger.debug(
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

            logger.debug("selecting dropdowns")

            logger.debug("📑 Selecting Report type...")

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
                            logger.debug(
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
                logger.debug(
                    "✅ 'List events for each participant' checkbox is now checked."
                )
            else:
                logger.debug(
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

            logger.debug(
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
            logger.debug("✅ 'Run Report' button clicked via text match.")

            # the POST triggers a new tab — Selenium doesn't auto-switch to new tabs/windows.
            logger.debug("📤 Submitting report form...")
            downloaded_file = self.wait_for_new_download(
                download_dir, timeout=60
            )  # Wait for the file to download

            logger.info("✅ ivolunteer Report File downloaded: %s", downloaded_file)

            # Convert the downloaded file to CSV
            # and replace ivolunteer column names with postgresql column names
            modified_xls_file=self.convert_xls_to_csv(downloaded_file)
            if modified_xls_file is None:
                raise CommandError(f"❌ Failed to convert XLS to CSV for {downloaded_file}")

            call_command(
                "bulk_load_users_from_ivolunteer",
                csv=modified_xls_file,
                dry_run=False,
                log="DEBUG"
            )

            logger.info(
                "✅ ivolunteer user report processed successfully."
            )

        except Exception as e:
            logger.error("❌ Error occurred: %s ", str(e))
        finally:
            driver.quit()
