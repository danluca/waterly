import threading
import pytz
import logging
import requests

from datetime import datetime, timedelta, tzinfo
from typing import Optional
from .config import DEFAULT_TIMEZONE, DATA_DIR, CONFIG, Settings
from .storage import write_text_file

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

class WeatherService:
    """
    Provides weather forecasting services by collecting and processing weather data.

    This class is designed to interface with the Open-Meteo weather API to fetch weather
    data for a specific location. It manages its own threading mechanism to periodically
    update forecasts, storing the next 12-hour precipitation probability and the time of
    the last update. The service is built to operate in a daemon thread, running until
    explicitly stopped.

    :ivar _next_12h_rain_prob: The probability of rain for the next 12 hours, as a floating-point value [0.0-1.0].
        Negative if no data is available.
    :type _next_12h_rain_prob: float
    :ivar _forecast_days: The number of forecast days requested from the weather API. Hardcoded as 3 for now.
    :type _forecast_days: int
    :ivar _timezone: The timezone of the weather data, determined from the API response or set to a default.
    :type _timezone: pytz.BaseTzInfo
    :ivar _last_update: The timestamp of the last successful weather data update.
    :type _last_update: datetime | None
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._next_12h_rain_prob: float = -1.0
        self._forecast_days: int = 3    # hardcoded for now using a common sense value
        self._timezone: pytz.BaseTzInfo = CONFIG[Settings.LOCAL_TIMEZONE]
        self._last_update: Optional[datetime] = None
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

    def get_next_12h_rain_probability(self) -> float:
        """
        Gets the rain probability for the next 12 hours.

        This method returns the predicted probability of rain in the next 12
        hours. The value is obtained while ensuring thread safety, preventing
        access collisions when used in concurrent environments.

        :return: The probability of rain for the next 12 hours as a float value [0.0-1.0].
        :rtype: float
        """
        with self._lock:
            return self._next_12h_rain_prob

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
                self._update_weather()
                if (CONFIG[Settings.LOCAL_TIMEZONE] is None) or (CONFIG[Settings.LOCAL_TIMEZONE] != self.get_timezone()):
                    self._logger.info(f"Local timezone changed from {CONFIG[Settings.LOCAL_TIMEZONE]} to {self._timezone}")
                    CONFIG[Settings.LOCAL_TIMEZONE] = self._timezone
            except Exception as e:
                self._logger.error(f"Weather update failed: {e}", exc_info=True)
            self._stop.wait(CONFIG[Settings.WEATHER_CHECK_INTERVAL_SECONDS])

    def _update_weather(self):
        """
        Updates the current weather data by fetching information from the Open-Meteo API and calculates the probability
        of rain for the next 12 hours. The weather data is saved, and the timezone is determined based on the fetched
        information. If an invalid timezone is encountered, a default timezone is used.
        The Open-Meteo API URL can be created at https://open-meteo.com/en/docs. Example API request:
        https://api.open-meteo.com/v1/forecast?latitude=45.0341769&longitude=-93.4641572&hourly=temperature_2m,precipitation_probability,soil_moisture_1_to_3cm,precipitation&timezone=auto&forecast_days=3&wind_speed_unit=mph&temperature_unit=fahrenheit&precipitation_unit=inch

        :raises requests.exceptions.HTTPError: If the HTTP request returns an unsuccessful status code.
        :raises requests.exceptions.RequestException: For other request-related exceptions' response.
        :return: None
        """
        params = {
            "latitude": CONFIG[Settings.LATITUDE],
            "longitude": CONFIG[Settings.LONGITUDE],
            "hourly": "precipitation_probability,temperature_2m,precipitation,soil_moisture_1_to_3cm",
            "forecast_days": self._forecast_days,
            "timezone": "auto"  # Open-Meteo can auto-detect by coordinates
        }
        r = requests.get(OPEN_METEO_URL, params=params, timeout=15)
        r.raise_for_status()
        self._save_weather_data(r.text)
        data = r.json()
        hourly = data.get("hourly", {})
        probs = hourly.get("precipitation_probability", [])
        times = hourly.get("time", [])
        # determine local timezone
        try:
            self._timezone = pytz.timezone(data.get("timezone", "UTC"))
        except pytz.UnknownTimeZoneError:
            self._timezone = DEFAULT_TIMEZONE
            self._logger.warning(f"Invalid timezone '{data.get('timezone', 'UTC')}' for pytz/TZDB version {pytz.VERSION}. Using default timezone {DEFAULT_TIMEZONE} instead.")

        now = datetime.now(self._timezone)
        horizon = now + timedelta(hours=12)
        next_12 = []
        for t, p in zip(times, probs):
            # noinspection PyBroadException
            try:
                ts = self._timezone.localize(datetime.fromisoformat(t.replace("Z", "+00:00")).replace(tzinfo=None))
            except Exception:
                continue
            if now <= ts <= horizon:
                next_12.append((ts, p / 100.0))
        prob = max((p for _, p in next_12), default=0.0)
        with self._lock:
            self._next_12h_rain_prob = prob
            self._last_update = now
        self._logger.info(f"Weather updated. Next 12h rain probability: {prob*100:.2f}%")
