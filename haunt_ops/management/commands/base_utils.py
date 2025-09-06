"""
This module provides a base class for utility commands:
    1) A method to convert Excel files to CSV. The converted files
    have a csv extension instead of xls"
    2) A method to replace Excel column names based on a YAML
     mapping.The CSV file containing replaced headers are
     prefixed with 'replaced_' to indicate that the
     column names have been modified
     to be PostgreSQL friendly.
    3) A method to wait for a new file download to complete,
     rename it to "<command>-YYYYmmdd-HHMMSS<ext>" and return
     the new path. This is useful for commands that download files
     from ivolunteer and need to ensure the file is fully
     downloaded before processing.
"""

import os
import sys
import time
import shutil
import logging
from pathlib import Path
from datetime import datetime

import pandas as pd
import yaml
from django.core.management.base import BaseCommand, CommandError

# pylint: disable=no-member

logger = logging.getLogger("haunt_ops")


class BaseUtilsCommand(BaseCommand):
    """Base class for utility commands that handle file conversion and column renaming.
    Provides methods to convert Excel files to CSV and replace column names based on a YAML mapping.
    The converted CSV files are prefixed with 'replaced_' to indicate that the column names
    have been modified to be PostgreSQL friendly.
    """

    PREFIX = "replaced_"

    def convert_xls_to_csv(self, input_path):
        """Convert Excel (.xls/.xlsx) → CSV,  this takes
        run_selenium_participation_query_date.xls and
         creates a csv file run_selenium_participation_query_date.csv.
        The new csv file is input to replace_column_names and the original
            ivolunteer excel column
         names are replaced with postgresql friendly column names and the output file name is
           replaced_run_selenium_participation_query_date.csv
        The replaced_run_selenium_participation_query_date.csv file is input to the
           bulk_load_events_from_ivolunteer script to load ivolunteer data into
            the postgresql database
        """
        sheet_name = 0
        output_path = None

        try:
            df = pd.read_excel(input_path, sheet_name=sheet_name)
            output_path = Path(input_path).with_suffix(".csv")
            df.to_csv(output_path, index=False, encoding="utf-8")
            logger.info("✅ Converted %s → %s", input_path, output_path)

            # Chain into header‐replace step
            self.replace_column_names(output_path)

        except FileNotFoundError as exc:
            raise CommandError(f"❌ File not found: {input_path}") from exc
        except pd.errors.ParserError as e:
            raise CommandError(f"❌ Parser error: {e}") from e
        except pd.errors.XLRDError as e:
            raise CommandError(f"❌ Excel read error: {e}") from e
        except pd.errors.EmptyDataError as exc:
            raise CommandError(f"❌ No data in {input_path}") from exc
        except (OSError, IOError) as e:
            raise CommandError(f"❌ File I/O error: {e}") from e
        except Exception as e:
            raise CommandError(f"❌ Unexpected error: {e}") from e
        finally:
            if output_path and output_path.exists():
                logger.info("CSV ready at %s", output_path)
            else:
                logger.error("Failed to produce CSV from %s", input_path)

    def replace_column_names(self, csv_path):
        """Rename headers in a CSV based on config/etl_config.yaml mapping."""
        directory, filename = os.path.split(csv_path)
        out_name = self.PREFIX + filename
        out_path = os.path.join(directory, out_name)

        try:
            with open("config/etl_config.yaml", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            mapping = cfg.get("csv_header_name_mapping", {})
        except FileNotFoundError:
            logger.error("❌ config/etl_config.yaml not found")
            return
        except yaml.YAMLError as e:
            logger.error("❌ YAML parse error: %s", e)
            return

        try:
            df = pd.read_csv(csv_path, dtype=str)
            df = df.rename(columns=mapping)
            df.to_csv(out_path, index=False)
            logger.info("✅ Replaced columns, saved to %s", out_path)
        except FileNotFoundError:
            logger.error("❌ CSV not found: %s", csv_path)
        except Exception as e:
            logger.error("❌ Error processing CSV %s: %s", csv_path, e)

    def wait_for_new_download(self, download_dir, timeout=60, stable_secs=2):
        """
        Waits up to `timeout` seconds for a new file to appear and stabilize in size,
        renames it to "<command>-YYYYmmdd-HHMMSS<ext>" and returns the new path.
        - Ignores hidden temp items like .com.google.Chrome.*
        - Skips partials (.crdownload/.part/.tmp)
        - Handles races where a file disappears between listdir() and getsize()
        """
        tmp_exts = (".crdownload", ".part", ".tmp")

        def _is_final_candidate(path):
            name = os.path.basename(path)
            if name.startswith("."):          # e.g., .com.google.Chrome.*
                return False
            if not os.path.isfile(path):      # skip directories and gone files
                return False
            if name.endswith(tmp_exts):       # skip partials
                return False
            return True

        existing = set(os.listdir(download_dir))
        start = time.time()

        while time.time() - start < timeout:
            try:
                current = set(os.listdir(download_dir))
            except FileNotFoundError:
                time.sleep(0.25)
                continue

            added = current - existing
            if added:
                paths = [os.path.join(download_dir, f) for f in added]
                paths = [p for p in paths if _is_final_candidate(p)]

                if paths:
                    try:
                        newest = max(paths, key=os.path.getmtime)
                    except (FileNotFoundError, ValueError):
                        # file vanished or no paths; rescan
                        time.sleep(0.25)
                        continue

                    # wait for size to be stable for stable_secs total
                    last_size = None
                    stable_elapsed = 0.0
                    poll = 0.25
                    # cap polls by stable_secs but also bail out if file disappears
                    while stable_elapsed < stable_secs:
                        try:
                            size = os.path.getsize(newest)
                        except FileNotFoundError:
                            # It got finalized/renamed away; break to rescan
                            newest = None
                            break

                        if size == last_size and size > 0:
                            stable_elapsed += poll
                        else:
                            stable_elapsed = 0.0
                            last_size = size
                        time.sleep(poll)

                    if newest is None:
                        # file changed under us; rescan outer loop
                        time.sleep(0.25)
                        continue

                    # Build destination name
                    cmd = os.path.basename(sys.argv[1]) if len(sys.argv) > 1 else "download"
                    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                    ext = os.path.splitext(newest)[1]
                    new_name = f"{cmd}-{ts}{ext}"
                    new_path = os.path.join(download_dir, new_name)

                    # Avoid collisions
                    i = 1
                    while os.path.exists(new_path):
                        new_path = os.path.join(download_dir, f"{cmd}-{ts}-{i}{ext}")
                        i += 1

                    try:
                        shutil.move(newest, new_path)
                    except FileNotFoundError:
                        # Vanished between size check and move; rescan
                        time.sleep(0.25)
                        continue
                    except Exception as e:
                        logger.warning("⚠️ Move failed: %s", e)
                        return newest  # fall back to the original path

                    logger.info("✅ Download renamed to %s", new_path)
                    return new_path

        time.sleep(0.25)

        raise CommandError(f"❌No completed download in {timeout}s")


    def handle(self, *args, **options):
        """Base handle method to be overridden by subclasses."""
        raise NotImplementedError("Subclasses must implement the handle method.")
