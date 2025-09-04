import os
from datetime import datetime, UTC, tzinfo
from typing import Any
from enum import StrEnum
from .config import DATA_DIR, CONFIG, Settings, ZONES, UnitType
from .model.trend import TrendSet, Measurement, convert_measurement
from .json.serialization import ThreadSafeJSON

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
        if ("%YEAR%" not in self._pathPattern) and ("%MONTH%" not in self._pathPattern):
            raise ValueError("Path pattern must contain both %YEAR% and %MONTH% placeholders")
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
        dt = datetime.now(CONFIG[Settings.LOCAL_TIMEZONE])
        return self._pathPattern.replace("%YEAR%", dt.strftime("%Y")).replace("%MONTH%", dt.strftime("%m_%b"))

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
    RPI_TEMPERATURE = "rpitemp"

__rpi_zone_name = "RPI"

DEFAULT_TRENDS: dict[TrendName, TrendSet] = {}
trends_store: dict[TrendName, RollingThreadSafeJSON] = {}

def init_default_trends():
    """
    Initializes default trend configurations for various environmental metrics if they are not
    already defined. The function populates the global `DEFAULT_TRENDS` dictionary with trend
    data associated with different environmental metrics like humidity, temperature, pH, salinity,
    and nutrient levels. Trends are created based on the predefined zones and associated configuration
    settings such as unit system and maximum sample size.

    :param DEFAULT_TRENDS: Global dictionary intended to store predefined environmental trend
                           data mapped by trend names.
    :type DEFAULT_TRENDS: dict

    :raises KeyError: If specific keys required from configuration `CONFIG` are unavailable.

    :return: None
    """
    global DEFAULT_TRENDS

    if len(DEFAULT_TRENDS) > 0:
        return

    metric:bool = CONFIG[Settings.UNITS] == UnitType.METRIC
    DEFAULT_TRENDS[TrendName.HUMIDITY] = TrendSet([z.name for z in ZONES.values()], TrendName.HUMIDITY, "%", CONFIG[Settings.TREND_MAX_SAMPLES])
    DEFAULT_TRENDS[TrendName.TEMPERATURE] = TrendSet([z.name for z in ZONES.values()], TrendName.TEMPERATURE, "°C" if metric else "°F", CONFIG[Settings.TREND_MAX_SAMPLES])
    DEFAULT_TRENDS[TrendName.PH] = TrendSet([z.name for z in ZONES.values()], TrendName.PH, "pH", CONFIG[Settings.TREND_MAX_SAMPLES])
    DEFAULT_TRENDS[TrendName.ELECTRICAL_CONDUCTIVITY] = TrendSet([z.name for z in ZONES.values()], TrendName.ELECTRICAL_CONDUCTIVITY, "µS/cm", CONFIG[Settings.TREND_MAX_SAMPLES])
    DEFAULT_TRENDS[TrendName.SALINITY] = TrendSet([z.name for z in ZONES.values()], TrendName.SALINITY, "ppt", CONFIG[Settings.TREND_MAX_SAMPLES])
    DEFAULT_TRENDS[TrendName.TOTAL_DISSOLVED_SOLIDS] = TrendSet([z.name for z in ZONES.values()], TrendName.TOTAL_DISSOLVED_SOLIDS, "ppm", CONFIG[Settings.TREND_MAX_SAMPLES])
    DEFAULT_TRENDS[TrendName.NITROGEN] = TrendSet([z.name for z in ZONES.values()], TrendName.NITROGEN, "mg/kg", CONFIG[Settings.TREND_MAX_SAMPLES])
    DEFAULT_TRENDS[TrendName.PHOSPHORUS] = TrendSet([z.name for z in ZONES.values()], TrendName.PHOSPHORUS, "mg/kg", CONFIG[Settings.TREND_MAX_SAMPLES])
    DEFAULT_TRENDS[TrendName.POTASSIUM] = TrendSet([z.name for z in ZONES.values()], TrendName.POTASSIUM, "mg/kg", CONFIG[Settings.TREND_MAX_SAMPLES])
    DEFAULT_TRENDS[TrendName.WATER] = TrendSet([z.name for z in ZONES.values()], TrendName.WATER, "L" if metric else "gal", CONFIG[Settings.TREND_MAX_SAMPLES])
    DEFAULT_TRENDS[TrendName.RPI_TEMPERATURE] = TrendSet([__rpi_zone_name], TrendName.RPI_TEMPERATURE, "°C" if metric else "°F", CONFIG[Settings.TREND_MAX_SAMPLES])

