"""
Docstring for haunt_ops.management.commands.run_api_users_query
"""


import os
import json
import logging
from datetime import datetime

import requests
import yaml

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import DatabaseError
from django.utils.timezone import get_current_timezone
from haunt_ops.services.sync_user import sync_user
from haunt_ops.utils.logging_utils import configure_rotating_logger

LOG_LEVELS = {
    "DEBUG": logging.DEBUG, "INFO": logging.INFO,
    "WARNING": logging.WARNING, "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL
}


class Command(BaseCommand):
    """
    Docstring for Command
    """
    help = "Call iVolunteer API for user data, map fields using etl_config.yaml, " \
                "and save cleaned JSON."

    def add_arguments(self, parser):
        parser.add_argument('--output-dir', type=str, default="haunt_ops/downloads",
                                help="Where to write the JSON file.")
        parser.add_argument('--log-level',
            dest="log_level",
            type=str,
            default="INFO",
            choices=LOG_LEVELS.keys(),
            help="Set the logging level (default: INFO).")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate updates without saving to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        log_level = options["log_level"]
        output_dir = options["output_dir"]

        # Setup logging
        os.makedirs(settings.LOG_DIR, exist_ok=True)
        logger = configure_rotating_logger(
            __file__, log_dir=settings.LOG_DIR, log_level=LOG_LEVELS[log_level]
        )


        self.stdout.write("📡 Starting iVolunteer API fetch...")
        logger.info("🔍 Querying iVolunteer API...")

        url = "https://the-haunt.ivolunteer.com/api/v1/db/participants"
        api_key = os.environ.get("IVOLUNTEER_API_KEY")
        if not api_key:
            logger.error("❌ Missing IVOLUNTEER_API_KEY in environment")
            raise CommandError("Missing IVOLUNTEER_API_KEY in environment")

        headers = {
            "accept": "application/json",
            "api-key": api_key,
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            logger.info("✅ API call successful")
            data = response.json()

            # Map fields from API using YAML mapping
            mapped_data = []
            total = 0
            created = 0
            updated = 0
            skipped = 0
            for idx, record in enumerate(data, start=1):
                mapped = self.map_fields(record, logger)
                if mapped is None:
                    logger.debug("⛔ Skipping record #%d due to validation errors", idx)
                    skipped += 1
                    continue
                mapped_data.append(mapped)

            if not mapped_data:
                raise CommandError("❌ No valid records found after mapping.")

            # Save mapped data
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(output_dir, f"ivolunteer_users_{timestamp}.json")

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(mapped_data, f, indent=2)

            logger.info("📦 JSON written to %s", output_path)
            # Sync users
            logger.info("🔄 Syncing users to database..."
            )
            for idx, record in enumerate(mapped_data, start=1):
                total += 1
                try:
                    created_flag = sync_user(record, logger=logger, dry_run=dry_run)
                    if created_flag is not None:
                        if created_flag:
                            created += 1
                        else:
                            updated += 1
                    else:
                        skipped += 1
                except (DatabaseError, ValueError, KeyError) as e:
                    logger.warning("⚠️ Error processing record %s: %s", idx, str(e))
                    skipped += 1
                except AttributeError as e:
                    logger.error("❌ Unexpected error processing record %s: %s",
                                 idx, str(e), exc_info=True)
                    skipped += 1

            logger.info("✅ Sync complete. Total: %s | Created: %s | Updated: %s | Skipped: %s ",
                        total, created, updated, skipped)
            if dry_run:
                logger.info("ℹ️ Dry run mode: no changes were saved.")

            logger.info("✅ Records processed: %d | Skipped: %d", len(mapped_data), skipped)
            self.stdout.write(f"✅ JSON written to: {output_path}")

        except requests.exceptions.RequestException as e:
            logger.error("❌ API error: %s", e)
            raise CommandError(str(e)) from e
        except (IOError, OSError, DatabaseError) as e:
            logger.error("❌ Unexpected error: %s", e, exc_info=True)
            raise CommandError(str(e)) from e

    def map_fields(self, record, logger=None):
        """
        Maps API JSON fields to local model fields using etl_config.yaml.
        Also flattens `customFieldValues` and joins `groups`.
        Skips invalid records by returning None.
        """
        try:
            with open("config/etl_config.yaml", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                mapping = config.get("json_field_name_mapping", {})
        except (FileNotFoundError, yaml.YAMLError) as e:
            raise CommandError(f"❌ Failed to load etl_config.yaml: {e}") from e

        mapped = {}
        raw_dob = None

        for key, value in record.items():
            normalized_key = key.strip()

            if normalized_key == "customFieldValues":
                for field in value:
                    field_name = field.get("customField", {}).get("name", "").strip()
                    field_value = field.get("value", "")
                    mapped_key = mapping.get(field_name, field_name)
                    mapped[mapped_key] = field_value

            elif normalized_key == "groups":
                group_names = [g.get("name") for g in value if isinstance(g, dict) and "name" in g]
                mapped_key = mapping.get("Member of Group(s)", "groups")
                mapped[mapped_key] = ", ".join(group_names)

            else:
                mapped_key = mapping.get(normalized_key, normalized_key)
                mapped[mapped_key] = value
                if mapped_key == "date_of_birth":
                    raw_dob = value

        # Convert dob from int or string timestamp to ISO date
        if raw_dob:
            try:
                if isinstance(raw_dob, int):
                    dt = datetime.fromtimestamp(raw_dob / 1000.0, tz=get_current_timezone())
                elif isinstance(raw_dob, str) and raw_dob.isdigit():
                    dt = datetime.fromtimestamp(int(raw_dob) / 1000.0, tz=get_current_timezone())
                else:
                    dt = None

                if dt:
                    mapped["date_of_birth"] = dt.date().isoformat()
                    if logger:
                        logger.debug("🕐 Converted dob %s → %s", raw_dob, mapped["date_of_birth"])
            except (ValueError, OSError, TypeError) as e:
                mapped["date_of_birth"] = None
                if logger:
                    logger.warning("⚠️ Failed to convert dob %r: %s", raw_dob, e)

        # Validate required fields
        required_fields = ["email", "first_name", "last_name", "date_of_birth"]
        missing = [f for f in required_fields if not mapped.get(f)]
        if missing:
            if logger:
                logger.warning("🚫 Skipping record due to missing fields: %s", missing)
            return None

        return mapped
