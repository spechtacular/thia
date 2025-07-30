from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime
from haunt_ops.models import AppUser
from haunt_ops.models import Groups
from haunt_ops.models import Events
from haunt_ops.models import AppUserGroups
from haunt_ops.models import EventVolunteers
from haunt_ops.models import GroupVolunteers
from haunt_ops.models import EventChecklist
import logging
import csv
import os
from datetime import datetime


logger = logging.getLogger('haunt_ops')  # Uses logger config from settings.py


class Command(BaseCommand):

    help = 'Load or update user groups from a CSV file with optional dry-run feature.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file.')
        parser.add_argument('--dry-run', action='store_true', help='Simulate updates without saving to database.')


    def handle(self, *args, **kwargs):
        file_path = kwargs['csv_file']
        dry_run = kwargs['dry_run']
        try:
            with open(file_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                user_email=''
                total = 0
                created_count = 0
                updated_count = 0
                action = ''
                message = ''
                for row in reader:
                    total += 1
                    user_email = row['email'].strip()
                    if not user_email:
                        message = f"Skipping row {total}: missing email."
                        logging.warning(message)
                        continue

                    user_exists = AppUser.objects.filter(email=user_email).exists()
                    print(f"haunt_experience: {row['haunt_experience']}")
                    print(f"events: {row['events']}")

                    if dry_run:
                        action = 'Would create' if not user_exists else 'Would update'
                        message = f'{action} user: {user_email}'
                    else:
                        if user_exists:
                           user = AppUser.objects.get(email=user_email)
                           self.stdout.write(f"email: {user_email}, User ID: {user.id}")

                           event_volunteer,created = EventVolunteers.objects.update_or_create(
                               email=user_email,
                               defaults={
                               }
                           )
                        
                           if created:
                              created_count += 1
                              action = 'EventVolunteers Created'
                           else:
                              updated_count += 1
                              action = 'EventVolunteers Updated'
                           message = f'{action} user: {user.id},{user.email}'
                           logging.info(message)
                        else: 
                           self.stderr.write("User not found.")
            summary = f"Processed: {total}, Created: {created_count}, Updated: {updated_count}"
            self.stdout.write(self.style.SUCCESS(summary))
            logging.info(summary)
            self.stdout.write(self.style.SUCCESS('CSV import complete.'))
            if dry_run:
                self.stdout.write(self.style.WARNING("Dry-run mode enabled: no changes were saved."))


        except FileNotFoundError:
            error_msg = f'File not found: {file_path}'
            self.stderr.write(self.style.ERROR(error_msg))
            logging.error(error_msg)

        except Exception as e:
            error_msg = f'Error processing file: {str(e)}'
            self.stderr.write(self.style.ERROR(error_msg))
            logging.error(error_msg)
