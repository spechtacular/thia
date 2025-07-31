""" 
haunt_ops/management/commands/replace_column_names.py
Command to replace ivolunteer header names with Postgresql friendly column names and 
save to a new CSV file.
This command reads a configuration file for the mapping of old column names to new ones.
It supports dry-run mode to simulate changes without saving.
"""
from django.core.management.base import BaseCommand
# This script replaces column names in a CSV file based on a mapping defined in a YAML configuration file.
import pandas as pd
import yaml
import logging

logger = logging.getLogger('haunt_ops')


class Command(BaseCommand):
    """        
        start command
            python manage.py replace_column_names --dry-run --cin=path/to/input.csv --cout=path/to/output.csv
        or without dry-run
            python manage.py replace_column_names --cin=path/to/input.csv --cout=path/to/output.csv
        This command replaces ivolunteer header names with Postgresql friendly column names and saves to a new CSV file.
    """
    # Define the help text for the command
    help = 'Replace ivolunteer header names with Postgresql friendly column names and save to a new CSV file.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Simulate conversion without saving.')
        parser.add_argument("--cin", help="input csv file path", type=str, required=True)
        parser.add_argument("--cout", help="output csv file path", type=str, required=True)

    def handle(self, *args, **kwargs):
        dry_run = kwargs['dry_run']
        cin = kwargs['cin']
        cout = kwargs['cout']   

        try:
            with open("config/etl_config.yaml", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            csv_header_names = config.get("csv_header_name_mapping", {})
            logger.info("CSV Header Names Mapping: %s", csv_header_names)  

            message = ""
            try:
                dataframe = pd.read_csv(cin,header=0,dtype=str);
                dataframe = dataframe.rename(columns=csv_header_names)
                if dry_run:
                    message="Dry run mode: No changes will be saved."
                else:
                    # Save the modified dataframe to the specified output file
                    dataframe.to_csv(cout, index=False) 
                    message=f"Column names replaced and saved to {cout}."
            except FileNotFoundError:
                logger.error("Error: input csv file '%s' not found.", cin)
                message = f"Error: input csv file '{cin}' not found."
            except pd.errors.ParserError as e:
                logger.error("Parser error reading input csv file %s: %s", cin, e)
                message = f"Parser error reading input csv file {cin}: {e}"
            except UnicodeDecodeError as e:
                logger.error("Unicode decode error reading input csv file %s: %s", cin, e)
                message = f"Unicode decode error reading input csv file {cin}: {e}"
            finally:
                logger.info(message)

        except FileNotFoundError:    
            logger.error("Error: config/config.yaml file not found.")
        except yaml.YAMLError as e:
            logger.error("Error parsing YAML file: %s", e)
        except (OSError, IOError) as e:
            logger.error("File operation error occurred: %s", e)
        except Exception as e:
            logger.error("An unexpected error occurred: %s", e)
