# bulk_load_users_from_ivolunteer.py


import os
import json
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd
import yaml
from django.utils.timezone import get_current_timezone
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import DatabaseError

from haunt_ops.services.sync_user import sync_user
from haunt_ops.utils.logging_utils import configure_rotating_logger


LOG_LEVELS = {
    "DEBUG": logging.DEBUG, "INFO": logging.INFO,
    "WARNING": logging.WARNING, "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL
}


class Command(BaseCommand):
    """
    Docstring for Command
    :doc Author: Your Name
    :doc Date: 2024-06-19
    :doc Version: 1.0
    :doc License: MIT
    :var Supports: Description
    :var Args: Description
    :var Returns: Description
    :var dict: Description
    :vartype dict: Mapped
    """
    help = "Insert or update iVolunteer users from a CSV or JSON file (with optional dry-run)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            required=True,
            help="Path to the input file (CSV or JSON).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate updates without saving to the database.",
        )
        parser.add_argument(
            "--log-level",
            dest="log_level",
            type=str,
            default="INFO",
            choices=LOG_LEVELS.keys(),
            help="Set the logging level (default: INFO).",
        )

    def handle(self, *args, **options):
        file_path = options["file"]
        dry_run = options["dry_run"]
        log_level = options["log_level"]

        if not os.path.exists(file_path):
            raise CommandError(f"❌ File not found: {file_path}")

        # Setup logging
        os.makedirs(settings.LOG_DIR, exist_ok=True)
        logger = configure_rotating_logger(
            __file__, log_dir=settings.LOG_DIR, log_level=LOG_LEVELS[log_level]
        )

        # Load column mapping
        try:
            with open("config/etl_config.yaml", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                column_mapping = config.get("json_field_name_mapping", {})
        except (FileNotFoundError, yaml.YAMLError) as e:
            raise CommandError(f"❌ Failed to load YAML config: {e}") from e

        logger.info("📂 Starting bulk user load.")
        logger.info("File: %s", file_path)
        logger.info("Dry run: %s", dry_run)

        ext = Path(file_path).suffix.lower()
        records = []
        total = 0
        created = 0
        updated = 0
        skipped = 0

        if dry_run:
            logger.info("🛑 Dry-run mode: no data was saved to the database.")
        try:
            if ext in [".xls", ".xlsx"]:
                df = pd.read_excel(file_path, dtype=str)
                df.rename(columns=column_mapping, inplace=True)
                records = df.fillna("").to_dict(orient="records")

            elif ext == ".csv":
                df = pd.read_csv(file_path, dtype=str)
                df.rename(columns=column_mapping, inplace=True)
                records = df.fillna("").to_dict(orient="records")

            elif ext == ".json":
                with open(file_path, encoding="utf-8") as f:
                    raw_records = json.load(f)
                records = []
                for r in raw_records:
                    mapped = map_json_fields(r, column_mapping, logger=logger)
                    if mapped:
                        records.append(mapped)
                    else:
                        skipped += 1


            else:
                raise CommandError(f"Unsupported file extension: {ext}")

            for idx, record in enumerate(records, start=1):
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
                except (RuntimeError, TypeError) as e:
                    # Only catch exceptions not already handled above, log and re-raise
                    logger.error("❌ Unexpected error processing record %s: %s",
                                 idx, str(e), exc_info=True)
                    raise

            logger.info("✅ Sync complete. Total: %s | Created: %s | Updated: %s | Skipped: %s ",
                        total, created, updated, skipped)
            if dry_run:
                logger.info("ℹ️ Dry run mode: no changes were saved.")

        except (pd.errors.ParserError, json.JSONDecodeError, ValueError, IOError) as e:
            raise CommandError(f"❌ Failed to load records: {e}") from e


def map_json_fields(record, mapping, logger=None):
    """
    Remap keys of a JSON record using mapping from etl_config.yaml.
    Supports:
      - Top-level key remapping
      - Flattening customFieldValues into individual keys
      - Joining group names into a single string

    Args:
        record (dict): Raw iVolunteer record from API
        mapping (dict): Key remapping from etl_config.yaml
        logger (Logger, optional): Logger instance for debug output

    Returns:
        dict: Mapped record with local column names


    Remap keys from iVolunteer API JSON into local format using etl_config.yaml.
    Also validates and converts fields like date_of_birth.
    """
    mapped = {}
    missing_required_fields = []
    raw_dob = None

    if logger:
        logger.debug("🔍 Mapping record ID: %s", record.get("id", "[no id]"))

    for key, value in record.items():
        # Simple mapping
        if key in mapping:
            local_key = mapping[key]
            mapped[local_key] = value
            if logger:
                logger.debug("➡️ Mapped field: '%s' → '%s' = %r", key, local_key, value)

            if local_key == "date_of_birth":
                raw_dob = value  # Save for special handling below

        elif key == "customFieldValues" and isinstance(value, list):
            for item in value:
                field_name = item.get("customField", {}).get("name")
                raw_value = item.get("value", "")
                if field_name:
                    local_key = mapping.get(field_name, field_name)
                    mapped[local_key] = raw_value
                    if logger:
                        logger.debug("🧩 Mapped customField: '%s' → '%s' = %r",
                                     field_name, local_key, raw_value)

        elif key == "groups":
            if isinstance(value, list):
                group_names = [g.get("name", "") for g in value if isinstance(g, dict)]
                mapped["groups"] = ", ".join(filter(None, group_names))
                if logger:
                    logger.debug("👥 Mapped groups list → 'groups' = %r", mapped["groups"])
            elif isinstance(value, str):
                mapped["groups"] = value
                if logger:
                    logger.debug("👥 Used string 'groups' = %r", value)

        else:
            if logger:
                logger.debug("❓ Unmapped field: %s = %r", key, value)

    # ✅ Convert dob from timestamp if needed
    if raw_dob is not None:
        try:
            if isinstance(raw_dob, int):  # From API timestamp
                dt = datetime.fromtimestamp(raw_dob / 1000.0, tz=get_current_timezone())
                mapped["date_of_birth"] = dt.isoformat(timespec="milliseconds")
                if logger:
                    logger.debug("🕐 Converted dob timestamp %s → date_of_birth = %s",
                                 raw_dob, mapped["date_of_birth"])
            elif isinstance(raw_dob, str) and raw_dob.isdigit():
                dt = datetime.fromtimestamp(int(raw_dob) / 1000.0, tz=get_current_timezone())
                mapped["date_of_birth"] = dt.isoformat(timespec="milliseconds")
                if logger:
                    logger.debug("🕐 Converted dob string timestamp %s → date_of_birth = %s",
                                 raw_dob, mapped["date_of_birth"])
        except Exception as e:
            if logger:
                logger.warning("⚠️ Failed to convert dob timestamp %r: %s", raw_dob, e)
            mapped["date_of_birth"] = None

    # ✅ Validate required fields
    required_fields = ["email", "first_name", "last_name", "date_of_birth"]
    for field in required_fields:
        if not mapped.get(field):
            missing_required_fields.append(field)

    if missing_required_fields:
        if logger:
            logger.warning("🚫 Skipping record: missing required fields %s", missing_required_fields)
        return None  # Signal to caller to skip this record

    if logger:
        logger.debug("✅ Final mapped record: %s", mapped)

    return mapped
