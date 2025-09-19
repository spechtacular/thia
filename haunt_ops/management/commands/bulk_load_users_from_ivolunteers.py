"""
Command to load or update users from a CSV file.
Uses the AppUser model.
Allows for dry-run and variable logging level options.
"""

import logging
import csv
import os
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.conf import settings
from haunt_ops.models import AppUser
from haunt_ops.models import Groups
from haunt_ops.models import GroupVolunteers
from haunt_ops.utils.logging_utils import configure_rotating_logger

# pylint: disable=no-member

LOG_LEVELS = {
    "DEBUG": logging.DEBUG, "INFO": logging.INFO,
    "WARNING": logging.WARNING, "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL
}

class Command(BaseCommand):
    """
    start command
        python manage.py bulk_load_users_from_ivolunteers --csv haunt_ops/download/replaced_users.csv
    or with dry-run
        python manage.py bulk_load_users_from_ivolunteers --csv haunt_ops/download/replaced_users.csv --dry-run
    or with log-level
        python manage.py bulk_load_users_from_ivolunteers --csv haunt_ops/download/replaced_users.csv --log-level DEBUG
    """

    help = "Insert or update ivolunteer users from a CSV file with optional dry-run feature."

    def add_arguments(self, parser):
        parser.add_argument("--csv", type=str, help="Path to the CSV file.(Default download to haunt_ops/download/ folder).")
        parser.add_argument(
            '--dry-run',
            action="store_true",
            help="Simulate updates without saving to database.",
        )
        parser.add_argument(
            '--log-level','--log',
            dest="log_level",
            type=str,
            default="DEBUG",
            choices=list(LOG_LEVELS.keys()),
            help="Set the log level (default: INFO)",
        )

    def handle(self, *args, **kwargs):
        file_path = kwargs["csv"]
        if not file_path:
            raise CommandError("--csv is required")
        dry_run = kwargs['dry_run']
        level_name = (kwargs['log_level'] or 'INFO').upper()
        level = LOG_LEVELS[level_name]

        # 2) make sure log dir exists
        os.makedirs(settings.LOG_DIR, exist_ok=True)

        # 3) configure your rotating logger (you already have this util)
        logger = configure_rotating_logger(
            __file__, log_dir=settings.LOG_DIR, log_level=level)

        logger.debug("Options: %r", kwargs)

        logger.info("Starting bulk load of users data from ivolunteer.")

        try:
            with open(file_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                user_email = ""
                total = 0
                created_count = 0
                updated_count = 0
                message = ""
                for row in reader:
                    total += 1
                    user_email = row["email"].strip()
                    logger.debug("---processing user_email: %s", user_email)
                    if not user_email:
                        message = f"Skipping row {total}: missing email {user_email}."
                        self.stdout.write(message)
                        logging.warning(message)
                        continue

                    if dry_run:
                        user_exists = AppUser.objects.filter(email=user_email).exists()
                        action = "Would create" if not user_exists else "Would update"
                        logger.info("%s user: %s", action, user_email)
                    else:
                        original_bd = row["date_of_birth"].strip()
                        logger.debug("original birth date %s", original_bd)

                        bd = original_bd.split(" ", 1)
                        logger.debug("date_of_birth after split %s", bd[0])


                        dt = row["start_date"].strip()
                        naive_dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
                        logger.debug("naive_date_joined before tz added %s", dt)

                        aware_dt = timezone.make_aware(
                            naive_dt, timezone=timezone.get_current_timezone()
                        )
                        logger.debug("aware_date_joined after tz added %s", aware_dt)


                        wv = False
                        logger.debug("waiver: %s", row["waiver"])
                        if "i agree" in row["waiver"].strip().lower():
                            wv = True
                        else:
                            wv = False
                        logger.debug("waiver after test: %s", wv)

                        eb = False
                        if "true" in row["email_blocked"].strip().lower():
                            eb = True
                        else:
                            eb = False
                        logger.debug("email_blocked: %s", eb)

                        wm = False
                        if "1.0" in row["wear_mask"].strip():
                            wm = True
                        else:
                            wm = False
                        logger.debug("wear_mask: %s", wm)

                        logger.debug("haunt_experience: %s", row["haunt_experience"])
                        logger.debug("events: %s", row["events"])




                        user, created = AppUser.objects.update_or_create(
                            email=user_email,
                            defaults={
                                "first_name": row["first_name"].strip(),
                                "last_name": row["last_name"].strip(),
                                "username": user_email,
                                "company": row["company"].strip(),
                                "address": row["address"].strip(),
                                "city": row["city"].strip(),
                                "state": row["state"].strip(),
                                "zipcode": row["zipcode"].strip(),
                                "country": row["country"].strip(),
                                "phone1": row["phone1"].strip(),
                                "phone2": row["phone2"].strip(),
                                "date_of_birth": bd[0],
                                "password": bd[0],
                                "date_joined": aware_dt,
                                "waiver": wv,
                                "referral_source": row["referral_source"].strip(),
                                "wear_mask": wm,
                                "tshirt_size": row["tshirt_size"].strip(),
                                "ice_name": row["ice_name"].strip(),
                                "ice_relationship": row["ice_relationship"].strip(),
                                "ice_phone": row["ice_phone"].strip(),
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
                        message = f"{action} user: {user.id},{user.email}"

                        # process haunt_experience and groups
                        haunt_experience = row["haunt_experience"].split(",")
                        for experience in haunt_experience:
                            experience = experience.strip()
                            if experience:
                                gmsg = ""
                                try:
                                    # case insensitive lookup
                                    group = Groups.objects.get(group_name__iexact=experience)
                                    logging.info(
                                        "Group ID: %d, Name: %s for user %s",
                                        group.id,
                                        group.group_name,
                                        user_email,
                                    )
                                    gv, created = (
                                        GroupVolunteers.objects.update_or_create(
                                            group_id=group.id,
                                            volunteer_id=user.id,
                                            defaults={},
                                        )
                                    )
                                    if created:
                                        gmsg = (
                                            f" | Added to group: {group.group_name} "
                                            f"and created GroupVolunteers entry {gv.id}."
                                        )
                                    else:
                                        gmsg = (
                                            f" | Already in group: {group.group_name} "
                                            f"and GroupVolunteers entry exists {gv.id}."
                                        )

                                except Groups.objects.model.DoesNotExist as exc:
                                    gmsg = (
                                        f"❌ No group found with name {experience} "
                                        f"for user {user_email} : "
                                        f"exc : {exc}"
                                    )
                                finally:
                                    logging.info(gmsg)
                        logging.info(message)
            summary = (
                f"✅Processed: {total} users, Created: {created_count} "
                f"users, Updated: {updated_count} users"
            )
            logging.info(summary)
            logger.info("✅CSV import of users complete.")
            if dry_run:
                logger.info("✅Dry-run mode enabled: no users were saved.")

        except FileNotFoundError:
            error_msg = f"❌File not found: {file_path}"
            logging.error(error_msg)

        except Exception as e:
            error_msg = f"❌Error processing file: {str(e)}"
            logging.error(error_msg)
