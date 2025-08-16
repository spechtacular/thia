"""
This command uses selenium to query the ivolunteer participation report page.
It uses a configuration file named ./config/selenium_config.yaml.
It supports dry-run mode to simulate updates without saving to the database.
"""

import os
import time
import traceback


import logging
import yaml

from django.core.management.base import CommandError
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from django.conf import settings
from haunt_ops.management.commands.base_utils import BaseUtilsCommand

# pylint: disable=no-member


logger = logging.getLogger("haunt_ops")


class Command(BaseUtilsCommand):
    """
    start command
        python manage.py run_selenium_participation_query
    or with custom config
        python manage.py run_selenium_participation_query --config=config/custom_config.yaml

    """

    help = "Run Selenium query for participation data from iVolunteer."

    def add_arguments(self, parser):
        parser.add_argument(
            "--config",
            type=str,
            default="config/selenium_config.yaml",
            help="Path to YAML configuration file (default: config/selenium_config.yaml)",
        )

    def handle(self, *args, **kwargs):
        config_file = kwargs.get("config", "config/selenium_config.yaml")

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            # Browser config
            download_directory = config["browser_config"]["download_directory"]
            download_dir = os.path.join(settings.BASE_DIR, download_directory)
            os.makedirs(download_dir, exist_ok=True)

            options = Options()
            for arg in config["browser_config"]["chrome_options"]:
                options.add_argument(arg)

            prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
            }
            options.add_experimental_option("prefs", prefs)
            driver = webdriver.Chrome(options=options)

            try:
                # Login
                iv_password = config["login"]["password"]
                if iv_password == "ENV":
                    iv_password = os.environ.get("IVOLUNTEER_PASSWORD")

                wait = WebDriverWait(driver, 30)
                driver.get(config["login"]["url"])
                wait.until(EC.presence_of_element_located((By.ID, "org_admin_login")))
                driver.find_element(By.ID, "action0").send_keys(
                    config["login"]["org_id"]
                )
                driver.find_element(By.ID, "action1").send_keys(
                    config["login"]["admin_email"]
                )
                driver.find_element(By.ID, "action2").send_keys(iv_password)
                driver.find_element(By.ID, "Submit").click()

                logger.info(
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
                        if option.get_attribute("value") == "DbParticipationReport":
                            if option.is_enabled():
                                report_dropdown.select_by_value("DbParticipationReport")
                                logger.info("✅ Successfully selected after wait")
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
                logger.info("Selected EMAIL sort option")

                # select report Format
                format_select = driver.find_element(
                    By.XPATH,
                    "//span[contains(text(),'Format:')]/ancestor::tr/following-sibling::tr[1]//select"
                )

                # Wait for the format select to be present
                Select(format_select).select_by_value("EXCEL")
                logger.info("Selected EXCEL format option")

                # Select Page Size (safe fallback)
                page_size_dropdown = driver.find_element(
                    By.XPATH, "//select[@class='GKEPJM3CLLB'][option[@value='LTR']]"
                )
                Select(page_size_dropdown).select_by_value("LTR")
                logger.info("Selected LTR page size")

                # Select Date Range
                date_range_select = driver.find_element(
                    By.XPATH,
                    "//span[text()='Date Range:']/ancestor::tr/following-sibling::tr[1]//select",
                )
                Select(date_range_select).select_by_visible_text("All Dates")
                logger.info("Selected All Dates option")

                # Select report options
                labels = driver.find_elements(
                    By.XPATH, "//span[contains(@class,'gwt-CheckBox')]"
                )
                for label_span in labels:
                    checkbox = label_span.find_element(By.TAG_NAME, "input")
                    label_text = label_span.text.strip()
                    if (
                        label_text
                        in ["Include emails", "Only show signed-in participants"]
                        and not checkbox.is_selected()
                    ):
                        checkbox.click()
                logger.info("Selected signed in participants option")

                # Select All Database Participants
                radio = driver.find_element(
                    By.XPATH,
                    "//label[text()="
                    "'All Database Participants']"
                    "/preceding-sibling::input[@type='radio']",
                )
                driver.execute_script("arguments[0].checked = true;", radio)
                logger.info("Selected All Database Participants option")

                # Run Report
                run_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//button[@title='Run the selected report']")
                    )
                )
                run_button.click()
                logger.info("Selected Run Report option")

                # Wait for report results to download
                downloaded_file = self.wait_for_new_download(
                    download_dir, timeout=60
                )
                logging.info("✅ ivolunteer Report File downloaded: %s", downloaded_file)
                # Convert XLS to CSV and
                # replace ivolunteer column names with postgresql column names
                self.convert_xls_to_csv(downloaded_file)
                logger.info(
                    "✅ ivolunteer participation report completed successfully."
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
