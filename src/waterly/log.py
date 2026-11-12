#  MIT License
#
#  Copyright (c) by Dan Luca. All rights reserved.
#

import logging
import os
import re
import time

from logging.handlers import BaseRotatingHandler
from datetime import datetime
from pathlib import Path
from .config import CONFIG, Settings, LOG_DIR

LOG_FILE = "app-%TIME%.log"


class MonthlyFileHandler(BaseRotatingHandler):
    """Switch monthly files on the first write after local midnight on the 1st."""

    def __init__(self, directory, timezone, backupCount=12):
        self.directory = Path(directory).resolve()
        self.timezone = timezone
        self.backupCount = backupCount
        filename = self._set_period(time.time())
        super().__init__(filename, mode="a", encoding="utf-8")

    def _set_period(self, timestamp):
        now = datetime.fromtimestamp(timestamp, self.timezone)
        year, month = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
        # Localize the new date separately so DST changes between months are respected.
        boundary = self.timezone.localize(datetime(year, month, 1))
        self.rolloverAt = boundary.timestamp()
        return str(self.directory / LOG_FILE.replace("%TIME%", now.strftime("%Y-%m")))

    def shouldRollover(self, record):
        return time.time() >= self.rolloverAt

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        self.baseFilename = self._set_period(time.time())
        self.stream = self._open()

        # Keep up to 12 previous monthly files, plus the active month.
        if self.backupCount > 0:
            backups = sorted(
                path for path in self.directory.glob("app-*.log")
                if re.fullmatch(r"app-\d{4}-(0[1-9]|1[0-2])\.log", path.name)
                and str(path) < self.baseFilename and path.is_file()
            )
            for path in backups[:-self.backupCount]:
                path.unlink()


def init_logging(level: int = logging.INFO) -> None:
    """
    Initialize application-wide logging.

    - Logs to console and to a rotating file under LOG_DIR.
    - File name follows the calendar month in the configured local timezone.
    - Safe to call multiple times; subsequent calls are ignored.
    """
    if logging.getLogger().handlers:
        return  # Already initialized

    os.makedirs(LOG_DIR, exist_ok=True)

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
    fh = MonthlyFileHandler(LOG_DIR, CONFIG[Settings.LOCAL_TIMEZONE], backupCount=12)
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter(fmt=fmt))
    fh.formatter.default_time_format = datefmt
    fh.formatter.default_msec_format = msfmt

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(ch)
    root.addHandler(fh)
