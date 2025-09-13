#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#
from datetime import datetime

import pytz
import logging
from ..config import DEFAULT_TIMEZONE, CONFIG, Settings

def valid_timezone(tz: str) -> pytz.BaseTzInfo:
    logger = logging.getLogger(__name__)
    try:
        timezone = pytz.timezone(tz or "UTC")
    except pytz.UnknownTimeZoneError:
        timezone = DEFAULT_TIMEZONE
        logger.warning(f"Invalid timezone '{tz}' for pytz/TZDB version {pytz.VERSION}. Using default timezone {DEFAULT_TIMEZONE} instead.")
    return timezone


def now_local() -> datetime:
    return datetime.now(CONFIG[Settings.LOCAL_TIMEZONE])
