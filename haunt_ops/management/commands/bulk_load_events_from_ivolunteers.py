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
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from haunt_ops.models import AppUser
from haunt_ops.models import EventVolunteers
from haunt_ops.models import Events
from haunt_ops.utils.logging_utils import configure_rotating_logger


# pylint: disable=no-member


class Command(BaseCommand):
    """
    run command
       python manage.py bulk_load_events_from_ivolunteer
                --csv=path/to/users.csv
    or with dry-run option
       python manage.py bulk_load_events_from_ivolunteer
                --csv=path/to/users.csv --dry-run
    or with custom log level
       python manage.py bulk_load_events_from_ivolunteer
                --csv=path/to/users.csv --log DEBUG
    or with custom log level and dry-run option
       python manage.py bulk_load_events_from_ivolunteer
                --csv=path/to/users.csv --dry-run --log DEBUG

    """

    help = "Load or update ivolunteer users from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument("--csv", type=str, help="Path to the CSV file.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate updates without saving to database.",
        )

        parser.add_argument(
            "--log",
            type=str,
            default="INFO",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            help="Set the log level (default: INFO)",
        )

    def handle(self, *args, **kwargs):
        file_path = kwargs["csv"]
        dry_run = kwargs["dry_run"]
        log_level = kwargs["log"].upper()

        # Get a unique log file using __file__
        logger = configure_rotating_logger(
            __file__, log_dir=settings.LOG_DIR, log_level=log_level
        )

        logger.info("loading ivolunteer events data.")


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
                        if hasattr(edate, "date"):   # edate might be a datetime
                            edate = edate.date()
                        incoming_name = row["event_name"].strip()
                        logger.debug("edate: %s", edate)
                        event = Events.objects.filter(event_date=edate).first()
                        if event is None:
                            base_name = (incoming_name or "Unnamed Event").strip()
                            new_name  = f"{base_name} — {edate}"   # your “modified” name
                            event = Events.objects.create(
                                event_date=edate,
                                event_name=new_name,
                                event_status="TBD",
                            )

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
                        # Process the row data
                        logger.debug("Processing row %s", total)
                        original_bd = row["date_of_birth"].strip()
                        if not original_bd:
                            message = f"row {total}: date_of_birth is not defined in the query result."
                            logging.warning(message)
                            obd = user.date_of_birth
                            if obd is None:
                                message = f"Skipping row {total}: date_of_birth is not specified in the user table either."
                                logging.warning(message)
                                continue
                            logger.debug("user date_of_birth: %s", obd)
                            obd_year = obd.year
                            obd_month = obd.month
                            obd_day = obd.day
                            original_bd = f"{obd_month:02}/{obd_day:02}/{obd_year:04}"
                        logger.debug("2original_bd: %s", original_bd)
                        dob = datetime.strptime(original_bd, "%m/%d/%Y")

                        logger.debug("dob: %s", dob)
                        dt = row["start_time"].strip()
                        if not dt:
                            message = f"Skipping row {total}: missing start_time."
                            logging.warning(message)
                            continue
                        logger.debug("dt: %s", dt)
                        naive_dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
                        aware_st = timezone.make_aware(
                            naive_dt, timezone=timezone.get_current_timezone()
                        )

                        logger.debug("aware_st: %s", aware_st)
                        dt = row["end_time"].strip()
                        naive_dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
                        aware_et = timezone.make_aware(
                            naive_dt, timezone=timezone.get_current_timezone()
                        )
                        logger.debug("aware_et: %s", aware_et)


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

                        logger.debug("under_16 %s", under_16)
                        logger.debug("under_18 %s", under_18)
                        logger.debug("age %s", age)

                        signed_in = row["signed_in"] == "Yes"

                        confirmed = row["confirmed"] == "Yes"

                        waitlist = row["waitlist"] == "Yes"

                        conflict = row["conflict"] == "Yes"

                        logger.debug("signed_in: %s", signed_in)
                        logger.debug("confirmed: %s", confirmed)
                        logger.debug("waitlist: %s", waitlist)
                        logger.debug("conflict: %s", conflict)


                        points = row["points"]
                        if points in (None or ""):
                            points = 0.0
                            logger.debug("points is None or empty, setting to 0.0")
                        else:
                            try:
                                points = float(points)
                            except ValueError:
                                logger.error(
                                    "Invalid points value '%s', setting to 0.0", points
                                )
                                points = 0.0
                        logger.debug("points: %f", points)
                        logger.debug("full_address: %s", row["full_address"].strip())

                        # use date_of_birth to determine if user is over 16
                        logger.debug("points: %f", points)
                        logger.debug("haunt_experience: %s", row["haunt_experience"])
                        logger.debug("original birth date %s", original_bd)

                        ev, created = EventVolunteers.objects.update_or_create(
                            volunteer_id=user.id,
                            event_id=event.id,
                            defaults={
                                "volunteer_id": user.id,
                                "event_id": event.id,
                                "event_name": event.event_name.strip(),
                                "date": event.event_date,
                                "hours": row["hours"].strip(),
                                "points": points,
                                "task": row["task"].strip(),
                                "slot_column": row["slot_column"].strip(),
                                "slot_row": row["slot_row"].strip(),
                                #"phone1": phone1,
                                "full_address": row["full_address"].strip(),
                                "under_16": under_16,
                                "under_18": under_18,
                                #"date_of_birth": dob,
                                "conflict": conflict,
                                "waitlist": waitlist,
                                "signed_in": signed_in,
                                "confirmed": confirmed,
                                "start_time": aware_st,
                                "end_time": aware_et,
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
