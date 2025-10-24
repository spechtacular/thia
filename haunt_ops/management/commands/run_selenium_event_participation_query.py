"""
This command uses selenium to query the ivolunteer participation report page.
It uses a configuration file named ./config/selenium_config.yaml.
It supports dry-run mode to simulate updates without saving to the database.
"""

import os
import time
import traceback
import argparse
import yaml


from django.core.management.base import CommandError
from django.core.management import call_command
from django.conf import settings

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from haunt_ops.management.commands.base_utils import BaseUtilsCommand
from haunt_ops.utils.logging_utils import configure_rotating_logger


# pylint: disable=no-member


class Command(BaseUtilsCommand):
    """
    start command
        python manage.py run_selenium_event_participation_query
    or with custom config
        python manage.py run_selenium_event_participation_query --config=config/custom_config.yaml

    """

    help = "Run Selenium query for participation data from iVolunteer."

    def add_arguments(self, parser):
        parser.add_argument(
            "--config",
            type=str,
            default="config/selenium_config.yaml",
            help="Path to YAML configuration file (default: config/selenium_config.yaml)",
        )
        parser.add_argument(
            "--log",
            type=str,
            default="INFO",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            help="Set the log level (default: INFO) ",
        )

        parser.add_argument(
            "--headless",
            action=argparse.BooleanOptionalAction,
            default=True,
            help="Run browser in headless mode (default: True) ",
        )


    def handle(self, *args, **kwargs):
        config_file = kwargs.get("config", "config/selenium_config.yaml")
        log_level = kwargs.get("log", "INFO").upper()
        headless = kwargs.get("headless", True)


        # Get a unique log file using __file__
        logger = configure_rotating_logger(
            __file__, log_dir=settings.LOG_DIR, log_level=log_level
        )

        logger.debug("querying and parsing ivolunteer event participation data.")
        logger.debug("Using config file: %s", config_file)
        logger.debug("Log level set to: %s", log_level)
        logger.debug("Headless mode: %s", headless)
        logger.debug("Log directory: %s", settings.LOG_DIR)

        # Define the allowed options (only these should be selected)
        allowed_options = {
            "Include emails",
            "Only show signed-up participants",
            "Include hours per task+slot",
            "List events for each participant",
            "Include custom prompts",
            "Include custom database fields"
        }

        # Store selected checkbox labels for logging
        selected_labels = []
        unselected_labels = []

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            # Browser config
            download_directory = config["browser_config"]["download_directory"]
            download_dir = os.path.join(settings.BASE_DIR, download_directory)
            os.makedirs(download_dir, exist_ok=True)

            opts = Options()
            for arg in config["browser_config"]["chrome_options"]:
                opts.add_argument(arg)

            prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
            }

            if headless:
                opts.add_argument("--headless=new")

            opts.add_experimental_option("prefs", prefs)

            driver = webdriver.Chrome(options=opts)

            try:
                # Login
                iv_password = os.environ.get("IVOLUNTEER_PASSWORD")

                wait = WebDriverWait(driver, 30)
                driver.get(os.environ.get("IVOLUNTEER_URL"))
                wait.until(EC.presence_of_element_located((By.ID, "org_admin_login")))
                driver.find_element(By.ID, "action0").send_keys(
                    os.environ.get("IVOLUNTEER_ORG")
                )
                driver.find_element(By.ID, "action1").send_keys(
                    os.environ.get("IVOLUNTEER_ADMIN_EMAIL")
                )
                driver.find_element(By.ID, "action2").send_keys(iv_password)
                driver.find_element(By.ID, "Submit").click()

                logger.debug(
                    "✅ Successfully logged in as %s ", config["login"]["admin_email"]
                )

                # Navigate
                wait.until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//div[@class='gwt-Label' and contains(text(), 'Database')]",
                        )
                    )
                ).click()
                wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//div[text()='Reports']"))
                ).click()

                # Select Report Type
                wait.until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "GCTNM2LCAMB"))
                )

                report_dropdown_elem = driver.find_element(
                    By.XPATH,
                    "//span[contains(text(),'Report:')]/ancestor::tr/following-sibling::tr[1]//select"
                    )
                report_dropdown = Select(report_dropdown_elem)

                # Find the option you want
                for i in range(10):  # retry for up to 10 seconds
                    for option in report_dropdown.options:
                        print("Option:", option.text, "| Value:", option.get_attribute("value"))
                        if option.get_attribute("value") == "DbParticipationReport":
                            if option.is_enabled():
                                report_dropdown.select_by_value("DbParticipationReport")
                                logger.debug("✅ Successfully selected after wait")
                                break
                    else:
                        time.sleep(1)
                        continue
                    break

                else:
                    raise RuntimeError(
                        "❌ 'DbParticipationReport' never became enabled."
                    )

                # select report Sort/Group
                sort_group_dropdown = driver.find_element(
                    By.XPATH, "//span[text()='Sort/Group:']/following::select[1]"
                )
                Select(sort_group_dropdown).select_by_value("EMAIL")
                logger.debug("Selected EMAIL sort option")

                # select report Format
                format_select = driver.find_element(
                    By.XPATH,
                    "//span[contains(text(),'Format:')]/ancestor::tr/following-sibling::tr[1]//select"
                )

                # Wait for the format select to be present
                Select(format_select).select_by_value("EXCEL")
                logger.debug("Selected EXCEL format option")

                # Select Page Size (safe fallback)
                page_size_dropdown = driver.find_element(
                    By.XPATH, "//select[@class='GCTNM2LCAMB'][option[@value='LTR']]"
                )
                Select(page_size_dropdown).select_by_value("LTR")
                logger.debug("Selected LTR page size")

                # Select Date Range
                date_range_select = driver.find_element(
                    By.XPATH,
                    "//span[text()='Date Range:']/ancestor::tr/following-sibling::tr[1]//select",
                )
                Select(date_range_select).select_by_visible_text("All Dates")
                logger.debug("Selected All Dates option")

                # Select report options
                labels = driver.find_elements(
                    By.XPATH, "//span[contains(@class,'gwt-CheckBox')]"
                )
                for label_span in labels:
                    try:
                        checkbox = label_span.find_element(By.TAG_NAME, "input")
                        label_text = label_span.text.strip()

                        if label_text in allowed_options:
                            if not checkbox.is_selected():
                                checkbox.click()
                            selected_labels.append(label_text)
                        else:
                            if checkbox.is_selected():
                                checkbox.click()
                            unselected_labels.append(label_text)
                    except Exception as e:
                        logger.warning("⚠️ Error processing checkbox: %s", e)

                logger.debug("✅ Selected checkboxes: %s", ", ".join(selected_labels))
                logger.debug("❌ Unselected checkboxes: %s", ", ".join(unselected_labels))


                # Select All Database Participants
                radio = driver.find_element(
                    By.XPATH,
                    "//label[text()="
                    "'All Database Participants']"
                    "/preceding-sibling::input[@type='radio']",
                )
                driver.execute_script("arguments[0].checked = true;", radio)
                logger.debug("Selected All Database Participants option")

                # Run Report
                run_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//button[@title='Run the selected report']")
                    )
                )
                run_button.click()
                logger.debug("Selected Run Report option")

                # Wait for report results to download
                downloaded_file = self.wait_for_new_download(
                    download_dir, timeout=60
                )
                logger.debug("✅ ivolunteer Report File downloaded: %s", downloaded_file)
                # Convert XLS to CSV and
                # replace ivolunteer column names with postgresql column names
                modified_xls_file=self.convert_xls_to_csv(downloaded_file)
                if modified_xls_file is None:
                    raise CommandError(f"❌ Failed to convert XLS to CSV for {downloaded_file}")

                call_command(
                    "bulk_load_events_from_ivolunteer",
                    csv=modified_xls_file,
                    dry_run=False,
                    log="INFO"
                )

                logger.info(
                    "✅ ivolunteer participation report processed successfully."
                )

            except Exception as e:
                logger.error("❌ Error during Selenium execution: %s", str(e))
                raise
            finally:
                driver.quit()

        except Exception as e:
            tb = traceback.format_exc()
            # Write the traceback to stderr
            self.stderr.write(self.style.ERROR(tb))
            # Then raise a CommandError with the original message
            raise CommandError(f"❌ Execution failed: {e}") from e
