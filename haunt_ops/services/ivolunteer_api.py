import os
import json
import csv
import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from haunt_ops.services.sync_user import sync_user_from_dict
from haunt_ops.utils.logging_utils import configure_rotating_logger

LOG_LEVELS = {
    "DEBUG": logging.DEBUG, "INFO": logging.INFO,
    "WARNING": logging.WARNING, "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL
}


class Command(BaseCommand):
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

        logger.info("📂 Starting bulk user load.")
        logger.info("File: %s", file_path)
        logger.info("Dry run: %s", dry_run)

        ext = Path(file_path).suffix.lower()
        records = []

        try:
            if ext == ".csv":
                with open(file_path, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    records = list(reader)
                    logger.info("📄 Detected CSV format: %d rows", len(records))
            elif ext == ".json":
                with open(file_path, encoding="utf-8") as f:
                    records = json.load(f)
                    if not isinstance(records, list):
                        raise CommandError("❌ JSON must contain a list of records.")
                    logger.info("🧾 Detected JSON format: %d records", len(records))
            else:
                raise CommandError("❌ Unsupported file type. Use .csv or .json")
        except Exception as e:
            raise CommandError(f"❌ Failed to load file: {e}")

        created = updated = skipped = 0

        for i, record in enumerate(records, start=1):
            try:
                user = sync_user_from_dict(record, dry_run=dry_run)
                if user:
                    if user._state.adding:
                        created += 1
                    else:
                        updated += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.warning("⚠️ Error processing record %d: %s", i, e)
                skipped += 1

        logger.info("✅ Finished processing %d users", len(records))
        logger.info("🆕 Created: %d", created)
        logger.info("🔁 Updated: %d", updated)
        logger.info("⏭️ Skipped: %d", skipped)

        if dry_run:
            logger.info("🛑 Dry-run mode: no data was saved to the database.")
