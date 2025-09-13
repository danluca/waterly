
#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#

import os
import pytz
import json
import threading

from typing import Any
from enum import StrEnum, Enum
from datetime import datetime
from pathlib import Path
from .model.units import UnitType
from .model.zone import Zone


def get_project_root():
    """
    Gets the root directory of the project by navigating two levels up from
    the current file's directory.

    :return: The root directory of the project as a pathlib.Path object.
    :rtype: Path
    """
    root_path = Path(__file__).parent.parent
    return root_path if root_path.exists() else None

#<editor-fold desc="Constants, Factory Settings">
# local timezone of the system - updated by the weather service
DEFAULT_TIMEZONE: pytz.BaseTzInfo = pytz.UTC

# Default location for weather (set to your coordinates, unless you happen to have a garden in the middle of the ocean, off west coast of Africa ;))
# - use https://www.google.com/maps and copy your coordinates
# E.g., Plus code: 2GJX+MW6 Plymouth, Minnesota
DEFAULT_LATITUDE = 0.0
DEFAULT_LONGITUDE = 0.0

# Pulse counter (GPIO)
PULSE_GPIO_PIN = 21
# Sensor spec: frequency(Hz) = 5.5 * flow(L/min)
WATER_FLOW_FREQUENCY_FACTOR = 5.5

# Paths
DATA_DIR = f"{get_project_root()}/data"
LOG_DIR = f"{get_project_root()}/logs"

# Zones and sensors IDs
ZONES: dict[int, Zone] = {}
RPI_ZONE_NAME = "RPI"   # must match core data entry for zone 4
#</editor-fold>

class Settings(StrEnum):
    """
    Enumeration for application settings.

    This class represents different configurable settings for an application as
    enumerable constants. Each setting has an associated default value. It provides
    a structured and type-safe way of defining application configuration options.

    Attributes:
    :ivar default: The default value associated with the setting.
    :type default: Any
    """
    HUMIDITY_TARGET_PERCENT = "humidity_target_percent", {"Z1":70.0, "Z2":70.0, "Z3":70.0}
    WATERING_START_TIME = "watering_start_time", {"value":"20:30"}                            # 8:30pm
    WATERING_MAX_MINUTES_PER_ZONE = "watering_max_minutes_per_zone", {"value":10}
    LAST_WATERING_DATE = "last_watering_date", {"value":None}
    RAIN_CANCEL_PROBABILITY_THRESHOLD = "rain_cancel_probability_threshold", {"value":50.0}   # 50%
    UNITS = "units", {"value":UnitType.IMPERIAL}
    WEATHER_CHECK_INTERVAL_SECONDS = "weather_check_interval_seconds", {"value":6*3600}       # 6 hours
    WEATHER_CHECK_PRE_WATERING_SECONDS = "weather_check_pre_watering_seconds", {"value":30*60}    # 30 minutes
    WEATHER_LAST_CHECK_TIMESTAMP = "weather_last_check_timestamp", {"value":None}
    SENSOR_READ_INTERVAL_SECONDS = "sensor_read_interval_seconds", {"value":60*10}            # 10 minutes
    MINIMUM_SENSOR_HUMIDITY_PERCENT = "minimum_sensor_humidity_percent", {"Z1":30.0, "Z2":30.0, "Z3":30.0}
    TREND_MAX_SAMPLES = "trend_max_samples", {"value":3000}                                  # ~ 1 month worth of samples
    LOCAL_TIMEZONE = "local_timezone", {"value":DEFAULT_TIMEZONE.zone}
    LOCATION = "location", {"longitude":DEFAULT_LONGITUDE, "latitude":DEFAULT_LATITUDE}
    GARDENING_SEASON = "gardening_season", {"start": "03-31", "stop": "10-31"}  # MM-DD (inclusive)

    def __new__(cls, value: str, default: dict = None):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.default = default
        return obj

# Defaults
DEFAULT_SETTINGS: dict[str, Any] = {item.name: item.default for item in Settings}

#<editor-fold desc="JSON Serialization">
def __json_datetime_encoder(dt:datetime) -> dict[str, str]:
    """
    Encodes a datetime object into a dictionary format suitable for JSON serialization.
    The dictionary contains the type of the object, its ISO 8601 string representation,
    and the time zone information if available.

    :param dt: The datetime object that needs to be encoded.
    :type dt: datetime
    :return: A dictionary containing the encoded datetime data with keys "__type__", "iso", and "tz".
    :rtype: dict[str, str]
    """
    return {
        "__type__": "datetime",
        "iso": dt.isoformat(),
        "tz": dt.tzinfo.__str__() if dt.tzinfo else "UTC"
    }

def __json_datetime_decoder(obj:dict[str, str]) -> datetime | dict[str, str]:
    """
    Decodes a JSON object into a datetime object or returns the object if it is not a
    datetime representation.

    This function checks if the object represents a datetime by looking for a specific key "__type__" with the
    value "datetime". If this key is absent or has a different value, the function simply returns the input object
    to allow further processing from within the object hook.
    Otherwise, it attempts to parse the datetime information using the provided timezone information or the default system
    timezone defined above DEFAULT_TIMEZONE.

    :param obj: A dictionary containing potential datetime representation.
    :type obj: dict[str, str]
    :return: A datetime object if the input is a valid datetime representation; otherwise, the original dictionary is returned.
    :rtype: datetime | dict[str, str]
    """
    if "__type__" not in obj or obj["__type__"] != "datetime":
        return obj
    # noinspection PyBroadException
    try:
        tz = pytz.timezone(obj["tz"]) if obj["tz"] else DEFAULT_TIMEZONE
    except Exception:
        tz = DEFAULT_TIMEZONE
    return tz.localize(datetime.fromisoformat(obj["iso"]).replace(tzinfo=None))

