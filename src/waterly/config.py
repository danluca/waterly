import datetime as dt
import pytz
from .zone import Zone

# Default watering policy
WATERING_START_LOCALTIME = dt.time(20, 30)  # 8:30 PM
WATERING_MAX_MINUTES_PER_ZONE = 10
HUMIDITY_TARGET_PERCENT = 70.0

# Weather policy
RAIN_CANCEL_PROBABILITY_THRESHOLD = 0.50    # 50%
WEATHER_CHECK_INTERVAL_SECONDS = 6 * 3600   # 6 hours

# Pulse counter (GPIO)
PULSE_GPIO_PIN = 21
# Sensor spec: frequency(Hz) = 5.5 * flow(L/min)
WATER_FLOW_FREQUENCY_FACTOR = 5.5

# Sensor reading policy
SENSOR_READ_INTERVAL_SECONDS = 60 * 10      # 10 minutes

# Storage paths
DATA_DIR = "data"
LOG_DIR = "logs"
SETTINGS_FILE = f"{DATA_DIR}/settings.json"
TRENDS_FILE = f"{DATA_DIR}/%YEAR%/trends.json"
TREND_MAX_SAMPLES = 52000   # ~ 1 year worth of samples
LOG_MAX_EVENTS = 100000     # ~ 1 year worth of events

# Web
HTTP_PORT:int = 8080

# Zones and sensors IDs
ZONES = {
    1: Zone("Z1", "Zone 1", 0x0A, None, 16),
    2: Zone("Z2", "Zone 2", 0x0B, 0x20, 19),
    3: Zone("Z3", "Zone 3", 0x0C, None, 20),
}
# local timezone of the system - updated by the weather service
DEFAULT_TIMEZONE: pytz.BaseTzInfo = pytz.UTC
LOCAL_TIMEZONE: pytz.BaseTzInfo = DEFAULT_TIMEZONE

# Location for weather (set to your coordinates)
LATITUDE = 45.0341769
LONGITUDE = -93.4641572
