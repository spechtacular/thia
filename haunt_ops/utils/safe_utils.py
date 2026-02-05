"""
Utility functions for safe type conversions.
Includes safe_strip, safe_int, safe_float, safe_bool, safe_parse_datetime.
"""



def safe_strip(value) -> str:
    """
    Safely convert a value to a trimmed string.
    None → ""
    """
    return str(value).strip() if value is not None else ""


def safe_int(value, default=0) -> int:
    """
    Safely convert value to int.
    Handles floats in strings and None.
    """
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_float(value, default=0.0) -> float:
    """
    Safely convert value to float.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_bool(value) -> bool:
    """
    Convert common truthy/falsey representations to boolean.
    Accepts: True, "true", "yes", "1", "y", "i agree"
    """
    if isinstance(value, bool):
        return value

    if value is None:
        return False

    val = str(value).strip().lower()
    return val in {"true", "1", "yes", "y", "i agree"}
