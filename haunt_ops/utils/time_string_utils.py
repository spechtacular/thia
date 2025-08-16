"""
# utils/time_string_utils.py
"""
import logging
from datetime import datetime
from django.utils.dateparse import parse_date, parse_datetime
from django.utils import timezone

# pylint: disable=no-member
# pylint: disable=syntax-error
logger = logging.getLogger("haunt_ops")  # Uses logger config from settings.py

def to_date(value):
    """
    Convert various types of date inputs to a Python date object.
    Supports datetime objects, date objects, and date strings in various formats.
    """
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        s = value.strip()
        # try full datetime first (handles “YYYY-MM-DDTHH:MM:SS±HH:MM”)
        dt = parse_datetime(s)
        if dt is None:
            # common normalization: “ ... -08” → “… -08:00”
            if s.endswith((" -00"," -01"," -02"," -03"," -04"," -05"," -06"," -07"," -08"," -09"," -10"," -11"," -12",
                           " +00"," +01"," +02"," +03"," +04"," +05"," +06"," +07"," +08"," +09"," +10"," +11"," +12")):
                dt = parse_datetime(s + ":00")
        if dt:
            return dt.date()
        # fall back to just a date string (YYYY-MM-DD)
        d = parse_date(s)
        if d:
            return d
        # last resort if it’s like “YYYY-MM-DD HH:MM:SS”
        return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").date()
    raise TypeError("Unsupported edate type")

def default_if_blank(value, default_value=None, *, date_only=False):
    """
    Return `value` if set (non-empty), else return `default_value`.
    Special handling for date/datetime defaults:
      - If `date_only=True` and default_value is a (Y,M,D) tuple, returns datetime.date
      - If date_only=False and default_value is a (Y,M,D[,H,M,S]) tuple, returns tz-aware datetime
    """
    if value not in (None, "", []):
        return value

    if isinstance(default_value, tuple):
        if date_only:
            return datetime.date(*default_value)
        else:
            tz = timezone.get_current_timezone()
            return tz.localize(datetime.datetime(*default_value))
    return default_value

def convert_date_formats(value):
    """
    Convert a date string to a datetime object using multiple formats.
    Tries several common date formats and returns the first successful parse.
    """
    clean_start_raw = (
                        value.strip()                 # remove leading/trailing spaces
                                .replace("\xa0", " ") # replace non-breaking spaces
                                .replace("\u200b", "")# remove zero-width spaces, just in case
    )
    parsed_event_date = None
    # Try parsing with multiple formats
    # Common formats: "MM/DD/YYYY", "MM-DD-YYYY", "MM/DD/YY"
    date_formats = ["%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y"]
    for fmt in date_formats:
        try:
            parsed_event_date = datetime.strptime(clean_start_raw, fmt)
            break
        except ValueError:
            parsed_event_date = None
    return parsed_event_date

