"""
Command to load or update users from a CSV file.
Uses the AppUser model and allows for dry-run and verbose logging.
Uses the configuration file named ./config/selenium_config.yaml
"""
import logging
import csv
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.conf import settings
from haunt_ops.models import AppUser
from haunt_ops.models import Groups
from haunt_ops.models import GroupVolunteers
from haunt_ops.utils.logging_utils import configure_rotating_logger



class Command(BaseCommand):
    """
        start command
            python manage.py load_users_from_csv --csv_file=path/to/users.csv --dry-run --verbose
        or with custom config
            python manage.py load_users_from_csv --csv_file=path/to/custom_users.csv --dry-run --verbose
        or without dry-run
            python manage.py load_users_from_csv --csv_file=path/to/users.csv
    """
    help = 'Load or update users from a CSV file with optional dry-run feature.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file.')
        parser.add_argument('--dry-run', action='store_true', help='Simulate updates without saving to database.')
        parser.add_argument( '--log-level', type=str, default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
            help='Set the log level (default: INFO)'
        )


    def handle(self, *args, **kwargs):
        file_path = kwargs['csv_file']
        dry_run = kwargs['dry_run']
        log_level = kwargs['log_level']

        # Get a unique log file using __file__
        logger = configure_rotating_logger(__file__, log_dir=settings.LOG_DIR, log_level=log_level)


        logger.info("Started load_groups command.")

        try:
            with open(file_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                user_email=''
                total = 0
                created_count = 0
                updated_count = 0
                message=''
                for row in reader:
                    total += 1
                    user_email = row['email'].strip()
                    if not user_email:
                        message = f"Skipping row {total}: missing email."
                        self.stdout.write(message)
                        logging.warning(message)
                        continue


                    if dry_run:
                        user_exists = AppUser.objects.filter(email=user_email).exists()
                        action = 'Would create' if not user_exists else 'Would update'
                        logger.info('%s user: %s', action, user_email)
                    else:
                        original_bd=row['date_of_birth'].strip()
                        bd=original_bd.split(' ',1)

                        dt=row['start_date'].strip()
                        naive_dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S') 
                        aware_dt=timezone.make_aware(naive_dt, timezone=timezone.get_current_timezone())

                        wv=False
                        if "I agree" in row['waiver'].strip() :
                            wv=True
                        else:
                            wv=False

                        eb=False
                        if "true" in row['email_blocked'].strip().lower() :
                            eb=True
                        else:
                            eb=False

                        wm=False
                        if "true" in row['wear_mask'].strip().lower() :
                            wm=True
                        else:
                            wm=False


                        logger.debug("haunt_experience: %s", row['haunt_experience'])
                        logger.debug("events: %s", row['events'])
                        logger.debug("original birth date %s", original_bd)
                        logger.debug("date_of_birth after split %s", bd[0])
                        logger.debug("original email_blocked: %s", row['email_blocked'])
                        logger.debug("email_blocked after test: %s", eb)
                        logger.debug("wear_mask: %s", row['wear_mask'])
                        logger.debug("waiver: %s", row['waiver'])
                        logger.debug("waiver after test: %s", wv)
                        logger.debug("naive_date_joined before tz added %s", dt)
                        logger.debug("aware_date_joined after tz added %s", aware_dt)
    

                        user,created = AppUser.objects.update_or_create(
                            email=user_email,
                            defaults={
                                 'first_name':row['first_name'].strip(),
                                 'last_name':row['last_name'].strip(),
                                 'username':user_email,
                                 'company':row['company'].strip(),
                                 'address':row['address'].strip(),
                                 'city':row['city'].strip(),
                                 'state':row['state'].strip(),
                                 'zipcode':row['zipcode'].strip(),
                                 'country':row['country'].strip(),
                                 'phone1':row['phone1'].strip(),
                                 'phone2':row['phone2'].strip(),
                                 #under_18:row['under_18'].strip()
                                 'date_of_birth':bd[0],
                                 'password':bd[0],
                                 #notes:row['notes'].strip(),
                                 'date_joined':aware_dt,
                                 #last_activity:row['last_activity'].strip(),
                                 'waiver':wv,
                                 'referral_source':row['referral_source'].strip(),
                                 #'haunt_experience':row['haunt_experience'].strip(),
                                 'wear_mask':wm,
                                 'tshirt_size':row['tshirt_size'].strip(),
                                 'ice_name':row['ice_name'].strip(),
                                 'ice_relationship':row['ice_relationship'].strip(),
                                 'ice_phone':row['ice_phone'].strip(),
                                 'allergies':row['allergies'].strip(),
                                 'email_blocked':eb,
                            }
                        )
                        
                        if created:
                           created_count += 1
                           action = 'Created'
                        else:
                           updated_count += 1
                           action = 'Updated'
                        message = f'{action} user: {user.id},{user.email}'

                        # process haunt_experience and groups
                        haunt_experience = row['haunt_experience'].split(';')
                        for experience in haunt_experience:
                            experience = experience.strip()
                            if experience:
                                try:
                                    group = Groups.objects.get(group_name=experience)
                                    self.stdout.write(f"Group ID: {group.id}, Name: {group.group_name} for user {user_email}")
                                    gv,created = GroupVolunteers.objects.update_or_create(
                                        group_id=group.id,
                                        volunteer_id=user.id,
                                        defaults={
                                        }
                                    )
                                    if created:
                                        message += f" | Added to group: {group.group_name} and created GroupVolunteers entry {gv.id}."
                                    else:
                                        message += f" | Already in group: {group.group_name} and GroupVolunteers entry exists {gv.id}."   

                                except Groups.objects.model.DoesNotExist as exc:
                                    raise CommandError(f"❌ No group found with name {experience} for user {user_email}.") from exc
                                
                    logging.info(message)
            summary = f"Processed: {total} users, Created: {created_count} users, Updated: {updated_count} users"
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
