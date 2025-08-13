"""
# utils/time_string_utils.py
"""
import datetime
from django.utils.dateparse import parse_date, parse_datetime
from django.utils import timezone

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
