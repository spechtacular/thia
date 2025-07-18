from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time

options = Options()
options.headless = True  # or False to see the browser
driver = webdriver.Chrome(options=options)

wait = WebDriverWait(driver, 20)

# 1. Login
driver.get("https://www.ivolunteer.com/login")  # Adjust if different
wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys("your_username")
driver.find_element(By.NAME, "password").send_keys("your_password")
driver.find_element(By.XPATH, "//button[contains(text(), 'Login')]").click()

# 2. Navigate to "Database"
wait.until(EC.presence_of_element_located((By.XPATH, "//div[text()='Database']"))).click()

tabs = driver.find_elements(By.XPATH, "//div[@class='gwt-TabLayoutPanelTabInner']/div")
for tab in tabs:
    print("Database Report TAB:", tab.text)


# 3. Go to Reports tab
wait.until(EC.presence_of_element_located((By.XPATH, "//div[text()='Reports']"))).click()

# 4. Configure the report:
# 4.1 Select format
format_select = Select(wait.until(EC.presence_of_element_located((By.XPATH, "//select[option[@value='EXCEL']]"))))
format_select.select_by_value("EXCEL")

# 4.2 Set sort/group
sort_selects = driver.find_elements(By.XPATH, "//select[@class='GKEPJM3CLLB']")
sort_selects[0].select_by_value("NAME_EMAIL")  # Sort/group dropdown
sort_selects[1].select_by_value("INFINITE")    # Page size dropdown

# 4.3 Toggle checkboxes (by value)
driver.find_element(By.XPATH, "//input[@value='INCLUDE_EVENTS']").click()

# 4.4 Select radio button: "All Database Participants"
driver.find_element(By.XPATH, "//label[contains(text(), 'All Database Participants')]/preceding-sibling::input").click()

# 5. Run the report
run_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@title='Run the selected report']")))
run_button.click()

# 6. Wait for and handle download (depends on how file is delivered)
time.sleep(10)  # or wait for file if browser handles download
driver.quit()

