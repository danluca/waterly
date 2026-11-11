import os
import sys
import unittest
from unittest.mock import MagicMock
from datetime import datetime, UTC

# Mock hardware-specific modules not available on Windows test environment
sys.modules['gpiozero'] = MagicMock()
sys.modules['modbus_tk'] = MagicMock()
sys.modules['modbus_tk.defines'] = MagicMock()
sys.modules['modbus_tk.modbus_rtu'] = MagicMock()
sys.modules['serial'] = MagicMock()

from waterly.config import AppConfig, Settings, CONFIG, RPI_ZONE_NAME
from waterly.storage import db, init_db
from waterly.model.units import Unit
from waterly.web import app

class TestSensorsAPI(unittest.TestCase):
    def setUp(self):
        init_db()

    def test_latest_sensors_empty_weather(self):
        CONFIG[Settings.WEATHER_LAST_CHECK_TIMESTAMP] = None
        with app.test_client() as client:
            response = client.get("/api/latest/sensors")
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn("weather", data)
            self.assertIsInstance(data["weather"]["prev12"], dict)
            self.assertIsInstance(data["weather"]["next12"], dict)
            self.assertIsNone(data["weather"]["forecast_time"])

    def test_latest_sensors_with_weather_forecast_and_timestamp(self):
        CONFIG[Settings.WEATHER_LAST_CHECK_TIMESTAMP] = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
        with db() as conn:
            now_ms = int(datetime.now(UTC).timestamp() * 1000)
            # Insert next 12h forecast row
            conn.execute("""
                INSERT INTO weather(collected_at_utc, forecast_ts_utc, tz, tag, temperature_2m, temperature_unit,
                                   precipitation_probability, precipitation, precipitation_unit, soil_moisture_1_to_3cm,
                                   moisture_unit, surface_pressure, pressure_unit)
                VALUES (?, ?, 'UTC', 'forecast', 55.0, '°F', 10.0, 0.0, 'inch', 0.25, 'm³/m³', 1013.25, 'hPa')
            """, (now_ms, now_ms + 3600 * 1000))

        with app.test_client() as client:
            response = client.get("/api/latest/sensors")
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn("weather", data)
            self.assertEqual(data["weather"]["next12"]["soil_moisture_min"], 25.0)
            self.assertEqual(data["weather"]["next12"]["soil_moisture_max"], 25.0)
            self.assertEqual(data["weather"]["next12"]["soil_moisture_unit"], "%")
            self.assertIsNotNone(data["weather"]["forecast_time"])

if __name__ == "__main__":
    unittest.main()
