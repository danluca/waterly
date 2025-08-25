import json
import os
import threading
import src.waterly.config as config
from datetime import datetime, UTC, tzinfo
from typing import Any, Dict
from enum import StrEnum, Enum

from .config import SETTINGS_FILE, TRENDS_FILE, HUMIDITY_TARGET_PERCENT, WATERING_START_LOCALTIME, \
    WATERING_MAX_MINUTES_PER_ZONE, RAIN_CANCEL_PROBABILITY_THRESHOLD, ZONES, TREND_MAX_SAMPLES
from .trend import TrendSet, Measurement, Trend

def _get_current_year() -> str:
    """
    Gets the current year as a string.

    This function retrieves the current year using the system's date and time,
    formats it as a string, and returns it.

    :return: The current year formatted as a string.
    :rtype: str
    """
    return str(datetime.now().year)

def write_text_file(path: str, content: str) -> None:
    """
    Write the given text to 'path', overwriting if it exists.
    Uses a temporary file + atomic replace to avoid partial writes.
    Creates parent directories if they don't exist.
    """
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)

    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        # Atomic on POSIX; safe overwrite on Windows
        os.replace(tmp_path, path)
    finally:
        # Best-effort cleanup if something went wrong before replace
        # noinspection PyBroadException
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

#<editor-fold desc="JSON serialization helpers">
def _json_default(o):
    """
    JSON serializer for custom types used in this project.
    """
    # Datetime -> ISO string
    if isinstance(o, datetime):
        return o.isoformat()

    # Measurement
    if (Measurement and isinstance(o, Measurement)) or o.__class__.__name__ == "Measurement":
        time_val = getattr(o, "time", None)
        time_iso = getattr(o, "time_iso", None)
        return {
            "time": time_iso() if callable(time_iso) else (time_val.isoformat() if time_val else None),
            "value": getattr(o, "value", None),
        }

    # Trend
    if Trend and isinstance(o, Trend):
        return {
            "name": getattr(o, "name", None),
            "unit": getattr(o, "unit", None),
            "maxSamples": getattr(o, "maxSamples", None),
            "data": [_json_default(m) for m in getattr(o, "data", [])],
        }

    # TrendSet
    if TrendSet and isinstance(o, TrendSet):
        return {
            "name": getattr(o, "name", None),
            "trends": {z: _json_default(t) for z, t in getattr(o, "trends", {}).items()},
        }

    # Enum -> value
    # noinspection PyBroadException
    try:
        if isinstance(o, Enum):
            return o.value
    except Exception:
        pass

    # Generic object: use its __dict__ as a last resort
    if hasattr(o, "__dict__"):
        return o.__dict__

    # Fallback to string representation
    return str(o)

def _parse_iso_datetime(value: Any) -> Any:
    """
    Best-effort ISO-8601 datetime parser. Returns original value if parsing fails.
    """
    if not isinstance(value, str):
        return value
    s = value.strip()
    # Normalize Zulu suffix to Python-compatible format
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    # noinspection PyBroadException
    try:
        return config.LOCAL_TIMEZONE.localize(datetime.fromisoformat(s))
    except Exception:
        return value

