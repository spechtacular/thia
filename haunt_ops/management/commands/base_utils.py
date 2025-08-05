# haunt_ops/management/commands/base_utils.py

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

logger = logging.getLogger('haunt_ops')


class BaseUtilsCommand(BaseCommand):
    PREFIX = "replaced_"

    def convert_xls_to_csv(self, input_path):
        """Convert Excel (.xls/.xlsx) → CSV,  this takes run_selenium_participation_query_date.xls and 
             creates a csv file run_selenium_participation_query_date.csv.
            The new csv file is input to replace_column_names and the original ivolunteer excel column
             names are replaced with postgresql friendly column names and the output file name is
               replaced_run_selenium_participation_query_date.csv
            The replaced_run_selenium_participation_query_date.csv file is input to the 
               bulk_load_events_from_ivolunteer script to load ivolunteer data into the postgresql database
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
        except pd.errors.EmptyDataError:
            raise CommandError(f"❌ No data in {input_path}")
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
        """
        existing = set(os.listdir(download_dir))
        tmp_exts = (".crdownload", ".part", ".tmp")

        start = time.time()
        while time.time() - start < timeout:
            added = set(os.listdir(download_dir)) - existing
            candidates = [f for f in added if not f.endswith(tmp_exts)]
            if candidates:
                paths = [os.path.join(download_dir, f) for f in candidates]
                newest = max(paths, key=os.path.getmtime)

                # wait for size to stabilize
                last_size = -1
                stable_start = time.time()
                while time.time() - stable_start < stable_secs:
                    size = os.path.getsize(newest)
                    if size == last_size:
                        # build new name
                        cmd = sys.argv[1]
                        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                        ext = os.path.splitext(newest)[1]
                        new_name = f"{cmd}-{ts}{ext}"
                        new_path = os.path.join(download_dir, new_name)

                        # avoid collisions
                        i = 1
                        while os.path.exists(new_path):
                            new_path = os.path.join(download_dir, f"{cmd}-{ts}-{i}{ext}")
                            i += 1

                        try:
                            shutil.move(newest, new_path)
                        except Exception as e:
                            logger.warning("⚠️ Move failed: %s", e)
                            return newest

                        logger.info("✅ Download renamed to %s", new_path)
                        return new_path

                    last_size = size
                    time.sleep(0.5)
            time.sleep(0.5)

        raise CommandError(f"❌No completed download in {timeout}s")

