import threading
import time
import logging
from datetime import datetime, time as dtime
from typing import Optional
from gpiozero import CPUTemperature

from .config import CONFIG, Settings, UnitType
from .model.measurement import WateringMeasurement, Measurement
from .patch import Patch, convert_celsius_fahrenheit
from .pulses import PulseCounter
from .storage import record_npk, record_rh, record_watering, record_rpi_temperature, TrendName
from .weather import WeatherService


class WateringManager:
    """
    Orchestrates the automated watering process, managing sensor readings, weather
    predictions, and scheduled operations to maintain targeted soil conditions
    across defined patches. Coordinates multiple zones, ensuring optimal watering
    efficiency based on real-time data and predefined thresholds.

    The WateringManager class operates on a separate thread to continuously monitor
    humidity levels, evaluate weather conditions, and decide whether to water
    plants. The class integrates with hardware sensors for data collection and uses
    settings for operational constraints like maximum watering duration and timing.

    The class handles daily scheduling, initiates the watering operation only when
    conditions demand it, and ensures safe shutdown of all controlled patches when
    stopped.

    :ivar patches: List of Patch instances representing zones to water.
    :type patches: list[Patch]
    :ivar weather: WeatherService instance, used to retrieve weather forecasts.
    :type weather: WeatherService
    :ivar pulses: PulseCounter instance, used to track water usage during watering cycles.
    :type pulses: PulseCounter
    """
    def __init__(self, patches: list[Patch], weather: WeatherService, pulses: PulseCounter):
        self.patches = patches
        self.weather = weather
        self.pulses = pulses
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="WateringManager", daemon=True)
        self._last_watering_date: Optional[str] = None
        self._last_humidity_reading: dict[str, float] = {}
        self._rh_target: float = CONFIG[Settings.HUMIDITY_TARGET_PERCENT]
        hh, mm = [int(x) for x in CONFIG[Settings.WATERING_START_TIME].split(":")]
        self._start_time: dtime = dtime(hh, mm)
        self._max_minutes: int = CONFIG[Settings.WATERING_MAX_MINUTES_PER_ZONE]
        self._rain_thr: float = CONFIG[Settings.RAIN_CANCEL_PROBABILITY_THRESHOLD]
        self._logger = logging.getLogger(__name__)

    def start(self):
        """
        Starts the internal thread responsible for operation execution and updates
        settings required for the process. Ensures the appropriate method is called for
        thread execution.

        :raises RuntimeError: If the thread fails to start properly.
        """
        self._thread.start()
        self._last_watering_date = CONFIG[Settings.LAST_WATERING_DATE]
        self._rh_target = CONFIG[Settings.HUMIDITY_TARGET_PERCENT]
        hh, mm = [int(x) for x in CONFIG[Settings.WATERING_START_TIME].split(":")]
        self._start_time = dtime(hh, mm)
        self._max_minutes = CONFIG[Settings.WATERING_MAX_MINUTES_PER_ZONE]
        self._rain_thr = CONFIG[Settings.RAIN_CANCEL_PROBABILITY_THRESHOLD]

    def stop(self):
        """
        Stops the current process, sets the stop event, waits for the thread to
        terminate with a timeout, and turns off the water valves for all patches.

        :return: None
        """
        self._stop.set()
        self._thread.join(timeout=5)
        for patch in self.patches:
            patch.stop_watering()

    def _parse_month_day(self, md: str) -> tuple[int, int]|None:
        """
        Parse a MM-DD string into (month, day). Falls back to defaults with logging if invalid.
        """
        try:
            m_str, d_str = md.split("-", 1)
            m, d = int(m_str), int(d_str)
            if not (1 <= m <= 12 and 1 <= d <= 31):
                raise ValueError("month/day out of range")
            return m, d
        except Exception as e:
            self._logger.error(f"Invalid gardening season day format '{md}', expected 'MM-DD': {e}")
            return None

    def _is_in_gardening_season(self, dt: datetime) -> bool:
        """
        Returns True if the given datetime falls within the configured gardening season (inclusive).
        Handles seasons that may wrap across the new year.
        """
        t = (dt.month, dt.day)
        start_md = self._parse_month_day(CONFIG[Settings.GARDENING_SEASON_START]) or self._parse_month_day(Settings.GARDENING_SEASON_START.default)
        end_md = self._parse_month_day(CONFIG[Settings.GARDENING_SEASON_END]) or self._parse_month_day(Settings.GARDENING_SEASON_END.default)
        if start_md <= end_md:
            # Non-wrapping season (e.g., 03-31 .. 10-31)
            return start_md <= t <= end_md
        else:
            # Wrapping season (e.g., 11-01 .. 03-31)
            return t >= start_md or t <= end_md

    def _run(self):
        """
        Monitors and manages periodic sensor polling, orchestrates the daily watering
        schedule based on environmental conditions such as humidity, rainfall forecast,
        and time of the day. Ensures optimal watering decisions by integrating sensor
        readings and external weather predictions.

        :raises RuntimeError: If the function is called in an unsupported context.
        """
        self._logger.info("Starting WateringManager")
        # Sensors polling loop and daily schedule orchestration
        last_poll:int = 0
        poll_interval:int = CONFIG[Settings.SENSOR_READ_INTERVAL_SECONDS]
        while not self._stop.is_set():
            epoch = int(time.time())
            # Poll sensors periodically
            if epoch - last_poll >= poll_interval:
                self._poll_sensors()
                last_poll = epoch
            # Check if it's time to water (once per day)
            now = datetime.now()
            today_key = now.strftime("%Y-%m-%d")
            if self._last_watering_date != today_key:
                if now.time() >= self._start_time:
                    if not self._is_in_gardening_season(now):
                        self._logger.warning(f"Skipping watering - current time {now.isoformat()} is "
                        f"NOT in gardening season {CONFIG[Settings.GARDENING_SEASON_START]} to {CONFIG[Settings.GARDENING_SEASON_END]}")
                        self._last_watering_date = today_key
                        CONFIG[Settings.LAST_WATERING_DATE] = today_key
                        continue
                    # Decide if we cancel due to rain or already on target humidity
                    rain_prob = self.weather.get_next_12h_rain_probability()
                    if rain_prob >= self._rain_thr:
                        self._logger.info(f"Watering canceled due to rain forecast: {rain_prob*100:.2f}% > {self._rain_thr*100:.2f}%")
                        CONFIG[Settings.LAST_WATERING_DATE] = today_key
                        self._last_watering_date = today_key
                    else:
                        self._logger.info(f"Rain forecast at {rain_prob*100:.2f}% < {self._rain_thr*100:.2f}% enables watering with target humidity {self._rh_target}%")
                        self._perform_watering(self._rh_target, self._max_minutes)
                        CONFIG[Settings.LAST_WATERING_DATE] = today_key
                        self._last_watering_date = today_key
            self._stop.wait(5.0)

    def _poll_sensors(self):
        """
        Iterates through all sensor patches to collect environmental measurement data and records the readings
        such as temperature, humidity, and nutrient levels. This function handles potential failures during
        sensor polling and logs them appropriately.

        :return: None
        :rtype: None
        """
        self._logger.info("Polling sensors for all zones")
        metric:bool = CONFIG[Settings.UNITS] == UnitType.METRIC
        for patch in self.patches:
            try:
                patch.open_sensor_bus()
                self._logger.info(f"Polling sensors for zone {patch.zone.name}...")
                sensor_readings = patch.measurements() # dictionary of temp, humidity, ec, ph, salinity, tds, nitrogen, phosphorus, potassium
                if sensor_readings.get(TrendName.TEMPERATURE) is not None:
                    self._last_humidity_reading[patch.zone.name] = sensor_readings[TrendName.HUMIDITY]
                    record_rh(patch.zone.name, sensor_readings[TrendName.HUMIDITY], sensor_readings[TrendName.TEMPERATURE],
                              sensor_readings[TrendName.PH], sensor_readings[TrendName.ELECTRICAL_CONDUCTIVITY],
                              sensor_readings[TrendName.SALINITY], sensor_readings[TrendName.TOTAL_DISSOLVED_SOLIDS])
                    self._logger.info(f"RHTemp sensor {patch.rh_sensor.device_addr:#02X} readings for zone {patch.zone.name} have been recorded")
                    self._logger.info(f"RHTemp at zone {patch.zone.name}: {sensor_readings[TrendName.HUMIDITY]:.2f}% @ {sensor_readings[TrendName.TEMPERATURE]:.2f}°{'C' if metric else 'F'}")
                if sensor_readings.get(TrendName.NITROGEN) is not None:
                    record_npk(patch.zone.name, sensor_readings[TrendName.NITROGEN], sensor_readings[TrendName.PHOSPHORUS],
                               sensor_readings[TrendName.POTASSIUM])
                    self._logger.info(f"NPK sensor {patch.npk_sensor.device_addr:#02X} readings for zone {patch.zone.name} have been recorded")
                if not sensor_readings:
                    self._logger.warning(f"No sensor readings available for zone {patch.zone.name} - sensor disconnected?")
            except Exception as e:
                self._logger.error(f"Sensors reading failed for zone {patch.zone.name}: {e}", exc_info=True)
        self.patches[0].close_sensor_bus()      # leverages the first patch to close the bus, sensors are all on same bus
        rpi_temp = Measurement(datetime.now(CONFIG[Settings.LOCAL_TIMEZONE]), CPUTemperature().temperature, "°C")
        record_rpi_temperature(rpi_temp)
        self._logger.info("Sensors polling finished")

    def _perform_watering(self, target_humidity: float, max_minutes_per_zone: int):
        """
        Executes a watering cycle for each patch in the respective zones based on target
        humidity and the maximum allowed time per zone. The process involves sequentially
        watering the patches, monitoring the humidity, and calculating the water usage for
        each zone. Once the watering process is complete, all patches are turned off.

        :param target_humidity: Target humidity level at which watering should stop for
            each zone during the cycle
        :type target_humidity: float
        :param max_minutes_per_zone: Maximum duration in minutes to water each zone, after
            which the watering process for that zone stops regardless of the humidity level
        :type max_minutes_per_zone: int
        :return: None
        """

        self._logger.info("Starting watering cycle")
        metric: bool = CONFIG[Settings.UNITS] == UnitType.METRIC
        water_leak = self.pulses.read_and_reset(metric)
        if water_leak > 0:
            self._logger.warning(f"Water leakage detected between watering cycles: {water_leak:.2f} {'L' if metric else 'gal'}")
        try:
            for patch in sorted(self.patches, key=lambda p: p.zone.name):
                # check whether humidity is already above target for this zone
                if self._last_humidity_reading.get(patch.zone.name) is not None and self._last_humidity_reading[patch.zone.name] >= self._rh_target:
                    self._logger.info(f"Watering canceled for zone {patch.zone.name} due to target humidity reached: {self._last_humidity_reading[patch.zone.name]:.2f}% >= {self._rh_target:.2f}%")
                    continue

                patch.open_sensor_bus()
                self.pulses.reset_count()
                start_ts = int(time.time())
                # Turn on the zone
                patch.start_watering()
                zone_done = False
                humid_start = patch.humidity()
                self._logger.info(f"Watering zone {patch.zone.name} started at humidity level {humid_start:.2f}%")
                while not zone_done and (int(time.time()) - start_ts) < (max_minutes_per_zone * 60):
                    # Read humidity
                    moist = patch.humidity() if patch.has_rh_sensor else None
                    # Wait a bit and measure water
                    time.sleep(10)
                    # Check humidity threshold
                    if moist is not None and moist >= target_humidity:
                        zone_done = True
                        m,s = divmod((int(time.time()) - start_ts), 60)
                        self._logger.info(f"Watering zone {patch.zone.name} reached humidity level {moist:.2f}% above target {target_humidity:.2f}% after {m:02d}:{s:02d} min")
                # Turn off the zone
                patch.stop_watering()
                stop_ts = int(time.time())
                humid_stop = patch.humidity()
                patch.close_sensor_bus()
                cur_local_time = datetime.now(CONFIG[Settings.LOCAL_TIMEZONE])

                # Compute water used during this watering cycle
                water_amount = self.pulses.read_and_reset(metric)
                msmt = WateringMeasurement(cur_local_time, water_amount, "L" if metric else "gal", humid_start, humid_stop, stop_ts-start_ts)
                record_watering(patch.zone.name, msmt)
                m,s = divmod((stop_ts-start_ts), 60)
                self._logger.info(f"Zone {patch.zone.name} watered for {m:02d}:{s:02d} min. Used ~{water_amount:.2f} {'L' if metric else 'gal'} of water and ended at humidity level {humid_stop:.2f}%")
                # Wait a bit before starting the next zone; allows the water valves to close properly before starting the next one
                time.sleep(10)
        finally:
            for patch in self.patches:
                patch.stop_watering()
            self._logger.info("Watering cycle finished")
