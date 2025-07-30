# 

import os
import pandas as pd
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Converts an Excel file to a CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            '--rin', '-in',
            type=str,
            required=True,
            help='Input Excel file path (.xlsx or .xls)'
        )
        parser.add_argument(
            '--cout', '-out',
            type=str,
            required=True,
            help='Output CSV file path'
        )
        parser.add_argument(
            '--sheet',
            type=str,
            default='0',
            help='Sheet name or index (default: 0)'
        )

    def handle(self, *args, **options):
        input_path = options['rin']
        output_path = options['cout']
        sheet_name = options['sheet']

        # Convert sheet_name to int if it's digit
        if sheet_name.isdigit():
            sheet_name = int(sheet_name)

        try:
            df = pd.read_excel(input_path, sheet_name=sheet_name)
            df.to_csv(output_path, index=False, encoding='utf-8')
            self.stdout.write(self.style.SUCCESS(
                f"✅ Successfully converted '{input_path}' to '{output_path}'"
            ))
        except FileNotFoundError:
            raise CommandError(f"❌ File not found: {input_path}")
        except Exception as e:
            raise CommandError(f"❌ Error: {e}")

