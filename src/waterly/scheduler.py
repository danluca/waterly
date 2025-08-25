import threading
import time
import logging
from datetime import datetime, time as dtime
from typing import Optional

from .config import SENSOR_READ_INTERVAL_SECONDS
from .patch import Patch
from .pulses import PulseCounter
from .storage import settings_store, record_npk, record_rh, record_water_liters, Settings
from .weather import WeatherService


def _read_settings():
    """
    Reads settings for watering parameters (humidity target, watering start time, maximum watering
    duration per zone, rain cancel probability threshold) from a settings store.
    If any parsing errors occur, defaults are used.

    :raises ValueError: If any value cannot be properly converted to its expected type.

    :return: A tuple containing:
        - `humidity_target_percent` as a float, representing the target
          humidity percentage.
        - `watering_start_time` as a `dtime` object, indicating the time at
          which watering starts.
        - `watering_max_minutes_per_zone` as an integer, specifying the
          maximum number of minutes per zone for watering.
        - `rain_cancel_probability_threshold` as a float, representing the
          threshold probability to cancel watering due to rain.
    :rtype: tuple[float, dtime, int, float]
    """
    s = settings_store.read()
    target = float(s.get(Settings.HUMIDITY_TARGET_PERCENT, Settings.HUMIDITY_TARGET_PERCENT.default))
    start_str = s.get(Settings.WATERING_START_TIME, Settings.WATERING_START_TIME.default)
    max_minutes = int(s.get(Settings.WATERING_MAX_MINUTES_PER_ZONE, Settings.WATERING_MAX_MINUTES_PER_ZONE.default))
    rain_thr = float(s.get(Settings.RAIN_CANCEL_PROBABILITY_THRESHOLD, Settings.RAIN_CANCEL_PROBABILITY_THRESHOLD.default))
    try:
        hh, mm = [int(x) for x in start_str.split(":")]
        start_time = dtime(hh, mm)
    except Exception:
        start_time = dtime(20, 30)
    return target, start_time, max_minutes, rain_thr


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
        self._rh_target: float = Settings.HUMIDITY_TARGET_PERCENT.default
        hh, mm = [int(x) for x in Settings.WATERING_START_TIME.default.split(":")]
        self._start_time: dtime = dtime(hh, mm)
        self._max_minutes: int = Settings.WATERING_MAX_MINUTES_PER_ZONE.default
        self._rain_thr: float = Settings.RAIN_CANCEL_PROBABILITY_THRESHOLD.default
        self._logger = logging.getLogger(__name__)

    def start(self):
        """
        Starts the internal thread responsible for operation execution and updates
        settings required for the process. Ensures the appropriate method is called for
        thread execution.

        :raises RuntimeError: If the thread fails to start properly.
        """
        self._thread.start()
        self._last_watering_date, self._rh_target, self._start_time, self._max_minutes, self._rain_thr = _read_settings()

    def stop(self):
        """
        Stops the current process, sets the stop event, waits for the thread to
        terminate with a timeout, and turns off the water valves for all patches.

        :return: None
        """
        self._stop.set()
        self._thread.join(timeout=5)
        for patch in self.patches:
            patch.water_state = False

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
        poll_interval:int = SENSOR_READ_INTERVAL_SECONDS
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
                    # Decide if we cancel due to rain or already on target humidity
                    rain_prob = self.weather.get_next_12h_rain_probability()
                    if rain_prob >= self._rain_thr:
                        self._logger.info(f"Watering canceled due to rain forecast: {rain_prob*100:.2f}% > {self._rain_thr*100:.2f}%")
                        self._last_watering_date = today_key
                    else:
                        self._perform_watering(self._rh_target, self._max_minutes)
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
        for patch in self.patches:
            try:
                sensor_readings = patch.measurements() # tuple of temp, humidity, ec, ph, salinity, tds, nitrogen, phosphorus, potassium
                self._last_humidity_reading[patch.zone.name] = sensor_readings[1]
                record_rh(patch.zone.name, sensor_readings[1], sensor_readings[0], sensor_readings[3], sensor_readings[2], sensor_readings[4], sensor_readings[5])
                if len(sensor_readings) > 6:
                    record_npk(patch.zone.name, sensor_readings[6], sensor_readings[7], sensor_readings[8])
            except Exception as e:
                self._logger.error(f"Sensors reading failed for zone {patch.zone.name}: {e}", exc_info=True)

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
        try:
            for patch in sorted(self.patches, key=lambda p: p.zone.name):
                # check whether humidity is already above target for this zone
                if self._last_humidity_reading[patch.zone.name] is not None and self._last_humidity_reading[patch.zone.name] >= self._rh_target:
                    self._logger.info(f"Watering canceled for zone {patch.zone.name} due to target humidity reached: {self._last_humidity_reading[patch.zone.name]:.2f}% >= {self._rh_target:.2f}%")
                    continue

                start_ts = int(time.time())
                patch.water_state = True
                zone_done = False
                while not zone_done and (int(time.time()) - start_ts) < (max_minutes_per_zone * 60):
                    # Read humidity
                    moist = patch.humidity()
                    # Wait a bit and measure water
                    time.sleep(10)
                    # Check humidity threshold
                    if moist is not None and moist >= target_humidity:
                        zone_done = True
                # Turn off the zone
                patch.water_state = False
                stop_ts = int(time.time())
                # Compute water used during this zone
                liters = self.pulses.read_and_reset_liters(seconds=max(1, stop_ts - start_ts))
                record_water_liters(patch.zone.name, liters)
                self._logger.info(f"Zone {patch.zone.name} watered for {(stop_ts-start_ts)//60}:{(stop_ts-start_ts)%60}. Used ~{liters:.2f} L of water")
                # Wait a bit before starting the next zone; allows the water valves to close properly before starting the next one
                time.sleep(10)
        finally:
            for patch in self.patches:
                patch.water_state = False
            self._logger.info("Watering cycle finished")
