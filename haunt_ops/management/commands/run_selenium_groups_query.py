from django.core.management.base import BaseCommand, CommandError
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from haunt_ops.models import Groups


import yaml
import os
import logging
import time # sleep for debugging

logger = logging.getLogger('haunt_ops')  # Uses logger config from settings.py

class Command(BaseCommand):

    help = 'Load or update groups from ivolunteers Groups page, uses configuration file named ./config/selenium_config.yaml'

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
            logger.error(f"config file not found {config_path}")
            raise CommandError(f"❌ Config file not found: {config_path}")

        try:
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)

            if not config:
                logger.error(f"Config file {config_path} is empty or malformed.")
                raise CommandError(f"❌ Config file {config_path} is empty or malformed.")

            #  --- initialize browser options ---
            download_directory=config['browser_config']['download_directory']

            options = Options()
            for arg in config['browser_config']['chrome_options']:
                logger.debug(f"adding  parameter {arg} to driver options")
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

                logger.info("logged in to the dashboard")       
                # Wait for Dashboard, Database option
                database_menu = wait.until(
                    EC.visibility_of_element_located((By.XPATH, "//div[@class='gwt-Label' and contains(text(), 'Database')]"))
                )

                database_menu.click()
                logger.info("clicked the database button")


                logger.info("waiting for Groups option")
                groups_tab = wait.until(EC.element_to_be_clickable((
                    By.XPATH,
                    "//div[@class='gwt-TabLayoutPanelTabInner']/div[text()='Groups']"
                )))
                groups_tab.click()
                logger.info("clicked on Groups option")
  
 
                # wait for groups tab to load
                wait.until(EC.presence_of_element_located((
                    By.CLASS_NAME, "GKEPJM3CCEB"
                ))) 

                logger.info("groups tab found")

                # variables used to report the group results
                created_count=0
                updated_count=0
                action=None 
                total=0
                groups = []
   
                # Find all divs under the container that might be items
                container = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "GKEPJM3CCEB")))
                item_divs = container.find_elements(By.XPATH, ".//div[contains(@class, 'GKEPJM3C')]")
                
                # Filter down to only visible leaf nodes with text
                group_names = [
                    div.text.strip()
                    for div in item_divs
                    if div.is_displayed() and div.text.strip() != ""
                ]

                for group_name in group_names:
                    print(group_name)
                    total += 1 
    
                    logger.info(f"Group Name: {group_name}")

                    if dry_run:
                        group_exists = Groups.objects.filter(group_name=group_name).exists()
                        if group_exists:
                           updated_count += 1
                           action='Updated'
                        else:
                           created_count += 1
                           action='Created'
                        dry_run_action = 'Would create' if not group_exists else 'Would update'
                        message = f'{dry_run_action} event: {group_name}'
                        logging.info(message)

                    else:
                        group,created = Groups.objects.update_or_create(
                           group_name=group_name,
                           defaults={    
                                'group_points':1,
                                'group_name':group_name.strip(),
                           }
                        )
                        if created:
                           created_count += 1
                           action = 'Created'
                        else:
                           updated_count += 1
                           action = 'Updated'

                        message = f'{action} event: {group.id},{group_name}'
                        logging.info(message)
                summary = f"Processed: {total}, Created: {created_count}, Updated: {updated_count}"
                logger.info(f"{summary}")
                logger.info('group import from ivolunteer complete.')
                if dry_run:
                    logger.info(f"Dry-run mode enabled: no changes were saved.")


            except Exception as e:
                logger.error(f"Exception occurred: {e}")
                raise CommandError(f"Exception occurred:{str(e)}")
            finally:
                driver.quit()
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {str(e)}")
            raise CommandError(f"❌ Failed to parse YAML config: {str(e)}")

