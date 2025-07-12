# map key names passed from ivolunteer to proper json key names
import argparse
import sys
import pandas as pd


import yaml

def read_yaml_config(config_file_path):
    # Reads a YAML configuration file and returns a dictionary.
    try:
        with open(config_file_path, 'r') as file:
            config = yaml.safe_load(file)
            return config
    except FileNotFoundError:
        print(f"Error: Config File not found at {config_file_path}")
        return None
    except yaml.YAMLError as e:
        print(f"Error parsing YAML Config file: {e}")
        return None


def replace_column_names(cin,name_mapping,cout):
    try:
        dataframe = pd.read_csv(cin,header=0,dtype=str);
        dataframe = dataframe.rename(columns=name_mapping)
        dataframe.to_csv(cout, index=False) # Overwrite the original CSV
        print("Column names replaced successfully.")
        return dataframe
    except FileNotFoundError:
        print(f"Error: csv file '{cin}' not found.")
        return None
    except Exception as e:
        print(f"An error occurred reading csv file {cin}: {e}")
        return None




# retrieve parameters from command line options
parser = argparse.ArgumentParser("replace_header_names")
parser.add_argument("-in", "--cin", help="input csv file path", type=str, required=True)
parser.add_argument("-out", "--cout", help="output csv file path", type=str, required=True)
parser.add_argument("-y", "--yaml", help="yaml configuration file path", type=str, required=True)

args = parser.parse_args()

config_data = read_yaml_config(args.yaml)
if config_data is None:
    sys.exit(1)
else:
    # Access CSV header name key value pairs:
    csv_header_names = config_data.get("csv_header_name_mapping", {})
    print(f"CSV Header Names Mapping: {csv_header_names}")

    # read the csv file from ivolunteer
    dataframe = replace_column_names(args.cin, csv_header_names, args.cout)
    if dataframe is None:
        print(f"dataframe read of csv file {args.cin} failed")
        sys.exit(1)
