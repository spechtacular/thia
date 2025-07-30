from django.core.management.base import BaseCommand
# This script replaces column names in a CSV file based on a mapping defined in a YAML configuration file.
import pandas as pd
import yaml
import logging

logger = logging.getLogger('haunt_ops')


class Command(BaseCommand):
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
            with open("config/etl_config.yaml") as f:
                config = yaml.safe_load(f)

            csv_header_names = config.get("csv_header_name_mapping", {})
            logger.info(f"CSV Header Names Mapping: {csv_header_names}")  

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
                logger.error(f"Error: input csv file '{cin}' not found.")
            except Exception as e:
                logger.error(f"An error occurred reading input csv file {cin}: {e}")
            finally:
                logger.info(message)

        except FileNotFoundError:    
            logger.error("Error: config/config.yaml file not found.")
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file: {e}")
        except Exception as e:
            logger.error(f"An unexpected YAML error occurred: {e}")
