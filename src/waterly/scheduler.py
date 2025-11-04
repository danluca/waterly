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

from .dfrobot.sen0438 import SEN0438
from .config import CONFIG, Settings, UnitType, ZONES, ENV_ZONE_NAME
from .model.measurement import WateringMeasurement, Measurement, convert_measurement
from .model.water_log import WateringRecord, WateringAssessment
from .model.units import Unit
from .patch import Patch
from .pulses import PulseCounter
from .queues import receive_scheduler_message, QueueMessage, Action
from .storage import record_npk, record_rh, record_watering, record_rpi_temperature, TrendName, \
    record_watering_assessment, record_waterlog, record_env_temperature, record_env_humidity
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
        self._manual_mode: dict = {}
        self._last_sensor_poll: int = 0

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

    def _handle_thread_messages(self):
        """
        Handles messages received from the scheduler thread and performs
        corresponding actions such as updating configuration, starting watering,
        and logging relevant information.

        This method monitors the message queue for incoming messages and processes
        each message based on its action type. When receiving an UPDATE_CONFIG action,
        it updates various configuration parameters and patch settings. For the
        START_WATERING action, it processes data to initiate watering manually for a
        specific zone and duration.

        This method is called repeatedly from the thread loop (see _run method).

        :raises Exception: Logs any unhandled exceptions internally and maintains
                           the method flow.
        """
        # noinspection PyBroadException
        try:
            msg: QueueMessage|None = receive_scheduler_message()
            if msg is None:
                return
            if msg.action == Action.UPDATE_CONFIG:
                self._logger.info(f"Updating instance parameters from config")

                hh, mm = [int(x) for x in CONFIG[Settings.WATERING_START_TIME].split(":")]
                self._start_time = dtime(hh, mm)
                self._max_minutes = CONFIG[Settings.WATERING_MAX_MINUTES_PER_ZONE]
                self._last_watering_date = CONFIG[Settings.LAST_WATERING_DATE]
                for p in self.patches:
                    p.min_sensor_humidity = CONFIG[Settings.MINIMUM_SENSOR_HUMIDITY_PERCENT][p.zone.name]
                    p.target_humidity = CONFIG[Settings.HUMIDITY_TARGET_PERCENT][p.zone.name]
            elif msg.action == Action.START_WATERING:
                data = msg.data or {}
                zone_name = str(data.get("zone") or "").strip()
                minutes = data.get("minutes")
                # noinspection PyBroadException
                try:
                    minutes = int(minutes) if minutes is not None else None
                except Exception:
                    minutes = None
                if not zone_name:
                    self._logger.warning("START_WATERING message missing 'zone' name - ignoring request")
                    return
                patch = next((p for p in self.patches if p.zone.name == zone_name), None)
                if patch is None:
                    self._logger.warning(f"START_WATERING could not find zone '{zone_name}' - ignoring request")
                    return
                self._logger.info(f"Manual start watering request accepted for zone {zone_name} for {minutes or self._max_minutes} minutes")
                self._manual_mode[zone_name] = {"state": "accepted", "duration": minutes or self._max_minutes}
            elif msg.action == Action.STOP_WATERING:
                data = msg.data or {}
                zone_name = str(data.get("zone") or "").strip()
                if not zone_name:
                    self._logger.warning("STOP_WATERING message missing 'zone' name - ignoring request")
                    return
                patch = next((p for p in self.patches if p.zone.name == zone_name), None)
                if patch is None:
                    self._logger.warning(f"STOP_WATERING could not find zone '{zone_name}' - ignoring request")
                    return
                info = self._manual_mode.get(zone_name, {}) or {}
                state = info.get("state")
                now_ts = int(time.time())
                metric: bool = CONFIG[Settings.UNITS] == UnitType.METRIC
                water_unit = Unit.LITERS if metric else Unit.GALLONS
                # If running, finalize and record; if preparing/accepted, cancel without record
                if state == "running":
                    try:
                        patch.stop_watering()
                        stop_ts = now_ts
                        humid_stop = patch.humidity()
                        patch.close_sensor_bus()
                        water_amount = convert_measurement(self.pulses.read_and_reset(), Unit.LITERS, water_unit)
                        start_h = info.get("humid_start")
                        duration = max(0, stop_ts - int(info.get("start_ts", stop_ts)))
                        msmt = WateringMeasurement(datetime.now(CONFIG[Settings.LOCAL_TIMEZONE]), water_amount, water_unit,
                                                   getattr(start_h, 'value', 0.0), getattr(humid_stop, 'value', 0.0), duration)
                        try:
                            record_watering_assessment(info.get("weather_assessment"))
                            record_watering(patch.zone.name, msmt)
                            record_waterlog(WateringRecord(patch.zone, True, msmt), info.get("weather_assessment"))
                        except Exception as e:
                            self._logger.error(f"Failed to record STOP_WATERING measurements for zone {patch.zone.name}: {e}", exc_info=True)
                        m, s = divmod(duration, 60)
                        self._logger.info(f"Manual watering STOP for zone {zone_name} at {humid_stop.value:.2f}% RH after {m:02d}:{s:02d}; used ~{msmt.value:.2f} {msmt.unit}")
                    finally:
                        self._manual_mode.pop(zone_name, None)
                else:
                    # Not running; just ensure everything is closed and stopped
                    patch.stop_watering()
                    patch.close_sensor_bus()
                    self._manual_mode.pop(zone_name, None)
                    self._logger.info(f"Manual watering STOP for zone {zone_name} acknowledged (not running)")
        except Exception as e:
            self._logger.error(f"Failed to handle scheduler message: {e}", exc_info=True)
            pass

    def _handle_sensor_polling(self):
        """
        Handles the periodic polling of sensors.

        This method is called repeatedly from the thread loop (see _run method) - checks the time elapsed since the last
        sensor polling and invokes the sensor polling routine if the polling interval has been
        exceeded. It ensures that sensors are periodically polled based on a predefined interval.

        :rtype: None
        """
        epoch = int(time.time())
        poll_interval: int = int(CONFIG[Settings.SENSOR_READ_INTERVAL_SECONDS])
        # Poll sensors periodically
        if epoch - self._last_sensor_poll >= poll_interval:
            self._poll_sensors()
            self._last_sensor_poll = epoch

    def _handle_auto_watering(self):
        """
        Checks and handles the automatic garden watering process. This method ensures that
        the watering is performed only once per day, taking into account various conditions
        such as the current time, gardening season, weather assessment, and drought status.

        This function performs the following logic:
        - Verifies if the current time is past the start time for watering.
        - Validates if the current date falls within the defined gardening season. If not, watering is skipped with a
          recorded assessment of the reason.
        - Checks weather conditions and determines if watering is required. Assessment is made using weather data and
          drought conditions.
        - Executes watering if conditions are favorable and updates the configuration with the last watering date.
        - Skips watering if conditions do not meet the criteria and logs relevant information.

        This method is called repeatedly from the thread loop (see _run method).

        :rtype: None
        """
        # Check if it's time to water (once per day)
        now = datetime.now(CONFIG[Settings.LOCAL_TIMEZONE])
        today_key = now.strftime("%Y-%m-%d")
        if self._last_watering_date != today_key:
            if now.time() >= self._start_time:
                if not self._is_in_gardening_season(now):
                    msg = f"NOT in gardening season {CONFIG[Settings.GARDENING_SEASON].get('start')} to {CONFIG[Settings.GARDENING_SEASON].get('end')}"
                    self._logger.warning(f"Skipping watering - current time {now.isoformat()} is {msg}")
                    self._last_watering_date = today_key
                    CONFIG[Settings.LAST_WATERING_DATE] = today_key
                    record_watering_assessment(WateringAssessment(enabled=False, reason={"warn": msg}, start_time=now))
                    return
                # weather assessment
                has_drought = any(patch.has_drought() for patch in self.patches)
                weather_assessment = self.weather.should_water_garden()
                weather_assessment.reason["drought"] = has_drought
                weather_assessment.enabled = weather_assessment.enabled or has_drought
                # persist current assessment
                record_watering_assessment(weather_assessment)
                # Decide if we cancel due to weather
                if weather_assessment.enabled:
                    self._logger.info("Weather data enables watering")
                    self._perform_watering(weather_assessment)
                    CONFIG[Settings.LAST_WATERING_DATE] = today_key
                    self._last_watering_date = today_key
                else:
                    self._logger.info("Watering canceled due to weather current conditions and forecast")
                    CONFIG[Settings.LAST_WATERING_DATE] = today_key
                    self._last_watering_date = today_key

    def _handle_manual_watering(self):
        """
        Non-blocking manual watering state machine.

        This method is called repeatedly from the thread loop (see _run).
        When a START_WATERING message is received, _handle_thread_messages places an entry
        in self._manual_mode[zone_name] = {"state": "accepted", "duration": minutes or max}.

        Here we progress each zone through states without sleeping:
        - accepted → preparing: stop other zones; set grace window to allow valves to close
        - preparing → running: after grace, open bus, reset pulses, capture start humidity, start watering
        - running → finalize: when duration reached or target humidity reached; stop/close and persist records
        """
        if not self._manual_mode:
            return

        now_ts = int(time.time())
        metric: bool = CONFIG[Settings.UNITS] == UnitType.METRIC
        water_unit = Unit.LITERS if metric else Unit.GALLONS

        zones = list(self._manual_mode.keys())
        for zone_name in zones:
            info = self._manual_mode.get(zone_name) or {}
            try:
                patch = next((p for p in self.patches if p.zone.name == zone_name), None)
                if patch is None:
                    self._logger.warning(f"Manual watering requested for unknown zone '{zone_name}', discarding")
                    del self._manual_mode[zone_name]
                    continue

                # Initialize defaults
                state = info.get("state", "accepted")
                requested_minutes = info.get("duration")
                # noinspection PyBroadException
                try:
                    requested_minutes = int(requested_minutes) if requested_minutes is not None else None
                except Exception:
                    requested_minutes = None
                max_minutes = self._max_minutes if requested_minutes is None else max(1, min(int(requested_minutes), int(self._max_minutes)))
                info["max_minutes"] = max_minutes

                if state == "accepted":
                    # Move to preparing: stop other zones and wait a short grace period for valves to close.
                    self._logger.info(f"Manual watering accepted for zone {zone_name}; preparing to start (up to {max_minutes} min)")
                    stopped_any = False
                    for p in self.patches:
                        if p.zone.name != patch.zone.name and p.water_state:
                            p.stop_watering()
                            stopped_any = True
                    # Set the grace window if we had to stop others, otherwise minimal delay
                    grace_sec = 10 if stopped_any else 0
                    info.update({
                        "state": "preparing",
                        "grace_until": now_ts + grace_sec,
                        "weather_assessment": WateringAssessment(start_time=datetime.now(CONFIG[Settings.LOCAL_TIMEZONE]), reason={"manual": True, "zone": zone_name}, enabled=True)
                    })
                    self._manual_mode[zone_name] = info
                    continue

                if state == "preparing":
                    if now_ts < int(info.get("grace_until", now_ts)):
                        # Still within grace period; wait for the next tick
                        continue
                    # Start the watering sequence (non-blocking)
                    try:
                        patch.open_sensor_bus()
                    except Exception as e:
                        # try to continue even if open fails; log and abort this run
                        self._logger.error(f"Failed to open sensor bus for zone {zone_name}: {e}", exc_info=True)
                        del self._manual_mode[zone_name]
                        continue
                    self.pulses.reset_count()
                    humid_start = patch.humidity()
                    info["humid_start"] = humid_start
                    patch.start_watering()
                    info.update({
                        "state": "running",
                        "start_ts": now_ts
                    })
                    self._logger.info(f"Manual watering started for zone {zone_name} at {humid_start.value:.2f}% RH")
                    self._manual_mode[zone_name] = info
                    continue

                if state == "running":
                    start_ts = int(info.get("start_ts", now_ts))
                    elapsed = now_ts - start_ts
                    time_exceeded = elapsed >= (int(info.get("max_minutes", self._max_minutes)) * 60)
                    if time_exceeded:
                        # Finalize watering and persist records
                        patch.stop_watering()
                        stop_ts = now_ts
                        patch.open_sensor_bus()     # ensure the bus is open for final readings (a poll sensor call while in running state would close the bus)
                        humid_stop = patch.humidity()
                        # noinspection PyBroadException
                        try:
                            patch.close_sensor_bus()
                        except Exception:
                            pass
                        water_amount = convert_measurement(self.pulses.read_and_reset(), Unit.LITERS, water_unit)
                        start_h = info.get("humid_start")
                        duration = max(0, stop_ts - int(info.get("start_ts", stop_ts)))
                        msmt = WateringMeasurement(datetime.now(CONFIG[Settings.LOCAL_TIMEZONE]), water_amount, water_unit,
                                                   getattr(start_h, 'value', 0.0), getattr(humid_stop, 'value', 0.0), duration)
                        try:
                            record_watering_assessment(info.get("weather_assessment"))
                            record_watering(patch.zone.name, msmt)
                            record_waterlog(WateringRecord(patch.zone, True, msmt), info.get("weather_assessment"))
                        except Exception as e:
                            self._logger.error(f"Failed to record manual watering measurements for zone {patch.zone.name}: {e}", exc_info=True)
                        m, s = divmod(duration, 60)
                        self._logger.info(f"Manual watering finished for zone {zone_name} at {humid_stop.value:.2f}% RH after {m:02d}:{s:02d}; used ~{msmt.value:.2f} {msmt.unit} of water")
                        # Cleanup
                        del self._manual_mode[zone_name]
                        continue

                # Keep entry if running and not done
                self._manual_mode[zone_name] = info

            except Exception as e:
                self._logger.error(f"Manual watering handler error for zone {zone_name}: {e}", exc_info=True)
                # Best-effort cleanup to keep loop healthy
                # noinspection PyBroadException
                try:
                    patch = next((p for p in self.patches if p.zone.name == zone_name), None)
                    if patch is not None:
                        patch.stop_watering()
                        patch.close_sensor_bus()
                except Exception:
                    pass
                self._manual_mode.pop(zone_name, None)
        

    def _run(self):
        """
        Monitors and manages periodic sensor polling, orchestrates the daily watering
        schedule.

        This method loops continuously every 15 seconds through various events such as sensor polling,
        watering, and thread messages.

        :raises RuntimeError: If the function is called in an unsupported context.
        """
        self._logger.info("Starting WateringManager")
        # Sensors polling loop and daily schedule orchestration
        while not self._stop.is_set():
            self._handle_thread_messages()

            self._handle_sensor_polling()

            self._handle_manual_watering()  # we give priority to manually invoked watering

            self._handle_auto_watering()

            self._stop.wait(15.0)

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
        # read env temperature and humidity
        # Get the Zone object (or None if not found)
        env_zone = next((z for z in ZONES.values() if z.name == ENV_ZONE_NAME), None)
        sensor = SEN0438(env_zone.rh_sensor_address)
        sensor.open()
        env_temp = Measurement(sensor.read_temperature_c(), Unit.CELSIUS, datetime.now(CONFIG[Settings.LOCAL_TIMEZONE]))
        record_env_temperature(env_temp if metric else env_temp.convert(Unit.FAHRENHEIT))
        time.sleep(0.25)
        env_humid = Measurement(sensor.read_humidity(), Unit.PERCENT, datetime.now(CONFIG[Settings.LOCAL_TIMEZONE]))
        record_env_humidity(env_humid)
        sensor.close()
        self._logger.info("Storage of sensor readings finished")

    def _perform_watering(self, weather_assessment: WateringAssessment):
        """
        Executes a watering cycle for each patch in the respective zones based on target
        humidity and the maximum allowed time per zone. The process involves sequentially
        watering the patches, monitoring the humidity, and calculating the water usage for
        each zone. Once the watering process is complete, all patches are turned off.

        This method is blocking and will wait for the watering to complete before returning.

        :param weather_assessment: watering assessment object of the weather forecast - used for record keeping, does not affect watering
        :type weather_assessment: WateringAssessment
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
                                      f"{patch.current_humidity.value:.2f}% >= {patch.target_humidity:.2f}%")
                    msmt = WateringMeasurement(patch.current_humidity.timestamp, 0, water_unit, patch.target_humidity,
                                               patch.current_humidity.value, 0)
                    record_waterlog(WateringRecord(patch.zone, False, msmt), weather_assessment)
                    continue

                patch.open_sensor_bus()
                self.pulses.reset_count()
                start_ts = int(time.time())
                # Turn on the zone
                patch.start_watering()
                zone_done = False
                humid_start = patch.humidity()
                self._logger.info(f"Watering zone {patch.zone.name} started at humidity level {humid_start.value:.2f}%")
                while not zone_done and (int(time.time()) - start_ts) < (self._max_minutes * 60):
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
                water_amount = convert_measurement(self.pulses.read_and_reset(), Unit.LITERS, water_unit)
                msmt = WateringMeasurement(cur_local_time, water_amount, water_unit, humid_start.value, humid_stop.value, stop_ts-start_ts)
                record_watering(patch.zone.name, msmt)
                m,s = divmod((stop_ts-start_ts), 60)
                self._logger.info(f"Zone {patch.zone.name} watered for {m:02d}:{s:02d} min. Used ~{msmt.value:.2f} "
                                  f"{msmt.unit} of water and ended at humidity level {humid_stop.value:.2f}%")
                record_waterlog(WateringRecord(patch.zone, True, msmt), weather_assessment)
                # Wait a bit before starting the next zone; allows the water valves to close properly before starting the next one
                time.sleep(10)
        finally:
            for patch in self.patches:
                patch.stop_watering()
            self._logger.info("Watering cycle finished")
