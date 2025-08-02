"""
Command to convert an Excel file to a CSV file.
This command reads an Excel file and writes its content to a CSV file.
It supports specifying the sheet to convert and handles both .xlsx and .xls formats.
"""

import pandas as pd
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """
    start command
        python manage.py convert_xls_report_to_csv --rin=path/to/input.xlsx --cout=path/to/output.csv --sheet=Sheet1
    or with sheet index
        python manage.py convert_xls_report_to_csv --rin=path/to/input.xlsx --cout=path/to/output.csv --sheet=0
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
            "--cout", "-out", type=str, required=True, help="Output CSV file path"
        )
        parser.add_argument(
            "--sheet", type=str, default="0", help="Sheet name or index (default: 0)"
        )

    def handle(self, *args, **options):
        input_path = options["rin"]
        output_path = options["cout"]
        sheet_name = options["sheet"]

        # Convert sheet_name to int if it's digit
        if sheet_name.isdigit():
            sheet_name = int(sheet_name)

        try:
            df = pd.read_excel(input_path, sheet_name=sheet_name)
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