def create_trends_store():
    """
    Initializes the `trends_store` global variable with instances of RollingThreadSafeJSON for
    each trend in TrendName if it is not already populated.

    The `trends_store` is filled with paths to JSON files for each trend, where the file paths are
    formatted to include the respective year and month. These files are used to store trend data,
    with default values sourced from `DEFAULT_TRENDS`.

    :return: None
    """
    global trends_store

    if len(trends_store) > 0:
        return

    for trendName in TrendName:
        trends_store[trendName] = RollingThreadSafeJSON(f"{DATA_DIR}/%YEAR%/%MONTH%_{trendName.value}.json", DEFAULT_TRENDS[trendName])

def _now_utc() -> datetime:
    return datetime.now(UTC)

def _now_utc_str() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat(timespec='milliseconds') + "Z"

def _now_local(tz: tzinfo = CONFIG[Settings.LOCAL_TIMEZONE]) -> datetime:
    return datetime.now(tz)

def _now_local_str(tz: tzinfo = CONFIG[Settings.LOCAL_TIMEZONE], fmt: str = "%FT%T.%f%z%Z") -> str:
    return datetime.now(tz).strftime(fmt)

def record_measurement(trend: TrendName, zone: str, value: float|int, cur_unit: str):
    """
    Records a measurement for a specific trend and zone with the given value.

    This function updates the trends store by adding a new measurement for the
    specified trend and zone. The measurement is timestamped with the current
    local time.

    :param trend: The name of the trend to update
    :type trend: TrendName
    :param zone: The identifier for the zone
    :type zone: str
    :param value: The measurement value to record. Can be a float or an integer.
    :type value: float | int
    :return: None
    """
    def _upd(data: TrendSet):
        new_unit = data.trend(zone).unit
        data.add_value(zone, Measurement(_now_local(), convert_measurement(value, cur_unit, new_unit)))
        return data
    trends_store[trend].update(_upd)

def record_humidity(zone: str, value: float):
    """
    Records the humidity measurement for a specified zone. This function provides
    a way to associate a humidity trend with the given location and its value.

    :param zone: The name of the zone or location where the humidity measurement
        is being recorded.
    :type zone: str
    :param value: The humidity level to be recorded, represented as a floating-point
        number.
    :type value: float
    :return: None
    """
    record_measurement(TrendName.HUMIDITY, zone, value, DEFAULT_TRENDS[TrendName.HUMIDITY].trend(zone).unit)

def record_temperature(zone: str, value: float):
    """
    Records a temperature measurement for a specified zone. The function captures
    the temperature value and associates it with the specified zone.

    :param zone: The name of the zone for which the temperature is being recorded.
    :type zone: str
    :param value: The temperature value to record.
    :type value: float
    :return: None
    """
    metric = CONFIG[Settings.UNITS] == UnitType.METRIC
    record_measurement(TrendName.TEMPERATURE, zone, value, "°C" if metric else "°F")

def record_electrical_conductivity(zone: str, value: int):
    """
    Records the electrical conductivity measurement for a specified zone with the given value.

    This function is responsible for logging or saving the electrical conductivity data associated
    with a specific zone.

    :param zone: The name of the zone for which the electrical conductivity measurement is being recorded.
    :type zone: str
    :param value: The numerical value of the electrical conductivity measurement.
    :type value: int
    :return: None
    """
    record_measurement(TrendName.ELECTRICAL_CONDUCTIVITY, zone, value, DEFAULT_TRENDS[TrendName.ELECTRICAL_CONDUCTIVITY].trend(zone).unit)

def record_total_dissolved_solids(zone: str, value: int):
    """
    Records the measurement of total dissolved solids for a specified zone.

    This function logs a measurement for the total dissolved solids in a designated zone.

    :param zone: The name of the zone for which the measurement is being recorded.
    :type zone: str
    :param value: The measured value of total dissolved solids to be recorded.
    :type value: int
    """
    record_measurement(TrendName.TOTAL_DISSOLVED_SOLIDS, zone, value, DEFAULT_TRENDS[TrendName.TOTAL_DISSOLVED_SOLIDS].trend(zone).unit)

def record_ph(zone: str, value: float):
    """
    Records the pH measurement for the specified zone.

    :param zone: The identifier of the zone where the measurement is obtained.
    :type zone: str
    :param value: The pH value recorded for the specified zone.
    :type value: float
    :return: None
    """
    record_measurement(TrendName.PH, zone, value, DEFAULT_TRENDS[TrendName.PH].trend(zone).unit)

