#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#
# python
import glob
import json
import sqlite3
import hashlib
import logging
import re
from contextlib import contextmanager
from datetime import datetime, UTC
from typing import Any

from .config import get_project_root, Settings, CONFIG, RPI_ZONE_NAME, ZONES, AppConfig
from .model.measurement import Measurement, WateringMeasurement
from .model.times import valid_timezone
from .model.trend import TrendName
from .model.units import Unit, UnitType
from .model.weather_data import WeatherData
from .model.zone import Zone

__db_file_name = f"{get_project_root()}/data/waterly-{datetime.now().year}.sqlite"

@contextmanager
def db(path=__db_file_name):
    """
    Context manager for managing a SQLite database connection. This context manager provides
    a connection to a SQLite database identified by the given path, with autocommit mode enabled.
    It ensures that the connection is properly closed when exiting the context.

    :param path: Optional; File path to the SQLite database. Defaults to a path named
        "<project_root>/data/waterly-<current_year>.sqlite".
    :type path: str
    :return: A SQLite connection object that can be used within the context.
    :rtype: sqlite3.Connection
    """
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)  # autocommit
    try:
        yield conn
    finally:
        conn.close()

def get_db_version(conn) -> tuple[str, str]:
    """
    Retrieves the current database version number from the migration history.

    This function checks whether the database is initialized. If the database
    is initialized, it fetches the most recent version from the
    `migration_history` table. If not initialized, it defaults to returning
    a version of "0.0.0".

    :param conn: The database connection object used to perform the query.
    :type conn: Connection
    :return: A string representing the current database version from migration
             history, or "0.0.0" if the database is uninitialized.
    :rtype: str
    """
    if __is_db_initialized(conn):
        cur = conn.cursor()
        cur.execute("SELECT version, checksum FROM migration_history ORDER BY version DESC LIMIT 1")
        return cur.fetchone()
    else:
        return "0.0.0", "0000"

def __has_script_version(conn, scr_version):
    """
    Checks if a specific script version exists in the migration history table.

    This function verifies whether a given migration version is recorded in the
    database's `migration_history` table. It first ensures that the database has
    been initialized before proceeding with the query.

    :param conn: The database connection object.
    :type conn: sqlite3.Connection
    :param scr_version: The script version to check in the migration history.
    :type scr_version: str
    :return: A boolean indicating whether the script version exists.
    :rtype: bool
    """
    if not __is_db_initialized(conn):
        return False
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM migration_history WHERE version=?", (scr_version,))
    return cur.fetchone()[0] > 0

def __is_db_initialized(conn):
    """
    Checks if the database has been initialized by verifying the presence of migration tables.

    :param conn: Database connection object.
    :type conn: sqlite3.Connection
    :return: True if the database is initialized with migration tables, False otherwise.
    :rtype: bool
    """
    return conn.execute("select count(*) as table_count from sqlite_master sm where sm.type = 'table' and sm.name like 'migration_%'").fetchone()[0] > 0

def init_db():
    """
    Initializes the database by applying required migrations and settings.

    This function checks the current state of the database and determines if any
    new migrations need to be applied. If the database is already at the latest
    version, it logs an informational message and exits. Otherwise, it runs the necessary
    migrations by executing SQL scripts in order, verifies their completion, and updates
    the migration history. Additionally, specific database pragmas for optimization and foreign
    key support are enabled during initialization.

    :raises RuntimeError: When encountering errors during SQL execution or migrations.
    """
    logger = logging.getLogger("init_db")
    # noinspection PyBroadException
    try:
        # Expose DB-backed persistence for AppConfig writes
        CONFIG.set_persist_callback(save_config_item)
    except Exception:
        # If configuration isn't fully initialized yet, skip; the setter can be called later if needed.
        logger.warning("Failed to expose hook persistence callback into AppConfig, skipping.")
        pass

    ddl_files = sorted(glob.glob(f"{get_project_root()}/waterly/db/*.sql"), key=lambda x: x.split("_")[-1])
    latest_version = re.search(r"_v([\d+.]+)\.", ddl_files[-1], re.RegexFlag.IGNORECASE).group(1)
    with db() as conn:
        cur = conn.cursor()
        if __is_db_initialized(conn):
            db_version, checksum = get_db_version(conn)
            if db_version == latest_version:
                logger.info(f"Database already initialized; currently at version {db_version} (hash {checksum})")
                return
            else:
                logger.info(f"Database is out of date; current version {db_version} (hash {checksum}), latest version {latest_version}")
        logger.info("Initializing/Migrating database...")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys = ON")     # Enable foreign keys
        # data model - read the files db/ddl*.sql and execute them as script in the versions order
        for ddl_file in ddl_files:
            with open(ddl_file, "r") as f:
                script_version = re.search(r"_v([\d+.]+)\.", ddl_file, re.RegexFlag.IGNORECASE).group(1)
                # do we need to run this migration?
                if not __has_script_version(conn, script_version):
                    logger.info(f"Running migration {script_version} from {ddl_file}")
                    script: str = f.read()
                    cur.executescript(script)
                    # create sha-256 of the file contents and insert as version into migration_history table
                    checksum = hashlib.sha256(script.encode("utf-8")).hexdigest()
                    cur.execute("INSERT INTO migration_history(version, description, checksum) VALUES (?, ?, ?)", (script_version,f"Schema {script_version} at {ddl_file}", checksum))
                    conn.commit()
                    logger.info(f"Migration {script_version} completed")
                else:
                    logger.info(f"Migration {script_version} already applied")


