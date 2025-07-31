"""
 Command to run Selenium based events query on the ivolunteers Events report page
 Load or update events from ivolunteers Events report
 uses the configuration file named ./config/selenium_config.yaml
"""

import os
import logging
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

import yaml
from haunt_ops.models import Events


logger = logging.getLogger('haunt_ops')  # Uses logger config from settings.py



class Command(BaseCommand):
    """
        start command
            python manage.py run_selenium_events_query --config=config/selenium_config.yaml --dry-run
        or with custom config
            python manage.py run_selenium_events_query --config=config/custom_config.yaml --dry-run
        or without dry-run
            python manage.py run_selenium_events_query --config=config/selenium_config.yaml
    """

    help = 'Load or update events from ivolunteers Events page, uses configuration file named ./config/selenium_config.yaml'

    def add_arguments(self, parser):
        parser.add_argument(
            '--config',
            type=str,
            default='config/selenium_config.yaml',
            help='Path to YAML configuration file (default: config/selenium_config.yaml) \n With Custom config:\n python manage.py load_config_example --config=config/custom_config.yaml'
        )
        parser.add_argument('--dry-run', action='store_true', help='Simulate updates without saving to database.')



    def handle(self, *args, **kwargs):
        config_path = kwargs['config']
        dry_run = kwargs['dry_run']

        if not os.path.exists(config_path):
            logger.error("config file not found %s", config_path)
            raise CommandError(f"❌ Config file not found: {config_path}")

        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)

            if not config:
                logger.error("Config file %s is empty or malformed.", config_path)
                raise CommandError(f"❌ Config file {config_path} is empty or malformed.")

            #  --- initialize browser options ---
            download_directory=config['browser_config']['download_directory']

            options = Options()
            for arg in config['browser_config']['chrome_options']:
                logger.debug("adding  parameter %s to driver options", arg)
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

            # --- initialize login ---
            LOGIN_URL = config['login']['url']
            ORG_ID = config['login']['org_id']
            ADMIN_EMAIL = config['login']['admin_email']
            PASSWORD = config['login']['password']
            if PASSWORD == 'ENV':
               PASSWORD = os.environ.get('IVOLUNTEER_PASSWORD')
    
    
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
                events_menu = wait.until(
                    EC.visibility_of_element_located((By.XPATH, "//div[@class='gwt-Label' and contains(text(), 'Events')]"))
                )
                events_menu.click()
    
                created_count=0
                updated_count=0
                action=None 
                total=0
                events = []
    
                # Locate all divs with __idx attribute (event blocks)
                event_blocks = driver.find_elements(By.XPATH, "//div[@__idx]")

                # read each event in the web page
                for block in event_blocks:
                    total += 1 
                    event_name = block.find_element(By.XPATH, ".//div[@style='font-weight: bold; font-size: 12pt;']").text
                    event_date = block.find_element(By.XPATH, ".//b[text()='Start:']/following-sibling::i[1]").text
                    event_status = block.find_element(By.XPATH, ".//b[text()='Status:']/following-sibling::i[1]").text
    
                    logger.info("Event Name: %s, Start: %s, Status: %s", event_name, event_date, event_status)

                    # Parse postgresql date format
                    parsed_event_date = datetime.strptime(event_date, '%m/%d/%Y')

                    # Reformat to django YYYY-MM-DD
                    formatted_event_date = parsed_event_date.strftime('%Y-%m-%d')

                    if dry_run:
                        event_exists = Events.objects.filter(event_name=event_name).exists()
                        if event_exists:
                           updated_count += 1
                           action='Updated'
                        else:
                           created_count += 1
                           action='Created'
                        dry_run_action = 'Would create' if not event_exists else 'Would update'
                        message = f'{dry_run_action} event: {event_name}'
                        logging.info(message)

                    else:
                        event,created = Events.objects.update_or_create(
                           event_date=formatted_event_date,
                           defaults={    
                                'event_date':formatted_event_date,
                                'event_name':event_name.strip(),
                                'event_status':event_status.strip(),
                           }
                        )
                        if created:
                           created_count += 1
                           action = 'Created'
                        else:
                           updated_count += 1
                           action = 'Updated'

                        message = f'{action} event: {event.id},{formatted_event_date}'
                        logging.info(message)
                summary = "Processed: %d, Created: %d, Updated: %d" % (total, created_count, updated_count)
                logger.info("%s", summary)
                logger.info('event import form ivolunteer complete.')
                if dry_run:
                    logger.info("Dry-run mode enabled: no changes were saved.")


            except Exception as e:
                logger.error("Exception occurred: %s", e)
                raise CommandError(f"Exception occurred:{str(e)}") from e
            finally:
                driver.quit()
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {str(e)}")
            raise CommandError(f"❌ Failed to parse YAML config: {str(e)}")

