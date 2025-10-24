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
        python manage.py run_selenium_update_signin_query
    or with custom config
        python manage.py run_selenium_update_signin_query --config=config/custom_config.yaml

    """

    help = "Run Selenium query to update signin checkbox on iVolunteer."

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
        log_level = kwargs.get("log", "DEBUG").upper()
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
                iv_password = os.environ.get("IVOLUNTEER_GROUP_PASSWORD")

                wait = WebDriverWait(driver, 30)
                driver.get(os.environ.get("IVOLUNTEER_URL"))
                wait.until(EC.presence_of_element_located((By.ID, "org_admin_login")))
                driver.find_element(By.ID, "action0").send_keys(
                    os.environ.get("IVOLUNTEER_ORG")
                )
                driver.find_element(By.ID, "action1").send_keys(
                    os.environ.get("IVOLUNTEER_GROUP_ACCOUNT")
                )
                driver.find_element(By.ID, "action2").send_keys(iv_password)
                driver.find_element(By.ID, "Submit").click()

                logger.debug(
                    "✅ Successfully logged in as %s ", config["login"]["admin_email"]
                )



            except Exception as e:
                logger.error("❌ Error during Selenium login: %s", str(e))
                raise
            finally:
                driver.quit()

        except Exception as e:
            tb = traceback.format_exc()
            # Write the traceback to stderr
            self.stderr.write(self.style.ERROR(tb))
            # Then raise a CommandError with the original message
            raise CommandError(f"❌ Execution failed: {e}") from e
