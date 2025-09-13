#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#
# from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .measurement import Measurement
from .units import Unit

# @dataclass(kw_only=True)
class WeatherData:
    """
    Represents weather data for a specific timestamp.

    This class encapsulates weather-related metrics such as temperature, soil
    humidity, and precipitation for a given timestamp. It is designed to model
    weather data efficiently, allowing access to these metrics through properties.

    :ivar _timestamp: The timestamp associated with the weather data.
    :type _timestamp: datetime
    :ivar _temperature: The temperature recorded at the given timestamp.
    :type _temperature: Measurement
    :ivar _soil_humidity: Soil humidity expressed as a percentage (m³/m³).
    :type _soil_humidity: Measurement
    :ivar _precipitation_amount: Precipitation amount at the given timestamp.
    :type _precipitation_amount: Measurement
    :ivar _precipitation_prob: Probability of precipitation at the given timestamp.
    :type _precipitation_prob: Measurement|None
    :ivar _surface_pressure: Surface pressure at the given timestamp.
    :type _surface_pressure: Measurement|None
    """
    def __init__(self, timestamp: datetime, tag: str, temperature: Measurement, soil_humidity: Measurement,
                 precipitation_amount: Measurement, precipitation_prob: Optional[Measurement]=None,
                 surface_pressure: Optional[Measurement]=None):
        self._timestamp = timestamp # local time
        self._tag = tag
        self._temperature = temperature
        self._soil_humidity = soil_humidity
        self._precipitation_amount = precipitation_amount # in current units, mm or inch
        self._precipitation_prob = precipitation_prob   # percentage
        self._surface_pressure = surface_pressure

    @classmethod
    def from_db_row(cls, row: tuple) -> "WeatherData":
        """
        Build from a DB row that matches the SELECT in storage.get_weather_data:
        SELECT collected_at_utc, forecast_ts_utc, tz, tag, temperature_2m, temperature_unit,
               soil_moisture_1_to_3cm, moisture_unit, precipitation, precipitation_unit,
               precipitation_probability, surface_pressure, pressure_unit
        """
        # row[0] is forecast timestamp - caller must already localize the timestamp (see storage.get_weather_data).
        # Here we only positionally map values to WeatherData constructor.
        return cls(
            timestamp=row[0],  # the caller should pass the localized datetime in place of row[0] (see storage)
            tag=row[1],
            temperature=Measurement(row[2],row[3]),
            soil_humidity=Measurement(row[4],row[5]),
            precipitation_amount=Measurement(row[6],row[7]),
            precipitation_prob=Measurement(row[8], Unit.PERCENT),
            surface_pressure=Measurement(row[9],row[10])
        )

    @classmethod
    def from_api_current(cls, ts: datetime, current: dict, units: dict) -> "WeatherData":
        """
        Build from Open-Meteo 'current' and 'current_units' dictionaries.
        """
        return cls(
            timestamp=ts,
            tag=current.get("time"),
            temperature=Measurement(current.get("temperature_2m", 0), units.get("temperature_2m")),
            soil_humidity=Measurement(current.get("relative_humidity_2m", 0), units.get("relative_humidity_2m")),
            precipitation_amount=Measurement(current.get("precipitation", 0), units.get("precipitation")),
            surface_pressure=Measurement(current.get("surface_pressure", 0), units.get("surface_pressure"))
        )

    @classmethod
    def from_api_hourly(cls, ts: datetime, tag: str, deg: float, soil: float, precip: float, prob: float, units: dict,
                        pressure: Optional[Measurement] = None) -> "WeatherData":
        """
        Build from Open-Meteo hourly arrays and hourly_units.
        """
        return cls(
            timestamp=ts,
            tag=tag,
            temperature=Measurement(deg, units.get("temperature_2m")),
            soil_humidity=Measurement(soil, units.get("soil_moisture_1_to_3cm")),
            precipitation_amount=Measurement(precip, units.get("precipitation")),
            precipitation_prob=Measurement(prob, Unit.PERCENT),
            surface_pressure=pressure
        )

    @property
    def timestamp(self) -> datetime:
        return self._timestamp

    @property
    def tag(self) -> str:
        return self._tag

    @property
    def temperature(self) -> Measurement:
        return self._temperature

    @property
    def soil_humidity(self) -> Measurement:
        return self._soil_humidity

    @property
    def precipitation_amount(self) -> Measurement:
        return self._precipitation_amount

    @property
    def precipitation_prob(self) -> Optional[Measurement]:
        return self._precipitation_prob

    @property
    def surface_pressure(self) -> Optional[Measurement]:
        return self._surface_pressure

    def __str__(self):
        return (f"WeatherData[timestamp={self._timestamp}, tag={self._tag}, temperature={self._temperature}, soil_humidity={self._soil_humidity}, "
                f"precipitation_amount={self._precipitation_amount}, precipitation_prob={self._precipitation_prob}, "
                f"surface_pressure={self._surface_pressure}]")
    def __repr__(self):
        return self.__str__()

