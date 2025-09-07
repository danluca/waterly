#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#

import logging
import os

from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from .config import CONFIG, Settings, LOG_DIR

LOG_FILE = "app-%TIME%.log"

def init_logging(level: int = logging.INFO) -> None:
    """
    Initialize application-wide logging.

    - Logs to console and to a rotating file under LOG_DIR.
    - File name rotates by size and includes current year for convenience.
    - Safe to call multiple times; subsequent calls are ignored.
    """
    if logging.getLogger().handlers:
        return  # Already initialized

    os.makedirs(LOG_DIR, exist_ok=True)
    now = datetime.now(CONFIG[Settings.LOCAL_TIMEZONE])
    logfile = os.path.join(LOG_DIR, LOG_FILE.replace("%TIME%", now.strftime("%Y-%m")))

    fmt = "%(asctime)s %(levelname)s [%(threadName)s] [%(name)s] %(message)s"
    datefmt = "%b-%d %H:%M:%S"
    msfmt = "%s.%03d"

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter(fmt=fmt))
    ch.formatter.default_time_format = datefmt
    ch.formatter.default_msec_format = msfmt

    # File handler with rotation
    fh = TimedRotatingFileHandler(logfile, when='D', interval=30, backupCount=12, encoding='utf-8')  # Keep 12 months
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter(fmt=fmt))
    fh.formatter.default_time_format = datefmt
    fh.formatter.default_msec_format = msfmt

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(ch)
    root.addHandler(fh)
