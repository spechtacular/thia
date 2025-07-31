"""
# haunt_ops/management/commands/load_groups_from_config.py
Command to load or update groups from a configuration file.
Uses the Groups model and allows for dry-run and verbose logging.
Uses the configuration file named ./config/etl_config.yaml
"""
from django.core.management.base import BaseCommand, CommandError
from haunt_ops.models import Groups


import yaml
import os
from datetime import datetime
import logging

logger = logging.getLogger('haunt_ops')  # Uses logger config from settings.py

class Command(BaseCommand):
    """
        start command
            python manage.py load_groups_from_config --config=config/etl_config.yaml --dry-run
        or with custom config
            python manage.py load_groups_from_config --config=config/custom_config.yaml --dry-run
        or without dry-run
            python manage.py load_groups_from_config --config=config/etl_config.yaml
    """


    help = 'Load or update events from ivolunteers Groups page, uses configuration file named ./config/etl_config.yaml'

    def add_arguments(self, parser):
        parser.add_argument(
            '--config',
            type=str,
            default='config/etl_config.yaml',
            help='Path to YAML configuration file (default: config/etl_config.yaml) \n With Custom config:\n python manage.py load_config_example --config=config/custom_config.yaml'
        )
        parser.add_argument('--dry-run', action='store_true', help='Simulate updates without saving to database.')



    def handle(self, *args, **kwargs):
        config_path = kwargs['config']
        dry_run = kwargs['dry_run']

        if not os.path.exists(config_path):
            logger.error(f"config file not found {config_path}")
            raise CommandError(f"❌ Config file not found: {config_path}")

        try:
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)

            if not config:
                logger.error(f"Config file {config_path} is empty or malformed.")
                raise CommandError(f"❌ Config file {config_path} is empty or malformed.")

            group_list = config.groups
            created_count=0
            updated_count=0
            action=None 
            total=0
            groups = []
    
            # read each event in the web page
            for block in group_list:
                total += 1 

                logger.info(f"Event Name: {event_name}, Start: {event_date}, Status: {event_status}")

                # Parse postgresql date format
                parsed_event_date = datetime.strptime(event_date, '%m/%d/%Y')

                # Reformat to django YYYY-MM-DD
                formatted_event_date = parsed_event_date.strftime('%Y-%m-%d')

                if dry_run:
                    event_exists = Groups.objects.filter(event_name=event_name).exists()
                    if event_exists:
                        updated_count += 1
                        action='Updated'
                    else:
                        created_count += 1
                        action='Created'
                    dry_run_action = 'Would create' if not event_exists else 'Would update'
                    message = f'{dry_run_action} event: {event_name}'
                    logging.info(message)

                else:
                    event,created = Groups.objects.update_or_create(
                        event_date=formatted_event_date,
                        defaults={    
                            'event_date':formatted_event_date,
                            'event_name':event_name.strip(),
                            'event_status':event_status.strip(),
                        }
                    )
                    if created:
                        created_count += 1
                        action = 'Created'
                    else:
                        updated_count += 1
                        action = 'Updated'

                    message = f'{action} event: {event.id},{formatted_event_date}'
                    logging.info(message)
                summary = "Processed: %d, Created: %d, Updated: %d" % (total, created_count, updated_count)
                logger.info("%s", summary)
                logger.info('event import form ivolunteer complete.')
                if dry_run:
                    logger.info("Dry-run mode enabled: no changes were saved.")


        except yaml.YAMLError as e:
            logger.error("YAML parsing error: %s", str(e))
            raise CommandError(f"❌ Failed to parse YAML config: {str(e)}") from e
        except Exception as e:
            logger.error("Exception occurred: %s", e)
            raise CommandError(f"Exception occurred:{str(e)}") from e
        finally:
            pass

