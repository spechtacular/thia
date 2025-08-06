"""
Command to load or update event participation from a CSV file.
Uses the AppUser, Events, EventVolunteers models.
Provides a dry-run option.
"""

from datetime import datetime
from datetime import date
import csv
import logging
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from haunt_ops.models import AppUser
from haunt_ops.models import EventVolunteers
from haunt_ops.models import Events

# pylint: disable=no-member
logger = logging.getLogger("haunt_ops")  # Uses logger config from settings.py


class Command(BaseCommand):
    """
    run command
       python manage.py bulk_load_events_from_ivolunteer
                --csv=path/to/users.csv
    or with dry-run option
       python manage.py bulk_load_events_from_ivolunteer
                --csv=path/to/users.csv --dry-run

    """

    help = "Load or update ivolunteer users from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument("--csv", type=str, help="Path to the CSV file.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate updates without saving to database.",
        )

    def handle(self, *args, **kwargs):
        file_path = kwargs["csv"]
        dry_run = kwargs["dry_run"]

        try:
            with open(file_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                user_email = ""
                total = 0
                created_count = 0
                updated_count = 0
                for row in reader:
                    total += 1
                    user_email = row["email"].strip()
                    if not user_email:
                        message = f"Skipping row {total}: missing email."
                        logging.warning(message)
                        continue

                    # Check if user exists
                    try:
                        user = AppUser.objects.get(email=user_email)
                        logger.info(
                            "processing app_user=%s,%s,%s,%s,%s",
                            user.id,
                            user.email,
                            user.first_name,
                            user.last_name,
                            user.date_of_birth,
                        )
                    except ObjectDoesNotExist:
                        logger.error("No user with  email %s found.", user_email)
                        continue

                    # Check if event exists
                    try:
                        edate = row["date"].strip()
                        logger.debug("edate: %s", edate)
                        event = Events.objects.filter(event_date=edate).first()
                        logger.info(
                            "processing event: %s, %s, %s, %s",
                            event.id,
                            event.event_name,
                            event.event_date,
                            event.event_status,
                        )
                    except ObjectDoesNotExist:
                        logger.error("No event dated %s found.", edate)
                        continue

                    if dry_run:
                        ev_exists = EventVolunteers.objects.filter(
                            volunteer_id=user.id, event_id=event.id
                        ).exists()
                        action = "Would create" if not ev_exists else "Would update"
                        message = (
                            f"event_volunteers {action} for user.id: "
                            f"{user.id}, event.id: {event.id}  with email: {user_email}"
                        )

                        if action == "Would create":
                            created_count += 1
                        else:
                            updated_count += 1
                    else:
                        original_bd = row["date_of_birth"].strip()
                        if not original_bd:
                            obd = user.date_of_birth
                            obd_year = obd.year
                            obd_month = obd.month
                            obd_day = obd.day
                            original_bd = f"{obd_month:02}/{obd_day:02}/{obd_year:04}"
                        logger.debug("1original_bd: %s", original_bd)
                        if not original_bd:
                            message = f"Skipping row {total}: missing date_of_birth."
                            logging.warning(message)
                            continue
                        logger.debug("2original_bd: %s", original_bd)
                        dob = datetime.strptime(original_bd, "%m/%d/%Y")

                        dt = row["start_time"].strip()
                        naive_dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
                        aware_st = timezone.make_aware(
                            naive_dt, timezone=timezone.get_current_timezone()
                        )

                        dt = row["end_time"].strip()
                        naive_dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
                        aware_et = timezone.make_aware(
                            naive_dt, timezone=timezone.get_current_timezone()
                        )

                        wv = False
                        if "I agree" in row["waiver"].strip():
                            wv = True
                        else:
                            wv = False

                        eb = "true" in row["email_blocked"].strip().lower()

                        wm = "true" in row["wear_mask"].strip().lower()

                        # todays date
                        today = date.today()
                        age = (
                            today.year
                            - dob.year
                            - ((today.month, today.day) < (dob.month, dob.day))
                        )
                        # use date_of_birth to determine if user is over 16
                        under_16 = age < 16
                        # use date_of_birth to determine if user is over 18
                        under_18 = age < 18

                        signed_in = row["signed_in"] == "Yes"

                        confirmed = row["confirmed"] == "Yes"

                        waitlist = row["waitlist"] == "Yes"

                        conflict = row["conflict"] == "Yes"

                        points = row["points"]
                        if points in (None or ""):
                            points = 0.0

                        phone1 = ""
                        if row[phone1] is None or row[phone1] == "":
                            phone1 = user.phone1
                        else:
                            phone1 = row["phone1"].strip()

                        ice_name = ""
                        if row["ice_name"] is None or row["ice_name"] == "":
                            ice_name = user.ice_name
                        else:
                            ice_name = row["ice_name"].strip()

                        ice_relationship = ""
                        if (
                            row["ice_relationship"] is None
                            or row["ice_relationship"] == ""
                        ):
                            ice_relationship = user.ice_relationship
                        else:
                            ice_relationship = row["ice_relationship"].strip()

                        ice_phone = ""
                        if row["ice_phone"] is None or row["ice_phone"] == "":
                            ice_phone = user.ice_phone
                        else:
                            ice_phone = row["ice_phone"].strip()

                        # use date_of_birth to determine if user is over 16
                        logger.debug("points: %f", points)
                        logger.debug("haunt_experience: %s", row["haunt_experience"])
                        logger.debug("original birth date %s", original_bd)
                        logger.debug("email_blocked after test: %s", eb)
                        logger.debug("wear_mask: %s", row["wear_mask"])
                        logger.debug("waiver: %s", row["waiver"])
                        logger.debug("waiver after test: %s", wv)
                        logger.debug("start_time %s", aware_st)
                        logger.debug("end_time %s", aware_et)
                        logger.debug("dob %s", dob)
                        logger.debug("age %s", age)
                        logger.debug("under_16 %s", under_16)
                        logger.debug("under_18 %s", under_18)

                        ev, created = EventVolunteers.objects.update_or_create(
                            volunteer_id=user.id,
                            event_id=event.id,
                            defaults={
                                "first_name": row["first_name"].strip(),
                                "last_name": row["last_name"].strip(),
                                "volunteer_id": user.id,
                                "event_id": event.id,
                                "hours": row["hours"].strip(),
                                "points": points,
                                "date": row["date"].strip(),
                                "slot_column": row["slot_column"].strip(),
                                "slot_row": row["slot_row"].strip(),
                                "phone1": phone1,
                                "full_address": row["full_address"].strip(),
                                "under_16": under_16,
                                "under_18": under_18,
                                "date_of_birth": dob,
                                "conflict": conflict,
                                "waitlist": waitlist,
                                "signed_in": signed_in,
                                "confirmed": confirmed,
                                "start_time": aware_st,
                                "end_time": aware_et,
                                "waiver": wv,
                                "wear_mask": wm,
                                "ice_name": ice_name,
                                "ice_relationship": ice_relationship,
                                "ice_phone": ice_phone,
                                "allergies": row["allergies"].strip(),
                                "email_blocked": eb,
                            },
                        )

                        if created:
                            created_count += 1
                            action = "Created"
                        else:
                            updated_count += 1
                            action = "Updated"
                        message = (
                            f"✅{action} event_volunteer: {ev.id}"
                            f" ,user_id: {ev.volunteer_id} event_id: {ev.event_id}"
                        )

                    logging.info(message)
            summary = f"✅Processed: {total} users, Created: {created_count}, Updated: {updated_count}"
            logging.info(summary)
            if dry_run:
                logging.info("✅Dry-run mode enabled: no users were saved.")

        except FileNotFoundError:
            logging.error("❌File not found: %s", file_path)

        except Exception as e:
            logging.error("❌Error processing file: %s error %s", file_path, str(e))