def _json_object_hook(obj: dict) -> Any:
    """
    Reconstruct domain model objects from JSON dictionaries.
    Called bottom-up by json.load.

    Supports:
    - Measurement: { "time": <iso>, "value": <num> }
    - Trend: { "name": <TrendName|str>, "unit": <str>, "maxSamples": <int>, "data": [Measurement...] }
    - TrendSet: { "name": <TrendName|str>, "trends": { zone: Trend, ... } }
    - Event: { "time": <iso>, "message": <str>, "level": <EventLevel|str> }
    """
    if not isinstance(obj, dict):
        return obj

    # Measurement
    if {"time", "value"} <= obj.keys() and len(obj.keys()) == 2:
        time_val = _parse_iso_datetime(obj.get("time"))
        value = obj.get("value")
        if isinstance(time_val, datetime):
            # noinspection PyBroadException
            try:
                return Measurement(time_val, value)
            except Exception:
                # If constructor differs, fall through to return original obj
                pass
        return obj

    # Trend
    if {"name", "unit", "maxSamples", "data"} <= obj.keys():
        name_val = obj.get("name")
        # noinspection PyBroadException
        try:
            name_enum = name_val if isinstance(name_val, TrendName) else TrendName(name_val)
        except Exception:
            name_enum = name_val
        unit = obj.get("unit")
        max_samples = obj.get("maxSamples")
        data_list = obj.get("data") or []
        # noinspection PyBroadException
        try:
            trend = Trend(name_enum, unit, max_samples)
            # Expect data_list to already contain Measurement objects via the hook above
            for m in data_list:
                # Append preserving the original order
                if isinstance(m, Measurement):
                    trend.data.append(m)
            return trend
        except Exception:
            return obj

    # TrendSet
    if {"name", "trends"} <= obj.keys():
        name_val = obj.get("name")
        # noinspection PyBroadException
        try:
            name_enum = name_val if isinstance(name_val, TrendName) else TrendName(name_val)
        except Exception:
            name_enum = name_val
        trends_dict = obj.get("trends") or {}
        zones = list(trends_dict.keys())
        # Infer unit/maxSamples from the first trend, if available
        first_trend = next((t for t in trends_dict.values() if isinstance(t, Trend)), None)
        unit = getattr(first_trend, "unit", "") if first_trend else ""
        max_samples = getattr(first_trend, "maxSamples", 0) if first_trend else 0
        # noinspection PyBroadException
        try:
            ts = TrendSet(zones, name_enum, unit, max_samples)
            # Replace trends with the deserialized Trend objects (preserve zones)
            # Ensure only Trend instances are set; ignore malformed entries
            ts.trends = {z: t for z, t in trends_dict.items() if isinstance(t, Trend)}
            return ts
        except Exception:
            return obj

    # Settings or generic enums: attempt to map known enums when encountered
    # Note: We keep settings dict keys as strings; values like Unit can be re-wrapped if needed.
    if "units" in obj and isinstance(obj["units"], str):
        # noinspection PyBroadException
        try:
            obj["units"] = Unit(obj["units"])
        except Exception:
            pass

    return obj

#</editor-fold>

class ThreadSafeJSON:
    """
    ThreadSafeJSON provides a thread-safe interface for reading and updating JSON
    configurations stored in a file.

    This class ensures proper synchronization using a reentrant lock, allowing
    safe concurrent access to the JSON file. It also creates the file's directory
    structure if it does not exist and initializes the file with a default value
    if it is missing. Operations such as reading and updating the file are
    protected to avoid race conditions or data corruption during concurrent use.

    :ivar path: Path to the JSON file.
    :type path: str
    :ivar default: Default value to initialize the file with if it does not exist.
    :type default: Any
    """
    def __init__(self, path: str, default: Any):
        self.path = path
        self.default = default
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            self._write(default)

    def _read(self) -> Any:
        """
        Reads and parses a JSON file using UTF-8 encoding.

        The method opens the file specified by the `path` attribute in read mode
        with UTF-8 encoding, then loads and returns its content as a Python object.
        The returned object represents the parsed JSON data.

        :return: The parsed JSON content as a Python object
        :rtype: Any
        """
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f, object_hook=_json_object_hook)

    def _write(self, content: Any):
        """
        Writes the given content to a temporary file in JSON format and renames
        it to the target file path. This ensures the atomicity of the write
        operation to avoid incomplete or corrupted writes.

        :param content: The content to be written to the file. It must be
            serializable to JSON format.
        """
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2, default=_json_default)
        os.replace(tmp_path, self.path)

    def read(self) -> Any:
        """
        Reads data in a thread-safe manner. If an exception is encountered during the
        read operation, it resets the data to a default value and returns this default.

        :return: The value read by the internal `_read` method or the default value if
            an exception occurs.
        :rtype: Any
        """
        with self._lock:
            # noinspection PyBroadException
            try:
                return self._read()
            except Exception:
                self._write(self.default)
                return self.default

    def update(self, updater):
        """
        Updates the stored data using the provided updater function. The method reads
        the current data, applies the updater function to modify it, writes the updated
        data back, and returns the updated result.

        :param updater: Function that accepts the current data as an input and returns
                        the updated data.
        :type updater: Callable
        :return: The updated data after applying the updater function.
        :rtype: Any
        """
        with self._lock:
            data = self.read()
            updated = updater(data)
            self._write(updated)
            return updated

