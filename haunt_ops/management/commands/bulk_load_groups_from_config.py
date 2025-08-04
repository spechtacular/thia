"""
# haunt_ops/management/commands/load_groups_from_config.py
Command to load or update groups from a configuration file.
Uses the Groups model and allows for dry-run and verbose logging.
Uses the configuration file named ./config/etl_config.yaml
"""
import os
import logging
import yaml

from django.core.management.base import BaseCommand, CommandError
from haunt_ops.models import Groups


logger = logging.getLogger("haunt_ops")  # Uses logger config from settings.py

class Command(BaseCommand):
    """
    start command
        python manage.py load_groups_from_config 
    or with custom config and dry-run
        python manage.py load_groups_from_config --config=config/custom_config.yaml --dry-run
    or with  custom config
        python manage.py load_groups_from_config --config=config/etl_config.yaml
    """

    help = "Load or update events from ivolunteers Groups page, uses configuration file named ./config/etl_config.yaml"

    def add_arguments(self, parser):
        parser.add_argument(
            "--config",
            type=str,
            default="config/etl_config.yaml",
            help="Path to YAML configuration file (default: config/etl_config.yaml) \n" \
            " With Custom config:\n --config=config/custom_config.yaml",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate updates without saving to database.",
        )

    def handle(self, *args, **kwargs):
        config_path = kwargs["config"]
        dry_run = kwargs["dry_run"]

        if not os.path.exists(config_path):
            logger.error("config file not found %s", config_path)
            raise CommandError(f"❌ Config file not found: {config_path}")

        try:
            with open(config_path, "r", encoding= "UTF-8") as file:
                config = yaml.safe_load(file)

            if not config:
                logger.error("Config file %s is empty or malformed.")
                raise CommandError(
                    f"❌ Config file {config_path} is empty or malformed."
                )

            groups_dict = config.get("groups",{})
            # Now split into two lists:
            group_names  = list(groups_dict.keys())
            created_count = 0
            updated_count = 0
            action = None
            total = 0

            # read each event in the web page
            for group in group_names:
                total += 1

                logger.info(
                    "Group Name: %s", group.strip() if group else "No Name")
                if dry_run:
                    group_exists = Groups.objects.filter(group_name=group).exists()
                    if group_exists:
                        updated_count += 1
                        action = "Updated"
                    else:
                        group_count += 1
                        action = "Created"
                    dry_run_action = (
                        "Would create" if not group_exists else "Would update"
                    )
                    message = f"{dry_run_action} group: {group}"
                    logging.info(message)

                else:
                    group_name, created = Groups.objects.update_or_create(
                        group_name=group,
                        defaults={
                            "group_name": group.strip(),
                        },
                    )
                    if created:
                        created_count += 1
                        action = "Created"
                    else:
                        updated_count += 1
                        action = "Updated"

                    message = f"{action} group: {group_name.id},{group_name}"
                    logging.info(message)
            summary = f"Processed: {total}, Created: {created_count}, Updated: {updated_count}" 
            logger.info("%s", summary)
            logger.info("group import from config file %s complete.", config_path)
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
