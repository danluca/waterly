import os
from datetime import datetime, UTC, tzinfo
from typing import Any, Dict
from enum import StrEnum
from .config import DATA_DIR, CONFIG, Settings, ZONES
from .model.trend import TrendSet, Measurement
from .json.serialization import ThreadSafeJSON

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

DEFAULT_TRENDS: dict[TrendName, TrendSet] = {
    TrendName.HUMIDITY: TrendSet([z.name for z in ZONES.values()], TrendName.HUMIDITY, "%", CONFIG[Settings.TREND_MAX_SAMPLES]),
    TrendName.TEMPERATURE: TrendSet([z.name for z in ZONES.values()], TrendName.TEMPERATURE, "°F", CONFIG[Settings.TREND_MAX_SAMPLES]),
    TrendName.PH: TrendSet([z.name for z in ZONES.values()], TrendName.PH, "pH", CONFIG[Settings.TREND_MAX_SAMPLES]),
    TrendName.ELECTRICAL_CONDUCTIVITY: TrendSet([z.name for z in ZONES.values()], TrendName.ELECTRICAL_CONDUCTIVITY, "µS/cm", CONFIG[Settings.TREND_MAX_SAMPLES]),
    TrendName.SALINITY: TrendSet([z.name for z in ZONES.values()], TrendName.SALINITY, "ppt", CONFIG[Settings.TREND_MAX_SAMPLES]),
    TrendName.TOTAL_DISSOLVED_SOLIDS: TrendSet([z.name for z in ZONES.values()], TrendName.TOTAL_DISSOLVED_SOLIDS, "ppm", CONFIG[Settings.TREND_MAX_SAMPLES]),
    TrendName.NITROGEN: TrendSet([z.name for z in ZONES.values()], TrendName.NITROGEN, "mg/kg", CONFIG[Settings.TREND_MAX_SAMPLES]),
    TrendName.PHOSPHORUS: TrendSet([z.name for z in ZONES.values()], TrendName.PHOSPHORUS, "mg/kg", CONFIG[Settings.TREND_MAX_SAMPLES]),
    TrendName.POTASSIUM: TrendSet([z.name for z in ZONES.values()], TrendName.POTASSIUM, "mg/kg", CONFIG[Settings.TREND_MAX_SAMPLES]),
    TrendName.WATER: TrendSet([z.name for z in ZONES.values()], TrendName.WATER, "L", CONFIG[Settings.TREND_MAX_SAMPLES]),
}
# Trends storage path
TRENDS_FILE = f"{DATA_DIR}/%YEAR%/trends.json"

trends_store = RollingThreadSafeJSON(TRENDS_FILE, DEFAULT_TRENDS)

def _now_utc() -> datetime:
    return datetime.now(UTC)

def _now_utc_str() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat(timespec='milliseconds') + "Z"

def _now_local(tz: tzinfo = CONFIG[Settings.LOCAL_TIMEZONE]) -> datetime:
    return datetime.now(tz)

def _now_local_str(tz: tzinfo = CONFIG[Settings.LOCAL_TIMEZONE], fmt: str = "%FT%T.%f%z%Z") -> str:
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