class RollingThreadSafeJSON(ThreadSafeJSON):
    """
    Provides a rolling mechanism for JSON data that allows safe updates across threads
    while dynamically updating file paths based on the current year.

    This class extends the functionality of ThreadSafeJSON to automatically adapt the
    storage path of JSON files according to the current year. It enforces the presence
    of a '%YEAR%' placeholder in the given path and resolves it during file operations.

    :ivar path: The file path template containing the '%YEAR%' placeholder.
    :type path: str
    :ivar default: The default data to use if the JSON file does not exist.
    :type default: Any
    """
    def __init__(self, path: str, default: Any):
        self._pathPattern = path
        if "%YEAR%" not in self._pathPattern:
            raise ValueError("Path pattern must contain %YEAR% placeholder")
        # Initialize base with the resolved current-year path; the file is created at the correct location immediately
        super().__init__(self.get_current_file_path(), default)

    def get_current_file_path(self) -> str:
        """
        Gets the current file path with the placeholder for the year replaced by
        the current year.

        This method replaces the "%YEAR%" keyword in the file path with the actual
        current year retrieved via a helper function.

        :return: The updated file path with the year properly replaced.
        :rtype: str
        """
        return self._pathPattern.replace("%YEAR%", _get_current_year())

    def read(self) -> Any:
        """
        Reads data using the current file path through the parent `read` method.
        
        Updates the instance's file path based on the current year, then calls and 
        returns data from the parent read operation. When the year advances, a new 
        file is created with default content.

        :return: Data read from the file 
        :rtype: Any
        """
        self.path = self.get_current_file_path()
        return super().read()

    def update(self, updater):
        """
        Updates the current file path and invokes the parent class update method.

        :param updater: The object used to perform the update operation.
        :return: The result of the update operation from the parent class method.
        """
        self.path = self.get_current_file_path()
        return super().update(updater)


class TrendName(StrEnum):
    """
    Enumeration for trend names in various environmental and measurement parameters.

    This enumeration defines constants representing different types of environmental
    and chemical trends such as humidity, temperature, and salinity, among others.
    Each value is represented as a string constant, which can be used to denote
    specific types of monitored or measured trends in applications.

    """
    HUMIDITY = "humidity"
    TEMPERATURE = "temperature"
    PH = "ph"
    ELECTRICAL_CONDUCTIVITY = "ec"
    SALINITY = "salinity"
    TOTAL_DISSOLVED_SOLIDS = "tds"
    NITROGEN = "nitrogen"
    PHOSPHORUS = "phosphorus"
    POTASSIUM = "potassium"
    WATER = "water"
    LOG = "events"

class Unit(StrEnum):
    """
    Represents a unit system for measurement.

    This class is an enumeration of the two used unit systems: Metric and Imperial. It is used to specify
    and work with the measurement systems in different contexts.

    :cvar METRIC: The metric measurement system, commonly used worldwide.
    :cvar IMPERIAL: The imperial measurement system, primarily used in the United States.
    """
    METRIC = "metric"
    IMPERIAL = "imperial"

class Settings(StrEnum):
    """
    Enumeration for application settings.

    This class represents different configurable settings for an application as
    enumerable constants. Each setting has an associated default value. It provides
    a structured and type-safe way of defining application configuration options.

    Attributes:
    :ivar default: The default value associated with the setting.
    :type default: float | int | str
    """
    HUMIDITY_TARGET_PERCENT = "humidity_target_percent", HUMIDITY_TARGET_PERCENT
    WATERING_START_TIME = "watering_start_time", f"{WATERING_START_LOCALTIME.hour:02d}:{WATERING_START_LOCALTIME.minute:02d}"
    WATERING_MAX_MINUTES_PER_ZONE = "watering_max_minutes_per_zone", WATERING_MAX_MINUTES_PER_ZONE
    RAIN_CANCEL_PROBABILITY_THRESHOLD = "rain_cancel_probability_threshold", RAIN_CANCEL_PROBABILITY_THRESHOLD
    UNITS = "units", Unit.IMPERIAL

    def __new__(cls, value: str, default: float|int|str):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.default = default
        return obj

# Defaults
DEFAULT_SETTINGS: dict[Settings, float|int|str] = {
    Settings.HUMIDITY_TARGET_PERCENT: Settings.HUMIDITY_TARGET_PERCENT.default,
    Settings.WATERING_START_TIME: Settings.WATERING_START_TIME.default,
    Settings.WATERING_MAX_MINUTES_PER_ZONE: Settings.WATERING_MAX_MINUTES_PER_ZONE.default,
    Settings.RAIN_CANCEL_PROBABILITY_THRESHOLD: Settings.RAIN_CANCEL_PROBABILITY_THRESHOLD.default,
    Settings.UNITS: Settings.UNITS.default,
}