def get_config_from_db() -> AppConfig:
    """
    Fetches configuration settings from the database and returns them parsed into the
    `AppConfig` structure. If any setting from `Settings` is not found in the database,
    this method adds the default value for it in the database and commits the changes.

    :raises DatabaseError: If there are issues with database connectivity or execution.
    :raises JSONDecodeError: If a setting value in the database cannot be decoded from JSON.

    :return: The application configuration settings.
    :rtype: AppConfig
    """
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM config")
        raw_settings = dict(cur.fetchall())
        #parse into CONFIG structure
        for setting in Settings:
            if setting.name in raw_settings:
                CONFIG[setting] = json.loads(raw_settings[setting.name])
            else:
                CONFIG[setting] = setting.default
                cur.execute("INSERT INTO config(type, value) VALUES (?, ?)", (setting.name, json.dumps(setting.default)))
                conn.commit()
        return CONFIG

def save_config_to_db():
    """
    Save application configuration to the database.

    This function iterates through all settings defined in the Settings enumeration, updating
    their corresponding values in the 'config' database table. The function serializes each
    configuration setting to a JSON string before storing it in the database. All changes
    are committed upon successfully updating the database records.

    :return: None
    """
    with db() as conn:
        cur = conn.cursor()
        for setting in Settings:
            cur.execute("UPDATE config SET value=? WHERE type=?", (json.dumps(CONFIG.settings[setting.name]), setting.name))
        conn.commit()

def save_config_item(item: Settings, value: dict[str, Any]):
    """
    Update the configuration item in the database with the specified value.

    This function updates a configuration setting in the database. The `item` specifies
    the configuration type, while `value` is the new data to be stored for that
    configuration. The function ensures that the provided value is serialized into JSON
    format before being saved to the database.

    :param item: The configuration type to be updated. This value is an instance of Settings, which defines the configuration type in the application.
    :param value: The new configuration value to be stored in the database. It must be a dictionary with string keys and values of any type.
    :return: None
    """
    with db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE config SET value=? WHERE type=?", (json.dumps(value), item.name))
        conn.commit()

def get_zones_from_db() -> dict[int, Zone]:
    """
    Fetches zone data from the database and populates it into the ZONES dictionary.

    Executes a query to retrieve zone details including ID, name, description, RH sensor address, NPK sensor
    address, and relay address. The data is then stored in the ZONES dictionary with the zone ID as the key
    and an instance of the Zone class as the value. The function returns the updated ZONES dictionary.

    :return: A dictionary mapping zone IDs to Zone objects.
    :rtype: dict[int, Zone]
    """
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, description, rh_sensor_address, npk_sensor_address, relay_address FROM zone")
        for zone in cur.fetchall():
            ZONES[zone[0]] = Zone(zone[1], zone[2], zone[3], zone[4], zone[5])
        return ZONES

def __add_measurement(trend: str, zone: str, measurement: Measurement):
    """
    Adds a new measurement into the database. The measurement is associated with a specific
    trend and zone, includes a timestamp, a reading value, and its unit of measurement. It
    uses a database connection to insert or replace the data into the 'measurement' table.

    :param trend: A string representing the name of the trend to which the measurement belongs.
    :type trend: str
    :param zone: A string representing the name of the zone in which the measurement was taken.
    :type zone: str
    :param measurement: The object representing the measurement - timestamp, value, unit.
    :type measurement: Measurement
    :return: None
    """
    with db() as conn:
        zone_id = conn.execute("SELECT id FROM zone WHERE name=?", (zone,)).fetchone()
        conn.execute("INSERT OR REPLACE INTO measurement(name, zone_id, ts_utc, tz, reading, unit) VALUES (?,?,?,?,?,?)",
            (trend, zone_id[0], int(measurement.timestamp.timestamp() * 1000), str(measurement.timestamp.tzinfo),
             measurement.value, measurement.unit))
        conn.commit()

def record_measurement(trend: TrendName, zone: str, measurement: Measurement, unit: Unit = None):
    """
    Store a measurement into the database with the provided unit (no in-DB conversion).
    :param trend: A string representing the name of the trend to which the measurement belongs.
    :type trend: str
    :param zone: A string representing the name of the zone in which the measurement was taken.
    :type zone: str
    :param measurement: The object representing the measurement - timestamp, value, unit.
    :type measurement: Measurement
    :param unit: An optional string representing a new unit for measurement argument to be converted to (e.g., 'Celsius', 'kW').
    :type unit: Unit
    :return: None
    """
    msmt = measurement if unit is None or unit == measurement.unit else measurement.convert(unit)
    __add_measurement(trend, zone, msmt)

