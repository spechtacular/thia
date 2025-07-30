from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from haunt_ops.models import AppUser, Events, Groups, EventChecklist, GroupVolunteers, EventVolunteers
import logging

logger = logging.getLogger('haunt_ops')  # Uses logger config from settings.py

class Command(BaseCommand):
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
                    logger.info(f" - {name}: {count} record(s) would be deleted.")

                # process User deletion separately
                logger.info(f" - AppUser: {user_count} record(s) would be deleted.")

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
                            logger.info(f" - Deleted {deleted} record(s) from {name}")

                        # delete AppUser data
                        logger.info("🚨 Deleting data from AppUser table...")
                        logger.info(f"🚨 Deleting {user_count} user(s)...")
                        to_delete.delete()
                        logger.info(self.style.SUCCESS(f"✅ Deleted {user_count} user(s), except IDs {keep_ids}."))
                    logger.info(self.style.SUCCESS("✅ Data cleared successfully."))
                except Exception as e:
                    logger.error(self.style.ERROR(f"❌ Error deleting data: {e}"))