def _json_default(o) -> dict[str, Any]:
    """
    Encodes an object to a JSON-compatible format. This function is used to provide a default
    serialization behavior for config objects that are not inherently serializable by Python's
    `json` library.

    :param o: An object to serialize. Can include datetime instances, Enum instances, or other
              arbitrary objects with attributes or string representations.
    :type o: Any

    :return: A JSON-compatible representation of the object. For datetime objects, it
             produces an ISO string representation. For Enum instances, it provides
             their values. Other objects fallback to their `__dict__` attribute or
             string representation.
    :rtype: Union[str, dict]
    """
    # Datetime -> ISO string
    if isinstance(o, datetime):
        return __json_datetime_encoder(o)

    # Enum -> value
    # noinspection PyBroadException
    try:
        if isinstance(o, Enum):
            return {"value": o.value}
    except Exception:
        pass

    if isinstance(o, dict):
        return o

    # Generic object: use its __dict__ as a last resort
    if hasattr(o, "__dict__"):
        return o.__dict__

    # Fallback to string representation
    return {"value": str(o)}

def _json_object_hook(obj: dict) -> Any:
    """
    Transforms a JSON-decoded dictionary by applying custom decoding logic. This
    helper function is typically used in JSON deserialization processes to handle
    specific data types, such as datetime objects.

    :param obj: The JSON-decoded dictionary object to be processed.
    :type obj: dict
    :return: Partially transformed object after applying decoding, which could be a dictionary or a datetime object.
    :rtype: Any
    """
    if not isinstance(obj, dict):
        return obj

    obj = __json_datetime_decoder(obj)
    if isinstance(obj, datetime):
        return obj
    return obj

#</editor-fold>

class AppConfig:
    """
    Handles configuration settings for the application, providing access to settings
    and persisting configurations to a file.

    The class is used to manage application settings, enabling storage, retrieval,
    and persistence of configurations. It ensures proper marshaling and unmarshaling
    of settings values based on their types and handles file-based persistence
    with thread safety. When no existing configuration file is found, it initializes
    settings with default values.

    :ivar settings: A dictionary holding the application's configuration values.
    :type settings: dict[str, Any]
    """
    def __init__(self):
        # If no config provided, use factory defaults
        self._lock = threading.RLock()
        self.settings: dict[str, Any] = DEFAULT_SETTINGS.copy()
        self._settings_file = f"{DATA_DIR}/settings.json"
        self._persist_callback = None  # injected persistence (e.g., DB) to avoid circular import

    def __getitem__(self, arg: Settings) -> Any:
        if arg.name not in self.settings:
            self.settings[arg.name] = arg.default
        return AppConfig.__unmarshal__(arg, self.settings.get(arg.name))

    def __setitem__(self, arg: Settings, value: Any):
        self.settings[arg.name] = AppConfig.__marshal__(arg, value)
        # Defer cross-module persistence via injected callback to avoid circular imports
        cb = self._persist_callback
        if callable(cb):
            # noinspection PyBroadException
            try:
                cb(arg, self.settings[arg.name])
            except Exception:
                # Do not let persistence failures break config assignment
                pass

    def save_to_file(self):
        os.makedirs(os.path.dirname(self._settings_file), exist_ok=True)
        self._write_to_file()

    def read_from_file(self):
        os.makedirs(os.path.dirname(self._settings_file), exist_ok=True)
        if not self._read_from_file():
            self._write_to_file()   # when read from the backing file fails, write the defaults as starting point

    def init_item(self, item: Settings, value: dict[str, Any] = None):
        self.settings[item.name] = value if value else item.default

    def set_persist_callback(self, callback):
        """
        Inject a persistence callback with signature (setting: Settings, marshaled_value: dict[str, Any]) -> None
        to persist changes outside this module (e.g., database).
        """
        with self._lock:
            self._persist_callback = callback

    @staticmethod
    def __unmarshal__(arg: Settings, value: dict[str, Any]) -> Any:
        match arg:
            case Settings.LOCAL_TIMEZONE:
                return pytz.timezone(value["value"])
            case _:
                if "value" in value:
                    return value["value"]
                elif "__type__" in value:
                    return _json_object_hook(value)
                else:
                    return value

    @staticmethod
    def __marshal__(arg: Settings, value: Any) -> dict[str, Any]:
        match arg:
            case Settings.LOCAL_TIMEZONE:
                if isinstance(value, pytz.BaseTzInfo):
                    return {"value": value.zone}
                elif isinstance(value, dict):
                    return value
                else:
                    return {"value": value}
            case _:
                if isinstance(value, dict) and "value" in value and len(value) == 1:
                    return value
                else:
                    return _json_default(value)

    def _read_from_file(self) -> bool:
        with self._lock:
            if not os.path.exists(self._settings_file):
                return False
            # noinspection PyBroadException
            try:
                with open(self._settings_file, "r") as f:
                    self.settings = json.load(f, object_hook=_json_object_hook)
                return True
            except Exception:
                return False

    def _write_to_file(self) -> None:
        with self._lock:
            tmp_path = self._settings_file + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, default=_json_default)
            os.replace(tmp_path, self._settings_file)

CONFIG = AppConfig()