def record_rpi_temperature(value: Measurement):
    """
    Records the Raspberry Pi board temperature under a dedicated zone.
    """
    record_measurement(TrendName.RPI_TEMPERATURE, RPI_ZONE_NAME, value)

def record_rh(zone: str, rh: Measurement, temp: Measurement, ph: Measurement, ec: Measurement, sal: Measurement, tds: Measurement):
    metric = CONFIG[Settings.UNITS] == UnitType.METRIC
    # write all in a short autocommit burst
    record_measurement(TrendName.HUMIDITY, zone, rh)
    record_measurement(TrendName.TEMPERATURE, zone, temp, Unit.CELSIUS if metric else Unit.FAHRENHEIT)
    record_measurement(TrendName.PH, zone, ph)
    record_measurement(TrendName.ELECTRICAL_CONDUCTIVITY, zone, ec)
    record_measurement(TrendName.SALINITY, zone, sal)
    record_measurement(TrendName.TOTAL_DISSOLVED_SOLIDS, zone, tds)

def record_npk(zone: str, n: Measurement, p: Measurement, k: Measurement):
    record_measurement(TrendName.NITROGEN, zone, n)
    record_measurement(TrendName.PHOSPHORUS, zone, p)
    record_measurement(TrendName.POTASSIUM, zone, k)

def record_watering(zone: str, measurement: WateringMeasurement):
    """
    Stores the watering amount under the 'water' trend. Extra fields like humidity_start/end
    and duration are currently not persisted in this simplified schema.
    """
    record_measurement(TrendName.WATER, zone, measurement)

def record_weather(weather_data: list[WeatherData]):
    """
    Records weather data into a database.

    This function takes a list of weather data and stores the relevant information
    to a database. It includes details about the current conditions and forecasts,
    such as temperature, precipitation, soil moisture, and surface pressure.

    :param weather_data: A list of WeatherData objects containing the weather details to be recorded.
    :type weather_data: list[WeatherData]
    :return: None
    """
    with db() as conn:
        cur = conn.cursor()
        # current conditions
        now = datetime.now(UTC).timestamp() * 1000
        for wd in weather_data:
            cur.execute("""
              INSERT OR REPLACE INTO weather(collected_at_utc, forecast_ts_utc, tz, tag, temperature_2m, temperature_unit, precipitation_probability, precipitation, precipitation_unit, soil_moisture_1_to_3cm, moisture_unit, surface_pressure, pressure_unit)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (now, wd.timestamp.timestamp() * 1000, str(wd.timestamp.tzinfo),
                  wd.tag, wd.temperature.value, wd.temperature.unit, wd.precipitation_prob.value if wd.precipitation_prob else None,
                  wd.precipitation_amount.value, wd.precipitation_amount.unit, wd.soil_humidity.value, wd.soil_humidity.unit,
                  wd.surface_pressure.value if wd.surface_pressure else None, wd.surface_pressure.unit if wd.surface_pressure else None))
        conn.commit()

def get_weather_data(from_ts: datetime, count: int) -> list[WeatherData]:
    """
    Retrieves weather forecast data either in forward or reverse temporal order based on the
    provided time.

    It excludes the records with null precipitation probability - those are records of current conditions that
    do not include forecasted precipitation probability.

    :param from_ts: The reference datetime from which the weather data should be fetched.
    :param count: The number of weather records to retrieve. A positive value fetches
        records moving forward in time. A negative value fetches records moving backward in time.
    :return: A list containing weather data entries encapsulated in `WeatherData` objects.
    """
    with db() as conn:
        cur = conn.cursor()
        how_many:int = abs(count)
        forward:bool = count > 0
        if forward:
            cur.execute("""
              SELECT collected_at_utc, forecast_ts_utc, tz, tag, temperature_2m, temperature_unit, soil_moisture_1_to_3cm, moisture_unit, precipitation, precipitation_unit, precipitation_probability, surface_pressure, pressure_unit
                FROM weather
               WHERE forecast_ts_utc >= ? and precipitation_probability is not null
            ORDER BY forecast_ts_utc
               LIMIT ?
            """, (from_ts.timestamp() * 1000, how_many))
        else:
            cur.execute("""
              SELECT collected_at_utc, forecast_ts_utc, tz, tag, temperature_2m, temperature_unit, soil_moisture_1_to_3cm, moisture_unit, precipitation, precipitation_unit, precipitation_probability, surface_pressure, pressure_unit
                FROM weather
               WHERE forecast_ts_utc <= ? and precipitation_probability is not null
            ORDER BY forecast_ts_utc DESC
               LIMIT ?
            """, (from_ts.timestamp() * 1000, how_many))
        rows = cur.fetchall()
        wdata:list = []
        for row in rows:
            # Build localized timestamp, then use a factory for clarity.
            localized_ts = datetime.fromtimestamp(row[1] / 1000, valid_timezone(row[2]))
            wdata.append(WeatherData.from_db_row((localized_ts, *row[3:])))
        return wdata