DEFAULT_TRENDS: dict[TrendName, TrendSet] = {
    TrendName.HUMIDITY: TrendSet([z.name for z in ZONES.values()], TrendName.HUMIDITY, "%", TREND_MAX_SAMPLES),
    TrendName.TEMPERATURE: TrendSet([z.name for z in ZONES.values()], TrendName.TEMPERATURE, "°F", TREND_MAX_SAMPLES),
    TrendName.PH: TrendSet([z.name for z in ZONES.values()], TrendName.PH, "pH", TREND_MAX_SAMPLES),
    TrendName.ELECTRICAL_CONDUCTIVITY: TrendSet([z.name for z in ZONES.values()], TrendName.ELECTRICAL_CONDUCTIVITY, "µS/cm", TREND_MAX_SAMPLES),
    TrendName.SALINITY: TrendSet([z.name for z in ZONES.values()], TrendName.SALINITY, "ppt", TREND_MAX_SAMPLES),
    TrendName.TOTAL_DISSOLVED_SOLIDS: TrendSet([z.name for z in ZONES.values()], TrendName.TOTAL_DISSOLVED_SOLIDS, "ppm", TREND_MAX_SAMPLES),
    TrendName.NITROGEN: TrendSet([z.name for z in ZONES.values()], TrendName.NITROGEN, "mg/kg", TREND_MAX_SAMPLES),
    TrendName.PHOSPHORUS: TrendSet([z.name for z in ZONES.values()], TrendName.PHOSPHORUS, "mg/kg", TREND_MAX_SAMPLES),
    TrendName.POTASSIUM: TrendSet([z.name for z in ZONES.values()], TrendName.POTASSIUM, "mg/kg", TREND_MAX_SAMPLES),
    TrendName.WATER: TrendSet([z.name for z in ZONES.values()], TrendName.WATER, "L", TREND_MAX_SAMPLES),
}

settings_store = ThreadSafeJSON(SETTINGS_FILE, DEFAULT_SETTINGS)
trends_store = RollingThreadSafeJSON(TRENDS_FILE, DEFAULT_TRENDS)

def _now_utc() -> datetime:
    return datetime.now(UTC)

def _now_utc_str() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat(timespec='milliseconds') + "Z"

def _now_local(tz: tzinfo = config.LOCAL_TIMEZONE) -> datetime:
    return datetime.now(tz)

def _now_local_str(tz: tzinfo = config.LOCAL_TIMEZONE, fmt: str = "%FT%T.%f%z%Z") -> str:
    return datetime.now(tz).strftime(fmt)

def record_measurement(trend: TrendName, zone: str, value: float|int):
    def _upd(data: Dict[TrendName, TrendSet]):
        data[trend].add_value(zone, Measurement(_now_local(), value))
        return data
    trends_store.update(_upd)

def record_humidity(zone: str, value: float):
    record_measurement(TrendName.HUMIDITY, zone, value)

def record_temperature(zone: str, value: float):
    record_measurement(TrendName.TEMPERATURE, zone, value)

def record_electrical_conductivity(zone: str, value: int):
    record_measurement(TrendName.ELECTRICAL_CONDUCTIVITY, zone, value)

def record_total_dissolved_solids(zone: str, value: int):
    record_measurement(TrendName.TOTAL_DISSOLVED_SOLIDS, zone, value)

def record_ph(zone: str, value: float):
    record_measurement(TrendName.PH, zone, value)

def record_salinity(zone: str, value: int):
    record_measurement(TrendName.SALINITY, zone, value)

def record_rh(zone: str, rh: float, temp: float, ph: float, ec: int, sal: int, tds: int):
    def _upd(data: Dict[TrendName, TrendSet]):
        time = _now_local()
        data[TrendName.HUMIDITY].add_value(zone, Measurement(time, rh))
        data[TrendName.TEMPERATURE].add_value(zone, Measurement(time, temp))
        data[TrendName.PH].add_value(zone, Measurement(time, ph))
        data[TrendName.ELECTRICAL_CONDUCTIVITY].add_value(zone, Measurement(time, ec))
        data[TrendName.SALINITY].add_value(zone, Measurement(time, sal))
        data[TrendName.TOTAL_DISSOLVED_SOLIDS].add_value(zone, Measurement(time, tds))
        return data
    trends_store.update(_upd)

def record_npk(zone: str, n: int, p: int, k: int):
    def _upd(data: Dict[TrendName, TrendSet]):
        time = _now_local()
        data[TrendName.NITROGEN].add_value(zone, Measurement(time, n))
        data[TrendName.PHOSPHORUS].add_value(zone, Measurement(time, p))
        data[TrendName.POTASSIUM].add_value(zone, Measurement(time, k))
        return data
    trends_store.update(_upd)

def record_water_liters(zone: str, liters: float):
    record_measurement(TrendName.WATER, zone, liters)