def record_salinity(zone: str, value: int):
    """
    Records the salinity measurement for a specified zone.

    :param zone: The zone identifier where the salinity measurement is taken.
    :type zone: str
    :param value: The salinity value to be recorded.
    :type value: int
    :return: None
    """
    record_measurement(TrendName.SALINITY, zone, value, DEFAULT_TRENDS[TrendName.SALINITY].trend(zone).unit)

def record_rpi_temperature(value: float):
    """
    Records the temperature measurement of the Raspberry Pi board. This function assigns
    the measurement to a specific trend and a default zone specific to the Raspberry Pi
    temperature context.

    :param value: The temperature value of the Raspberry Pi board to record in the unit configured for the trend.
    :type value: float
    """
    metric = CONFIG[Settings.UNITS] == UnitType.METRIC
    record_measurement(TrendName.RPI_TEMPERATURE, __rpi_zone_name, value, "°C" if metric else "°F")      # the RPI board temperature is not zone-specific; using always zone 1

def record_rh(zone: str, rh: float, temp: float, ph: float, ec: int, sal: int, tds: int):
    """
    Records environmental measurements such as relative humidity, temperature, pH level,
    electrical conductivity, salinity, and total dissolved solids for a specified zone.
    This function updates the respective trends for a given zone in the monitoring system.

    :param zone: The identifier for the specific area being recorded.
    :type zone: str
    :param rh: The relative humidity value to be recorded in percent.
    :type rh: float
    :param temp: The temperature value to be recorded in degrees Celsius or Fahrenheit, depending on the unit configuration of the trend.
    :type temp: float
    :param ph: The pH level to be recorded.
    :type ph: float
    :param ec: The electrical conductivity value to be recorded in microsiemens per centimeter (μS/cm).
    :type ec: int
    :param sal: The salinity value to be recorded
    :type sal: int
    :param tds: The total dissolved solids value to be recorded
    :type tds: int
    :return: None
    """
    metric = CONFIG[Settings.UNITS] == UnitType.METRIC
    record_measurement(TrendName.HUMIDITY, zone, rh, DEFAULT_TRENDS[TrendName.HUMIDITY].trend(zone).unit)
    record_measurement(TrendName.TEMPERATURE, zone, temp, "°C" if metric else "°F")
    record_measurement(TrendName.PH, zone, ph, DEFAULT_TRENDS[TrendName.PH].trend(zone).unit)
    record_measurement(TrendName.ELECTRICAL_CONDUCTIVITY, zone, ec, DEFAULT_TRENDS[TrendName.ELECTRICAL_CONDUCTIVITY].trend(zone).unit)
    record_measurement(TrendName.SALINITY, zone, sal, DEFAULT_TRENDS[TrendName.SALINITY].trend(zone).unit)
    record_measurement(TrendName.TOTAL_DISSOLVED_SOLIDS, zone, tds, DEFAULT_TRENDS[TrendName.TOTAL_DISSOLVED_SOLIDS].trend(zone).unit)

def record_npk(zone: str, n: int, p: int, k: int):
    """
    Records nitrogen (N), phosphorus (P), and potassium (K) measurements for a specific zone.

    This function handles the recording of nutrient measurements across different
    zones. It leverages the `record_measurement` function to log data for nitrogen,
    phosphorus, and potassium separately.

    :param zone: The identification of the zone for which the measurements are recorded.
    :type zone: str
    :param n: The nitrogen value to be recorded.
    :type n: int
    :param p: The phosphorus value to be recorded.
    :type p: int
    :param k: The potassium value to be recorded.
    :type k: int
    :return: None
    """
    record_measurement(TrendName.NITROGEN, zone, n, DEFAULT_TRENDS[TrendName.NITROGEN].trend(zone).unit)
    record_measurement(TrendName.PHOSPHORUS, zone, p, DEFAULT_TRENDS[TrendName.PHOSPHORUS].trend(zone).unit)
    record_measurement(TrendName.POTASSIUM, zone, k, DEFAULT_TRENDS[TrendName.POTASSIUM].trend(zone).unit)

def record_water_amount(zone: str, amount: float):
    """
    Records the amount of water for a specific zone. This function registers the water
    measurement data into the system for further analysis or monitoring.

    :param zone: The designated zone where the water measurement should be recorded.
    :type zone: str
    :param amount: The volume of water to be recorded in the specified zone. The unit of measurement is determined by
        the unit configuration captured during `init_default_trends` or already present in the trend data,
        `trends_store[TrendName.WATER].read().trend(zone).unit`
    :type amount: float
    :return: None
    """
    metric = CONFIG[Settings.UNITS] == UnitType.METRIC
    record_measurement(TrendName.WATER, zone, amount, "L" if metric else "gal")