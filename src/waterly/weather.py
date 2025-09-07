#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#

import threading
import pytz
import logging
import requests

from datetime import datetime, timedelta, tzinfo
from typing import Optional
from .config import DEFAULT_TIMEZONE, DATA_DIR, CONFIG, Settings, UnitType
from .model.measurement import convert_measurement
from .storage import write_text_file

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

class WeatherData:
    """
    Represents weather data for a specific timestamp.

    This class encapsulates weather-related metrics such as temperature, soil
    humidity, and precipitation for a given timestamp. It is designed to model
    weather data efficiently, allowing access to these metrics through properties.

    :ivar _timestamp: The timestamp associated with the weather data.
    :type _timestamp: datetime
    :ivar _temperature: The temperature recorded at the given timestamp.
    :type _temperature: float
    :ivar _temperature_unit: The unit of temperature measurement.
    :type _temperature_unit: str
    :ivar _soil_humidity: Soil humidity expressed as a percentage (m³/m³).
    :type _soil_humidity: float
    :ivar _precipitation_amount: Precipitation amount at the given timestamp.
    :type _precipitation_amount: float
    :ivar _precipitation_unit: The unit of precipitation measurement.
    :type _precipitation_unit: str
    :ivar _precipitation_prob: Probability of precipitation at the given timestamp.
    :type _precipitation_prob: float
    """
    def __init__(self, timestamp: datetime, temperature: float, temperature_unit: str, soil_humidity: float, precipitation_amount: float, precipitation_unit: str, precipitation_prob: float):
        self._timestamp = timestamp # local time
        self._temperature = temperature # in current units, 'C or 'F
        self._temperature_unit = temperature_unit
        self._soil_humidity = soil_humidity # in m3/m3 (percentage)
        self._precipitation_amount = precipitation_amount # in current units, mm or inch
        self._precipitation_unit = precipitation_unit
        self._precipitation_prob = precipitation_prob   # percentage

    @property
    def timestamp(self) -> datetime:
        return self._timestamp

    @property
    def temperature(self) -> float:
        return self._temperature

    @property
    def soil_humidity(self) -> float:
        return self._soil_humidity

    @property
    def precipitation_amount(self) -> float:
        return self._precipitation_amount

    @property
    def precipitation_prob(self) -> float:
        return self._precipitation_prob

    @property
    def temperature_unit(self) -> str:
        return self._temperature_unit

    @property
    def precipitation_unit(self) -> str:
        return self._precipitation_unit

    def __str__(self):
        return f"WeatherData[timestamp={self._timestamp}, temperature={self._temperature} {self._temperature_unit}, soil_humidity={self._soil_humidity}, precipitation_amount={self._precipitation_amount} {self._precipitation_unit}, precipitation_prob={self._precipitation_prob}]"
    def __repr__(self):
        return self.__str__()

