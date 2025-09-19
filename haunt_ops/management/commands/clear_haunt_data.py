"""
Command to clear haunt-related operational data.
Deletes data from key tables like AppUser, Events, Groups,
     GroupVolunteers, and EventVolunteers.
Can be run in dry-run mode to preview deletions without actually
    removing data.
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model
from haunt_ops.models import (
    Events,
    Groups,
    TicketSales,
    AppUser,
    GroupVolunteers,
    EventVolunteers,
)

# pylint: disable=no-member
logger = logging.getLogger("haunt_ops")  # Uses logger config from settings.py

import sys

def confirm(prompt: str, default: bool = False) -> bool:
    """
    Ask user to confirm. Returns True/False.
    default=False -> [y/N]; default=True -> [Y/n]
    """
    suffix = " [Y/n] " if default else " [y/N] "
    while True:
        try:
            ans = input(prompt + suffix).strip().lower()
        except EOFError:
            # No stdin (e.g., piped/CI) -> choose default
            return default
        if ans == "":
            return default
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("Please enter 'y' or 'n'.")

class Command(BaseCommand):
    """
    start command
        python manage.py clear_haunt_data --dry-run
    or without dry-run
        python manage.py clear_haunt_data
    This command deletes all data from key operational tables,
         optional --dry-run to preview deletions.
    It does not delete specifed accounts, such as sysadmin and test accounts.
    """

    help = "Deletes all data from key operational tables, with optional --dry-run"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview which tables will be cleared without deleting any data",
        )

        parser.add_argument(
            "-y", "--yes",
            action="store_true",
            help="Skip confirmation prompt and proceed."
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # tables to clear
        tables = [
            ("EventVolunteers", EventVolunteers),
            ("GroupVolunteers", GroupVolunteers),
            ("TicketSales", TicketSales),
            ("AppUser", AppUser),
            ("Groups", Groups),
            ("Events", Events),
        ]

        # refuse to run interactively if no TTY and no --yes
        if not sys.stdin.isatty() and not options["yes"]:
            raise CommandError("No TTY available; re-run with --yes to proceed non-interactively.")

        if not options["yes"]:
            if not confirm("This will delete all Haunt data from the Postgresql database. Continue?", default=False):
                self.stdout.write(self.style.WARNING("Aborted by user."))
                return

        # dont clear required accounts
        # dont delete these accounts, these are used for sysadmin, test accounts, etc.
        keep_ids = [1]
        logger.info("🔍 Checking for AppUser deletions...")
        user = get_user_model()

        to_delete = user.objects.exclude(id__in=keep_ids)
        user_count = to_delete.count()

        if user_count == 0:
            logger.info(self.style.WARNING("No app_users to delete."))
            return
        else:

            if dry_run:
                logger.info("🔍 DRY RUN: The following deletions would occur:")
                for name, model in tables:
                    count = model.objects.count()
                    logger.info(" - %s: %d record(s) would be deleted.", name, count)

                # process User deletion separately
                logger.info(" - AppUser: %d record(s) would be deleted.", user_count)

                # finished dry run
                logger.info(
                    self.style.SUCCESS("✅ Dry run complete. No data has been deleted.")
                )
                return

            # if not dry run, proceed with deletion
            else:
                try:
                    with transaction.atomic():
                        logger.info("🚨 Deleting data from haunt-related tables...")
                        for name, model in tables:
                            deleted, _ = model.objects.all().delete()
                            logger.info(
                                " - Deleted %d record(s) from %s", deleted, name
                            )

                        # delete AppUser data
                        logger.info("🚨 Deleting data from AppUser table...")
                        logger.info("🚨 Deleting %d user(s)...", user_count)
                        to_delete.delete()
                        logger.info(
                            self.style.SUCCESS(
                                f"✅ Deleted {user_count} user(s), except IDs {keep_ids}."
                            )
                        )
                    logger.info(self.style.SUCCESS("✅ Data cleared successfully."))
                except Exception as e:
                    logger.error(self.style.ERROR(f"❌ Error deleting data: {e}"))
