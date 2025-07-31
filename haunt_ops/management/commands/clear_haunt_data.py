"""
Command to clear haunt-related operational data.
Deletes data from key tables like AppUser, Events, Groups, EventChecklist, GroupVolunteers, and EventVolunteers.
Can be run in dry-run mode to preview deletions without actually removing data.
"""
import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from haunt_ops.models import Events, Groups, EventChecklist, GroupVolunteers, EventVolunteers

logger = logging.getLogger('haunt_ops')  # Uses logger config from settings.py

class Command(BaseCommand):
    """
        start command
            python manage.py clear_haunt_data --dry-run
        or without dry-run
            python manage.py clear_haunt_data
        This command deletes all data from key operational tables, with optional --dry-run to preview deletions.
        It does not delete required accounts, such as sysadmin and test accounts.
        It will not delete AppUser accounts with IDs 2 and 3, which are used as sysadmin and test accounts.
    """

    help = 'Deletes all data from key operational tables, with optional --dry-run'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview which tables will be cleared without deleting any data',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # tables to clear
        tables = [
                ('EventVolunteers', EventVolunteers),
                ('GroupVolunteers', GroupVolunteers),
                ('EventChecklist', EventChecklist),
                ('Groups', Groups),
                ('Events', Events),
            ]
        
        # dont clear required accounts
        # dont delete these accounts, these are used as sysadmin and test accounts
        keep_ids = [2, 3] 
        logger.info("🔍 Checking for AppUser deletions...")
        User = get_user_model()

        to_delete = User.objects.exclude(id__in=keep_ids)
        user_count = to_delete.count()

        if user_count==0:
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
                logger.info(self.style.SUCCESS("✅ Dry run complete. No data has been deleted."))
                return

            # if not dry run, proceed with deletion
            else:
                try:
                    with transaction.atomic():
                        logger.info("🚨 Deleting data from haunt-related tables...")
                        for name, model in tables:
                            deleted, _ = model.objects.all().delete()
                            logger.info(" - Deleted %d record(s) from %s", deleted, name)

                        # delete AppUser data
                        logger.info("🚨 Deleting data from AppUser table...")
                        logger.info("🚨 Deleting %d user(s)...", user_count)
                        to_delete.delete()
                        logger.info(self.style.SUCCESS(f"✅ Deleted {user_count} user(s), except IDs {keep_ids}."))
                    logger.info(self.style.SUCCESS("✅ Data cleared successfully."))
                except Exception as e:
                    logger.error(self.style.ERROR(f"❌ Error deleting data: {e}"))

