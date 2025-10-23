from celery import shared_task
from haunt_ops.models import EventVolunteers
from selenium import webdriver
from selenium.webdriver.common.by import By
import os
import logging
import time

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def sync_signed_in_to_ivolunteer(self, ev_id):
    """
    Sync the signed_in field from Django to iVolunteer via Selenium.
    Retries automatically on failure.
    """
    try:
        ev = EventVolunteers.objects.select_related("volunteer", "event").get(pk=ev_id)
        email = ev.volunteer.email
        event_name = ev.event.event_name

        logger.info(f"🚀 Starting sync for volunteer {email} — event: {event_name}")

        # Setup Selenium Chrome driver
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)

        try:
            # Step 1 — Login
            driver.get("https://the-haunt.ivolunteer.com")
            time.sleep(2)

            driver.find_element(By.ID, "action0").send_keys(os.getenv("IVOLUNTEER_ORG"))
            driver.find_element(By.ID, "action1").send_keys(os.getenv("IVOLUNTEER_ADMIN_EMAIL"))
            driver.find_element(By.ID, "action2").send_keys(os.getenv("IVOLUNTEER_PASSWORD"))
            driver.find_element(By.ID, "Submit").click()
            time.sleep(4)

            # Step 2 — Navigate to event page
            driver.get("https://the-haunt.ivolunteer.com/oct_haunt_2025")
            time.sleep(3)

            # Step 3 — Find checkbox for user and click
            checkbox_xpath = f"//span[contains(text(), '{email}')]/ancestor::tr//input[@type='checkbox']"
            checkbox = driver.find_element(By.XPATH, checkbox_xpath)
            if not checkbox.is_selected():
                checkbox.click()
                logger.info(f"✅ Marked {email} as signed in on iVolunteer")

        except Exception as e:
            logger.error(f"❌ Selenium action failed for {email}: {e}")
            raise self.retry(exc=e)  # retry task

        finally:
            driver.quit()
            logger.info(f"🧹 Closed Selenium session for {email}")

    except EventVolunteers.DoesNotExist:
        logger.error(f"❌ EventVolunteer record {ev_id} not found.")
    except Exception as e:
        logger.error(f"❌ Unexpected error during sync for ID={ev_id}: {e}")
        raise self.retry(exc=e)

