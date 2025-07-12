import pandas as pd
import os
import argparse
import sys


def convert_excel_to_csv(excel_filepath, csv_filepath, sheet_name=0):
    """
    Converts an Excel file (xlsx or xls) to a CSV file without opening it.

    Args:
        excel_filepath (str): Path to the Excel file.
        csv_filepath (str): Path to save the resulting CSV file.
        sheet_name (int or str, optional): Sheet to convert. Defaults to 0 (first sheet).
    """
    try:
        df = pd.read_excel(excel_filepath, sheet_name=sheet_name)
        df.to_csv(csv_filepath, index=False, encoding='utf-8')
        print(f"Successfully converted '{excel_filepath}' to '{csv_filepath}'")
    except FileNotFoundError:
        print(f"Error: Excel file '{excel_filepath}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

script_name = os.path.basename(__file__)

# retrieve parameters from command line options
parser = argparse.ArgumentParser(script_name)
parser.add_argument("-in", "--rin", help="input report file path", type=str, required=True)
parser.add_argument("-out", "--cout", help="output csv file path", type=str, required=True)

args = parser.parse_args()


convert_excel_to_csv(args.rin, args.cout)
