#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#

import threading
import time
import logging
from datetime import datetime, time as dtime
from typing import Optional
from gpiozero import CPUTemperature
from waterly.model.units import Unit

from .config import CONFIG, Settings, UnitType
from .model.measurement import WateringMeasurement, Measurement
from .patch import Patch
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
        hh, mm = [int(x) for x in CONFIG[Settings.WATERING_START_TIME].split(":")]
        self._start_time: dtime = dtime(hh, mm)
        self._max_minutes: int = CONFIG[Settings.WATERING_MAX_MINUTES_PER_ZONE]
        self._logger = logging.getLogger(__name__)
        self._last_humidity_reading: dict[str, float] = {}

    def start(self):
        """
        Starts the internal thread responsible for operation execution and updates
        settings required for the process. Ensures the appropriate method is called for
        thread execution.

        :raises RuntimeError: If the thread fails to start properly.
        """
        self._thread.start()
        self._last_watering_date = CONFIG[Settings.LAST_WATERING_DATE]
        hh, mm = [int(x) for x in CONFIG[Settings.WATERING_START_TIME].split(":")]
        self._start_time = dtime(hh, mm)
        self._max_minutes = CONFIG[Settings.WATERING_MAX_MINUTES_PER_ZONE]

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
        start_md = self._parse_month_day(CONFIG[Settings.GARDENING_SEASON].get("start") or Settings.GARDENING_SEASON.default.get("start"))
        end_md = self._parse_month_day(CONFIG[Settings.GARDENING_SEASON].get("stop") or Settings.GARDENING_SEASON.default.get("stop"))
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
            now = datetime.now(CONFIG[Settings.LOCAL_TIMEZONE])
            today_key = now.strftime("%Y-%m-%d")
            if self._last_watering_date != today_key:
                if now.time() >= self._start_time:
                    if not self._is_in_gardening_season(now):
                        self._logger.warning(f"Skipping watering - current time {now.isoformat()} is "
                            f"NOT in gardening season {CONFIG[Settings.GARDENING_SEASON].get('start')} to {CONFIG[Settings.GARDENING_SEASON].get('end')}")
                        self._last_watering_date = today_key
                        CONFIG[Settings.LAST_WATERING_DATE] = today_key
                        continue
                    # Decide if we cancel due to weather or already on target humidity
                    has_drought = any(patch.has_drought() for patch in self.patches)
                    should_water = self.weather.should_water_garden() or has_drought
                    if should_water:
                        self._logger.info("Weather data enables watering")
                        self._perform_watering(self._max_minutes)
                        CONFIG[Settings.LAST_WATERING_DATE] = today_key
                        self._last_watering_date = today_key
                    else:
                        self._logger.info("Watering canceled due to weather current conditions and forecast")
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
        metric: bool = CONFIG[Settings.UNITS] == UnitType.METRIC
        all_readings: dict[Patch, dict[TrendName, Measurement]] = {}
        for patch in self.patches:
            try:
                patch.open_sensor_bus()
                time.sleep(0.25)
                self._logger.info(f"Polling sensors for zone {patch.zone.name}...")
                all_readings[patch] = patch.measurements()  # dictionary of temp, humidity, ec, ph, salinity, tds, nitrogen, phosphorus, potassium
            except Exception as e:
                self._logger.error(f"Sensors reading failed for zone {patch.zone.name}: {e}", exc_info=True)
            time.sleep(0.25)
        self.patches[0].close_sensor_bus()      # leverages the first patch to close the bus, sensors are all on same bus
        self._logger.info("Polling sensors for all zones complete. Storing readings")

        for patch, readings in all_readings.items():
            zone = patch.zone.name
            try:
                if readings.get(TrendName.TEMPERATURE) is not None:
                    self._last_humidity_reading[zone] = readings[TrendName.HUMIDITY].value
                    record_rh(zone, readings[TrendName.HUMIDITY], readings[TrendName.TEMPERATURE], readings[TrendName.PH],
                              readings[TrendName.ELECTRICAL_CONDUCTIVITY], readings[TrendName.SALINITY], readings[TrendName.TOTAL_DISSOLVED_SOLIDS])
                    temp = readings[TrendName.TEMPERATURE].convert(Unit.CELSIUS if metric else Unit.FAHRENHEIT)
                    self._logger.info(f"RHTemp at zone {zone}: {readings[TrendName.HUMIDITY].value:.2f}% @ "
                                      f"{temp.value:.2f} {temp.unit}")
                    self._logger.info(f"RHTemp sensor readings @ {patch.rh_sensor.device_addr:#02X} for zone {zone} have been recorded")
                if readings.get(TrendName.NITROGEN) is not None:
                    record_npk(zone, readings[TrendName.NITROGEN], readings[TrendName.PHOSPHORUS], readings[TrendName.POTASSIUM])
                    self._logger.info(f"NPK sensor readings @ {patch.npk_sensor.device_addr:#02X} for zone {zone} have been recorded")
            except Exception as e:
                self._logger.error(f"Sensors readings storage failed for zone {zone}: {e}", exc_info=True)
        rpi_temp = Measurement(CPUTemperature().temperature, Unit.CELSIUS, datetime.now(CONFIG[Settings.LOCAL_TIMEZONE]))
        record_rpi_temperature(rpi_temp if metric else rpi_temp.convert(Unit.FAHRENHEIT))
        self._logger.info("Storage of sensor readings finished")

    def _perform_watering(self, max_minutes_per_zone: int):
        """
        Executes a watering cycle for each patch in the respective zones based on target
        humidity and the maximum allowed time per zone. The process involves sequentially
        watering the patches, monitoring the humidity, and calculating the water usage for
        each zone. Once the watering process is complete, all patches are turned off.

        :param max_minutes_per_zone: Maximum duration in minutes to water each zone, after
            which the watering process for that zone stops regardless of the humidity level
        :type max_minutes_per_zone: int
        :return: None
        """

        self._logger.info("Starting watering cycle")
        metric: bool = CONFIG[Settings.UNITS] == UnitType.METRIC
        water_unit = Unit.LITERS if metric else Unit.GALLONS
        water_leak = Measurement(self.pulses.read_and_reset(), Unit.LITERS)
        if water_leak.value > 0:
            self._logger.warning(f"Water leakage detected between watering cycles: {water_leak.convert(water_unit).value:.2f} {water_unit}")
        try:
            for patch in sorted(self.patches, key=lambda p: p.zone.name):
                # check whether humidity is already above target for this zone
                if not patch.needs_watering():
                    self._logger.info(f"Watering canceled for zone {patch.zone.name} due to target humidity reached: "
                                      f"{patch.current_humidity:.2f}% >= {patch.target_humidity:.2f}%")
                    continue

                patch.open_sensor_bus()
                self.pulses.reset_count()
                start_ts = int(time.time())
                # Turn on the zone
                patch.start_watering()
                zone_done = False
                humid_start = patch.humidity()
                self._logger.info(f"Watering zone {patch.zone.name} started at humidity level {humid_start.value:.2f}%")
                while not zone_done and (int(time.time()) - start_ts) < (max_minutes_per_zone * 60):
                    # Wait a bit and measure water
                    time.sleep(10)
                    # Check humidity threshold
                    if not patch.check_needs_watering():
                        zone_done = True
                        m,s = divmod((int(time.time()) - start_ts), 60)
                        self._logger.info(f"Watering zone {patch.zone.name} reached humidity level {patch.current_humidity.value:.2f}% "
                                          f"above target {patch.target_humidity:.2f}% after {m:02d}:{s:02d} min")
                # Turn off the zone
                patch.stop_watering()
                stop_ts = int(time.time())
                humid_stop = patch.humidity()
                patch.close_sensor_bus()
                cur_local_time = datetime.now(CONFIG[Settings.LOCAL_TIMEZONE])

                # Compute water used during this watering cycle
                water_amount = self.pulses.read_and_reset()
                msmt = WateringMeasurement(cur_local_time, water_amount, Unit.LITERS, humid_start.value, humid_stop.value, stop_ts-start_ts)
                record_watering(patch.zone.name, msmt if metric else msmt.convert(Unit.GALLONS))
                m,s = divmod((stop_ts-start_ts), 60)
                self._logger.info(f"Zone {patch.zone.name} watered for {m:02d}:{s:02d} min. Used ~{msmt.convert(water_unit).value:.2f} "
                                  f"{water_unit} of water and ended at humidity level {humid_stop.value:.2f}%")
                # Wait a bit before starting the next zone; allows the water valves to close properly before starting the next one
                time.sleep(10)
        finally:
            for patch in self.patches:
                patch.stop_watering()
            self._logger.info("Watering cycle finished")
