"""
logging_utils.py
Utility functions for configuring logging in the haunt_ops application.
This module provides a function to set up a rotating logger for each script.
"""
import os
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

def _normalize_level(log_level):
    """Accept 'DEBUG' or logging.DEBUG, return an int level; fallback INFO."""
    if isinstance(log_level, int):
        return log_level
    if isinstance(log_level, str):
        lvl = getattr(logging, log_level.upper(), None)
        if isinstance(lvl, int):
            return lvl
    return logging.INFO


def configure_rotating_logger(script_file: str,
                              log_dir: str = "logs",
                              max_bytes=5 * 1024 * 1024,
                              log_level: str = "INFO",
                              backup_count=5) -> logging.Logger:
    """
    Configures a per-script rotating logger.

    Args:
        script_file (str): Typically __file__ from the calling script.
        log_dir (str): Directory to save log files.
        max_bytes (int): Maximum size of each log file before rotation.
        backup_count (int): How many rotated log files to keep.

    Returns:
        logging.Logger: Configured logger instance.
    """
    # Derive log filename
    command_name = os.path.splitext(os.path.basename(script_file))[0]
    timestamp = datetime.now().strftime("%m-%d-%Y_%H-%M-%S")
    log_filename = f"{command_name}_{timestamp}.log"

    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_filename)

    # Create and configure logger
    logger = logging.getLogger(f"{command_name}_logger")
    # Convert log level string to logging level constant
    level=_normalize_level(log_level)
    logger.setLevel(level)

    # Clear any existing handlers
    for h in logger.handlers[:]:
        logger.removeHandler(h)

    handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    logger.debug("Logging to: %s", log_path)

    return logger