class WeatherService:
    """
    Provides weather forecasting services by collecting and processing weather data.

    This class is designed to interface with the Open-Meteo weather API to fetch weather
    data for a specific location. It manages its own threading mechanism to periodically
    update forecasts, storing the next 12-hour precipitation probability and the time of
    the last update. The service is built to operate in a daemon thread, running until
    explicitly stopped.

    :ivar _forecast_days: The number of forecast days requested from the weather API. Hardcoded as 3 for now.
    :type _forecast_days: int
    :ivar _timezone: The timezone of the weather data, determined from the API response or set to a default.
    :type _timezone: pytz.BaseTzInfo
    :ivar _last_update: The timestamp of the last successful weather data update.
    :type _last_update: datetime | None
    """
    RAIN_12H_THRESHOLD_INCHES = 0.02    # an approximated 1.5 inches of rain per week means 0.1 inch per 12-hour interval; however, rain of 0.02 inches is enough from experience

    def __init__(self):
        self._lock = threading.RLock()
        self._weather_data: list[WeatherData] = []  # 48 hours worth of data, 24 hours past and 24 hours future
        self._forecast_days: int = 3    # hardcoded for now using a common sense value
        self._past_days: int = 1        # number of past days to consider for weather data
        self._timezone: pytz.BaseTzInfo = CONFIG[Settings.LOCAL_TIMEZONE]
        self._last_update: Optional[datetime] = CONFIG[Settings.WEATHER_LAST_CHECK_TIMESTAMP]
        self._update_offset_from_watering_time: int = CONFIG[Settings.WEATHER_CHECK_OFFSET_FROM_WATERING_SECONDS]
        self._precip_prob_threshold: float = CONFIG[Settings.RAIN_CANCEL_PROBABILITY_THRESHOLD]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="WeatherService", daemon=True)
        self._logger = logging.getLogger(__name__)

    def start(self):
        """
        Starts the internal thread execution.

        The `start` method is responsible for triggering the execution of the internal
        thread managed by the instance. Once called, the thread begins its activity
        in a separate execution flow.

        """
        # TODO: read last saved weather data, if any
        self._thread.start()

    def stop(self):
        """
        Stops the running thread safely.

        This method ensures the thread is stopped by setting an appropriate flag
        and waiting for the thread to terminate within a defined timeout.

        :return: None
        """
        self._stop.set()
        self._thread.join(timeout=5)

    def should_water_garden(self) -> bool:
        """
        Determines whether it is recommended to water the garden based on the current and past weather data

        It is recommended for a garden to receive about 1.5 inches of rain per week. This translates to ~ 0.1 inch per
        12-hour interval. Therefore,the algorithm we use returns false when either of the following conditions are met:
         - the past 12 hours have had more than 0.1 inch of rain
         - the next 12-hour rain probability is more than 50% and the amount of rain over 0.1 inch
        Otherwise, it returns true - the garden should be watered.
        :return: True if it is recommended to water the garden, False otherwise.
        :rtype: bool
        """
        if not self._weather_data:
            self._logger.info("Weather Data assessment: data not available yet - defaulting to enable watering.")
            return True
        now = datetime.now(self._timezone)
        past_12h_rain = 0.0
        past_12h_soil_humidity = 0.0
        next_12h_prob = 0.0
        next_12h_rain = 0.0
        next_12h_soil_humidity = 0.0
        horizon_from = now - timedelta(hours=12)
        horizon_to = now + timedelta(hours=12)
        past_data_points = 0    # hourly data points
        future_data_points = 0  # hourly data points, should have a minimum of 6
        for w in self._weather_data:
            if now > w.timestamp >= horizon_from:
                past_12h_rain += w.precipitation_amount
                past_12h_soil_humidity += w.soil_humidity
                past_data_points += 1
            if horizon_to <= w.timestamp < now:
                next_12h_prob = max(next_12h_prob, w.precipitation_prob)
                next_12h_rain += w.precipitation_amount
                next_12h_soil_humidity += w.soil_humidity
                future_data_points += 1
        precip_unit: str = self._weather_data[-1].precipitation_unit
        self._logger.info(f"Weather Data points: Past 12h: {past_data_points}, Future 12h: {future_data_points}")
        self._logger.info(f"Weather Data assessment: Past 12h rain: {past_12h_rain:.2f} {precip_unit}, Future 12h rain: {next_12h_rain:.2f} {precip_unit} with {next_12h_prob:.2f}% chance")
        past_12h_soil_humidity /= past_data_points if past_data_points > 0 else 1.0
        next_12h_soil_humidity /= future_data_points if future_data_points > 0 else 1.0
        self._logger.info(f"Weather Data assessment: Past 12h average soil humidity: {past_12h_soil_humidity*100.0:.2f}%, Future 12h average soil humidity: {next_12h_soil_humidity*100.0:.2f}%")
        rain_12_threshold = convert_measurement(self.RAIN_12H_THRESHOLD_INCHES, "inch", precip_unit)
        should_not_water = past_12h_rain > rain_12_threshold or (next_12h_prob > self._precip_prob_threshold and next_12h_rain > rain_12_threshold)
        return (not should_not_water) or future_data_points < 6

    def get_last_update(self) -> Optional[datetime]:
        """
        Retrieves the last update timestamp if available. This method is thread-safe
        and accesses the stored timestamp under a lock to ensure consistency when
        used in a multithreaded environment.

        :return: The datetime object representing the last update timestamp, or None
            if no update has been recorded.
        :rtype: Optional[datetime]
        """
        with self._lock:
            return self._last_update

    def get_timezone(self) -> pytz.BaseTzInfo:
        """
        Retrieve the timezone information.

        This method fetches the timezone associated with the object. The returned
        timezone is thread-safe and is retrieved while ensuring proper locking
        for consistent access.

        :return: The timezone information.
        :rtype: tzinfo
        """
        with self._lock:
            return self._timezone

    def _save_weather_data(self, data: str):
        """
        Saves the provided weather data to a file, indexing it by the current year and timestamp.
        The data is assumed to be in JSON format and will be stored in a structured directory
        within the specified data directory.

        :param data: Weather data to be saved. It should be in JSON format.
        :type data: str
        """
        with self._lock:
            # save the raw response for reference - we have other data elements of interest (precipitation, soil moisture)
            now = datetime.now(self._timezone)
            # index by current year
            filename = f"{DATA_DIR}/{now.year}/weather-{now.strftime('%m%d-%H%M')}.json"
            write_text_file(filename, data)

    def _run(self):
        """
        Performs periodic weather updates while monitoring for stopping events. It checks
        the current timezone against the locally configured timezone and updates the
        local configuration if a change is detected. Continuous operation is sustained
        until a stop signal is triggered.

        The method also handles exceptions during execution and logs error or
        informational events accordingly.

        :raises Exception: Logs the encountered exception during weather updates.
        :return: Does not return any value.
        """
        while not self._stop.is_set():
            try:
                now = datetime.now(self._timezone)
                h, m = tuple(map(int, CONFIG[Settings.WATERING_START_TIME].split(":")))
                watering_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if watering_time < now:
                    watering_time += timedelta(days=1)
                time_until_watering: int = int((watering_time - now).total_seconds())

                # Define the pre-watering window [window_start, watering_time)
                window_start = watering_time - timedelta(seconds=self._update_offset_from_watering_time)

                # Determine wait time and whether to perform an update based on window
                pre_m, pre_s = divmod(self._update_offset_from_watering_time, 60)
                weather_check_done:bool = False
                if now < window_start:
                    # BEFORE pre-watering window: run at regular interval, but don't overshoot the window start
                    wait_time = min(CONFIG[Settings.WEATHER_CHECK_INTERVAL_SECONDS], max(5, int((window_start - now).total_seconds())))
                    # Rate-limit: skip if we updated more recently than our wait_time
                    update_age = (now - self._last_update).total_seconds() if self._last_update else None
                    if update_age is not None and update_age < wait_time:
                        wait_m, wait_s = divmod(int(wait_time), 60)
                        age_m, age_s = divmod(int(update_age), 60)
                        age_h, age_m = divmod(age_m, 60)
                        self._logger.info(f"Skipping weather update - last update was {age_h:02d}h:{age_m:02d}m:{age_s:02d}s ago and "
                            f"waiting time is {wait_m:d}:{wait_s:02d} min. Note the pre-watering window is {pre_m:d}:{pre_s:02d} min.")
                        # fall-through to sleep
                    else:
                        weather_check_done = self._update_weather()
                elif window_start <= now < watering_time:
                    # INSIDE pre-watering window: allow only a single update in this window
                    last_update_in_window = self._last_update and (self._last_update >= window_start)
                    if not last_update_in_window:
                        self._logger.info(f"Entering pre-watering window of {pre_m:02d}:{pre_s:02d} min; performing a single weather update.")
                        weather_check_done = self._update_weather()
                    else:
                        self._logger.info(f"Pre-watering window of {pre_m:02d}:{pre_s:02d} min already updated weather at {self._last_update.strftime('%H:%M:%S')}; skipping additional updates.")
                    # Sleep until watering time to avoid repeated updates in the window
                    wait_time = max(5, int((watering_time - now).total_seconds()))
                else:
                    # Shouldn't happen because watering_time is always in the future, but be safe.
                    wait_time = CONFIG[Settings.WEATHER_CHECK_INTERVAL_SECONDS]

                if weather_check_done:
                    with self._lock:
                        if (CONFIG[Settings.LOCAL_TIMEZONE] is None) or (CONFIG[Settings.LOCAL_TIMEZONE] != self._timezone):
                            self._logger.info(f"Local timezone changed from {CONFIG[Settings.LOCAL_TIMEZONE]} to {self._timezone}")
                            CONFIG[Settings.LOCAL_TIMEZONE] = self._timezone
            except Exception as e:
                self._logger.error(f"Weather update failed: {e}", exc_info=True)
                wait_time = CONFIG[Settings.WEATHER_CHECK_INTERVAL_SECONDS]
            self._stop.wait(wait_time)

    def _update_weather(self) -> bool:
        """
        Updates the current weather data by fetching information from the Open-Meteo API and calculates the probability
        of rain for the next 12 hours. The weather data is saved, and the timezone is determined based on the fetched
        information. If an invalid timezone is encountered, a default timezone is used.
        The Open-Meteo API URL can be created at https://open-meteo.com/en/docs. Example API request:
        https://api.open-meteo.com/v1/forecast?latitude=45.0341769&longitude=-93.4641572&hourly=temperature_2m,precipitation_probability,soil_moisture_1_to_3cm,precipitation&current=temperature_2m,relative_humidity_2m,precipitation,surface_pressure&timezone=auto&past_days=1&forecast_days=3&wind_speed_unit=mph&temperature_unit=fahrenheit&precipitation_unit=inch

        :raises requests.exceptions.HTTPError: If the HTTP request returns an unsuccessful status code.
        :raises requests.exceptions.RequestException: For other request-related exceptions' response.
        :return: whether the weather data was successfully updated.
        :rtype: bool
        """
        metric:bool = CONFIG[Settings.UNITS] == UnitType.METRIC
        params = {
            "latitude": CONFIG[Settings.LATITUDE],
            "longitude": CONFIG[Settings.LONGITUDE],
            "hourly": "precipitation_probability,temperature_2m,precipitation,soil_moisture_1_to_3cm",
            "forecast_days": self._forecast_days,
            "past_days": self._past_days,
            "current": "temperature_2m,relative_humidity_2m,precipitation,surface_pressure",
            "temperature_unit": "celsius" if metric else "fahrenheit",
            "precipitation_unit": "mm" if metric else "inch",
            "timezone": "auto"  # Open-Meteo can auto-detect by coordinates
        }
        result:bool = False
        try:
            r = requests.get(OPEN_METEO_URL, params=params, timeout=20)
            r.raise_for_status()
            self._save_weather_data(r.text)
            data = r.json()
            hourly = data.get("hourly", {})
            hourly_units = data.get("hourly_units", {})
            current = data.get("current", {})
            current_units = data.get("current_units", {})
            probs = hourly.get("precipitation_probability", [])
            soil = hourly.get("soil_moisture_1_to_3cm", [])
            precip = hourly.get("precipitation", [])
            temps = hourly.get("temperature_2m", [])
            times = hourly.get("time", [])
            # determine local timezone
            try:
                self._timezone = pytz.timezone(data.get("timezone", "UTC"))
            except pytz.UnknownTimeZoneError:
                self._timezone = DEFAULT_TIMEZONE
                self._logger.warning(f"Invalid timezone '{data.get('timezone', 'UTC')}' for pytz/TZDB version {pytz.VERSION}. Using default timezone {DEFAULT_TIMEZONE} instead.")

            now = datetime.now(self._timezone)
            horizon_from = now - timedelta(hours=24)
            horizon_to = now + timedelta(hours=24)
            wdata: list[WeatherData] = []
            for t, p, s, r, deg in zip(times, probs, soil, precip, temps):
                # noinspection PyBroadException
                try:
                    ts = self._timezone.localize(datetime.fromisoformat(t.replace("Z", "+00:00")).replace(tzinfo=None))
                except Exception:
                    continue
                if horizon_from <= ts <= horizon_to:
                    wdata.append(WeatherData(ts, deg, hourly_units["temperature_2m"], s, r, hourly_units["precipitation"], p / 100.0))
            # for previous 12h determine the amount of rain and for next 12 hours probability of rain and amount of rain
            past_12h_rain = 0.0
            next_12h_prob = 0.0
            next_12h_rain = 0.0
            horizon_from = now - timedelta(hours=12)
            horizon_to = now + timedelta(hours=12)
            for w in wdata:
                if now > w.timestamp >= horizon_from:
                    past_12h_rain += w.precipitation_amount
                if horizon_to <= w.timestamp < now:
                    next_12h_prob = max(next_12h_prob, w.precipitation_prob)
                    next_12h_rain += w.precipitation_amount
            with self._lock:
                self._weather_data = wdata
                self._last_update = now
                CONFIG[Settings.WEATHER_LAST_CHECK_TIMESTAMP] = now
            result = True
            self._logger.info(f"Current weather conditions @ {current.get('time')} :: Temperature: {current.get('temperature_2m', 0)}"
                f"{current_units.get('temperature_2m')}, Humidity: {current.get('relative_humidity_2m', 0)}%, Precipitation: {current.get('precipitation', 0)}"
                f"{current_units.get('precipitation')}, Pressure: {current.get('surface_pressure', 0)}{current_units.get('surface_pressure')}")
            self._logger.info(f"Weather updated successfully. Previous 12h rain amount: {past_12h_rain:.2f}{hourly_units.get('precipitation')}."
                f"Next 12h rain: {next_12h_rain:.2f}{hourly_units.get('precipitation')} with {next_12h_prob*100:.2f}% chance")
        except Exception as e:
            self._logger.error(f"Failed to update weather data, will retry: {e}", exc_info=True)
            result = False
        return result
