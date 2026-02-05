"""
# utils/time_string_utils.py
"""

import logging
from datetime import datetime, date
from django.utils.dateparse import parse_date, parse_datetime
from django.utils import timezone

logger = logging.getLogger("haunt_ops")

# ----------- Safe Date/Time Conversion Utilities -----------

def to_date(value):
    """
    Convert a string, date, or datetime to a `date` object.
    Accepts ISO, partial datetime, or various formats.
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        s = value.strip()
        # Handle full ISO format
        dt = parse_datetime(s)
        if not dt and has_timezone_offset(s):
            dt = parse_datetime(s + ":00")
        if dt:
            return dt.date()

        d = parse_date(s)
        if d:
            return d

        # Final fallback: try basic format
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            pass

    raise TypeError(f"Unsupported value for to_date: {value!r}")


def to_datetime(value, make_aware=True):
    """
    Convert various inputs to a `datetime` object (optionally timezone-aware).
    Accepts datetime, date, string.
    """
    if isinstance(value, datetime):
        if make_aware and timezone.is_naive(value):
            return timezone.make_aware(value)
        return value

    if isinstance(value, date):
        dt = datetime.combine(value, datetime.min.time())
        return timezone.make_aware(dt) if make_aware else dt

    if isinstance(value, str):
        s = value.strip()
        dt = parse_datetime(s)
        if not dt and has_timezone_offset(s):
            dt = parse_datetime(s + ":00")
        if not dt:
            try:
                dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                dt = None

        if dt:
            return timezone.make_aware(dt) if make_aware and timezone.is_naive(dt) else dt

    raise TypeError(f"Unsupported value for to_datetime: {value!r}")


def has_timezone_offset(s):
    """
    Returns True if the string ends with a space and a +/-HH timezone.
    e.g., "2026-01-28 15:37:57 -08"
    """
    return any(s.endswith(f" {tz}") for tz in [
        f"-{str(i).zfill(2)}" for i in range(13)
    ] + [
        f"+{str(i).zfill(2)}" for i in range(13)
    ])


# ----------- Fallback Utilities -----------

def default_if_blank(value, default_value=None, *, date_only=False):
    """
    If `value` is None, '', or [], return `default_value`.
    If default_value is a tuple, convert to datetime/date.
    """
    if value not in (None, "", [], {}):
        return value

    if isinstance(default_value, tuple):
        if date_only:
            return date(*default_value)
        else:
            dt = datetime(*default_value)
            return timezone.make_aware(dt)

    return default_value


# ----------- Special Parsers -----------

def convert_us_date(value):
    """
    Handle U.S. formatted date strings: MM/DD/YYYY, MM-DD-YYYY, etc.
    Returns a naive datetime.
    """
    clean = value.strip().replace("\xa0", " ").replace("\u200b", "")
    formats = ["%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y"]

    for fmt in formats:
        try:
            return datetime.strptime(clean, fmt)
        except ValueError:
            continue
    return None


def try_parse_us_date(value):
    """
    Try parsing a U.S. formatted date string into a naive datetime object.
    Supported formats:
        - MM/DD/YYYY
        - MM-DD-YYYY
        - MM/DD/YY
    Returns:
        datetime or None
    """
    if not value:
        return None

    clean_value = (
        str(value).strip()
                  .replace("\xa0", " ")   # non-breaking space
                  .replace("\u200b", "")  # zero-width space
    )

    date_formats = ["%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y"]

    for fmt in date_formats:
        try:
            return datetime.strptime(clean_value, fmt)
        except ValueError:
            continue

    return None

def safe_parse_datetime(value):
    """Alias to to_datetime with silent failure."""
    try:
        return to_datetime(value)
    except (TypeError, ValueError):
        logger.debug("Could not parse datetime from %r", value)
        return None

