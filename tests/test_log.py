import logging
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytz

from waterly.log import MonthlyFileHandler


class TestMonthlyFileHandler(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.directory = Path(self.tempdir.name)
        self.timezone = pytz.timezone("America/Chicago")

    def timestamp(self, year, month, day, hour=0, minute=0, second=0):
        return self.timezone.localize(
            datetime(year, month, day, hour, minute, second)
        ).timestamp()

    def handler_at(self, timestamp, **kwargs):
        with patch("waterly.log.time.time", return_value=timestamp):
            handler = MonthlyFileHandler(self.directory, self.timezone, **kwargs)
        self.addCleanup(handler.close)
        return handler

    def write_at(self, handler, timestamp, message):
        with patch("waterly.log.time.time", return_value=timestamp):
            record = logging.LogRecord("test", logging.INFO, __file__, 0, message, (), None)
            handler.handle(record)

    def test_month_transition(self):
        handler = self.handler_at(self.timestamp(2026, 11, 30, 23, 59, 59))
        self.write_at(handler, self.timestamp(2026, 11, 30, 23, 59, 59), "November")
        self.write_at(handler, self.timestamp(2026, 12, 1), "December")
        self.assertEqual((self.directory / "app-2026-11.log").read_text(), "November\n")
        self.assertEqual((self.directory / "app-2026-12.log").read_text(), "December\n")
        self.assertEqual(handler.rolloverAt, self.timestamp(2027, 1, 1))

    def test_year_transition_and_append_existing_file(self):
        (self.directory / "app-2027-01.log").write_text("Existing\n")
        handler = self.handler_at(self.timestamp(2026, 12, 31))
        self.write_at(handler, self.timestamp(2027, 1, 1), "January")
        self.assertEqual(
            (self.directory / "app-2027-01.log").read_text(), "Existing\nJanuary\n"
        )

    def test_calendar_boundaries_include_leap_year_and_dst(self):
        for year, month in [(2026, 2), (2028, 2), (2026, 3), (2026, 11)]:
            with self.subTest(year=year, month=month):
                handler = self.handler_at(self.timestamp(year, month, 1))
                self.assertEqual(handler.rolloverAt, self.timestamp(year, month + 1, 1))

    def test_idle_months_are_skipped(self):
        handler = self.handler_at(self.timestamp(2026, 1, 1))
        self.write_at(handler, self.timestamp(2026, 4, 15), "April")
        self.assertEqual(Path(handler.baseFilename).name, "app-2026-04.log")
        self.assertEqual(handler.rolloverAt, self.timestamp(2026, 5, 1))
        self.assertFalse((self.directory / "app-2026-02.log").exists())

    def test_retention_preserves_other_files(self):
        for month in range(1, 13):
            (self.directory / f"app-2025-{month:02d}.log").touch()
        for name in ["services.log", "app-2025-01-01.log", "app-2025-00.log"]:
            (self.directory / name).touch()
        handler = self.handler_at(self.timestamp(2026, 1, 1))
        self.write_at(handler, self.timestamp(2026, 2, 1), "February")
        self.assertFalse((self.directory / "app-2025-01.log").exists())
        self.assertTrue((self.directory / "app-2025-02.log").exists())
        for name in ["services.log", "app-2025-01-01.log", "app-2025-00.log"]:
            self.assertTrue((self.directory / name).exists())


if __name__ == "__main__":
    unittest.main()
