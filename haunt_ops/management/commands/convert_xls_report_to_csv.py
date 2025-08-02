"""
Command to convert an Excel file to a CSV file.
This command reads an Excel file and writes its 
    content to a file of the same name with a csv extension.
It supports specifying the sheet to convert and handles both .xlsx and .xls formats.
"""
from pathlib import Path
import pandas as pd
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """
    start command
        python manage.py convert_xls_report_to_csv --rin=path/to/input.xlsx  
    or with optional sheet name or index
        python manage.py convert_xls_report_to_csv --rin=path/to/input.xlsx --sheet=Sheet1
    or with sheet index
        python manage.py convert_xls_report_to_csv --rin=path/to/input.xlsx --cout=path/to/output.csv --sheet=Sheet1
    """

    help = "Converts an Excel file to a CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--rin",
            "-in",
            type=str,
            required=True,
            help="Input Excel file path (.xlsx or .xls)",
        )
        
        parser.add_argument(
            "--sheet", type=str, default="0", help="Sheet name or index (default: 0)"
        )

    def handle(self, *args, **options):
        input_path = options["rin"]
        sheet_name = options["sheet"]

        # Convert sheet_name to int if it's digit
        if sheet_name.isdigit():
            sheet_name = int(sheet_name)

        try:
            df = pd.read_excel(input_path, sheet_name=sheet_name)
            output_path = Path(input_path).with_suffix(".csv")
            df.to_csv(output_path, index=False, encoding="utf-8")
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Successfully converted '{input_path}' to '{output_path}'"
                )
            )
        except FileNotFoundError as exc:
            raise CommandError(f"❌ File not found: {input_path}") from exc
        except Exception as e:
            raise CommandError(f"❌ Error: {e}") from e
