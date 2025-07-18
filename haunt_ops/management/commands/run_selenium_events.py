# todo: logging

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

import os
import time
import yaml

# --- browser options ---
driver = None
download_directory=None
options = Options()
# preferences used
prefs = None

# --- login ---
LOGIN_URL = None
ORG_ID = None
ADMIN_EMAIL = None
PASSWORD = None


def read_yaml_config(config_file_path):
    # Reads a YAML configuration file and returns a dictionary.
    try:
        with open(config_file_path, 'r') as file:
            config = yaml.safe_load(file)
            return config
    except FileNotFoundError:
        print(f"Error: Config File not found at {config_file_path}")
        return None
    except yaml.YAMLError as e:
        print(f"Error parsing YAML Config file: {e}")
        return None




def run_events_scraper():
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
        events_menu = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//div[@class='gwt-Label' and contains(text(), 'Events')]"))
        )
        events_menu.click()

        events = []


        # Locate all divs with __idx attribute (event blocks)
        event_blocks = driver.find_elements(By.XPATH, "//div[@__idx]")

        # read each event in the web page
        for block in event_blocks:

            event_name = block.find_element(By.XPATH, ".//div[@style='font-weight: bold; font-size: 12pt;']").text
            start_date = block.find_element(By.XPATH, ".//b[text()='Start:']/following-sibling::i[1]").text
            status = block.find_element(By.XPATH, ".//b[text()='Status:']/following-sibling::i[1]").text

            print(f"Event Name: {event_name}, Start: {start_date}, Status: {status}")

            events.append({
                'name': event_name,
                'start_date': start_date,
                'status': status
            })

        # debug 
        #print(events)


    except Exception as e:
        print("❌ Error occurred:", e)
    finally:
        driver.quit()

if __name__ == "__main__":
    config = read_yaml_config("selenium_config.yaml")
    if config is None:
        sys.exit(1)
    else:
        #  --- initialize browser options ---
        download_directory=config['browser_config']['download_directory']

        options = Options()
        for arg in config['browser_config']['chrome_options']:
            #print(f"adding yaml parameter {arg} to driver options")
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

        print(f"password is {PASSWORD}")

        run_events_scraper()

