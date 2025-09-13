#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#

from datetime import datetime
from typing import Optional

from .units import Unit

def convert_measurement(value: float|int|None, current_unit: Unit, new_unit: Unit) -> float|int|None:
    """
    Convert values between different measurement units.

    This function is designed to convert specified values from one unit to another.
    It supports conversions between Celsius and Fahrenheit, and between liters and gallons.
    If the current unit is already the same as the new unit, the original value is
    returned. If the provided value is None, the function returns None.

    :param value: The numeric value to be converted. Can be an integer, float, or None.
    :type value: float | int | None
    :param current_unit: The current measurement unit of the value.
    :type current_unit: Unit
    :param new_unit: The desired measurement unit to convert to.
    :type new_unit: str
    :return: The converted value as an integer or float, or None if the input value is None.
    :rtype: float | int | None
    """
    if current_unit == new_unit:
        return value
    if value is None:
        return None
    match current_unit, new_unit:
        case Unit.CELSIUS, Unit.FAHRENHEIT:
            return value * 9/5 + 32
        case Unit.FAHRENHEIT, Unit.CELSIUS:
            return (value - 32) * 5 / 9
        case Unit.LITERS, Unit.GALLONS:
            return value / 3.785411784
        case Unit.GALLONS, Unit.LITERS:
            return value * 3.785411784
        case Unit.INCHES, Unit.MM:
            return value * 25.4
        case Unit.MM, Unit.INCHES:
            return value / 25.4
    return value

class Measurement:
    """
    Represents a measurement with a timestamp, a numeric value, and its unit.

    :ivar _data: The numerical value of the measurement; can be a float, int, or None if no value is assigned.
    :type _data: float | int | None
    :ivar _unit: The unit of the value (e.g., "°C", "°F", "L", "gal"). If no unit is specified, the owning trend unit will be used.
    :type _unit: Unit | None
    :ivar _time: The datetime when the measurement was recorded.
    :type _time: datetime | None
    """
    def __init__(self, value: float | int | None, unit: Unit | None = None, time: Optional[datetime] = None):
        self._data: float | int | None = value
        self._unit: Unit = unit
        self._time: datetime = time

    @property
    def time_iso(self) -> str:
        """
        Converts the stored time to its ISO 8601 string representation.

        :return: ISO 8601 representation of time.
        :rtype: str
        """
        return self._time.isoformat() if self._time else ""

    @property
    def value(self) -> float | int | None:
        """
        Retrieves the numeric value of the measurement.

        :return: The current value of the measurement.
        :rtype: float | int | None
        """
        return self._data

    @property
    def timestamp(self) -> datetime:
        """
        Returns the time associated with the instance.

        :return: The time associated with the instance
        :rtype: datetime
        """
        return self._time

    @property
    def unit(self) -> Unit:
        """
        Returns the unit of the measurement.

        :return: The unit of the measurement.
        :rtype: str
        """
        return self._unit

    def convert(self, new_unit: Unit) -> "Measurement":
        """
        Convert the current measurement to a specified unit.

        This method converts the internal data of the current measurement object
        from its current unit to a new specified unit. The conversion is achieved
        by utilizing the `convert_measurement` function while preserving the
        original time of the measurement.

        :param new_unit: The unit to which the measurement will be converted.
        :type new_unit: str
        :return: A new Measurement object with the converted data and specified unit.
        :rtype: Measurement
        """
        return Measurement(convert_measurement(self._data, self._unit, new_unit), new_unit, self._time)

    def json_encode(self):
        return {
            "__type__": "Measurement",
            "time": self._time,
            "value": self._data,
        }

    @staticmethod
    def json_decode(obj):
        if "__type__" in obj and obj["__type__"] == "Measurement":
            time = obj.get("time")
            value = obj.get("value")
            return Measurement(value, time=time)
        return None

    def __str__(self) -> str:
        """
        Returns a string representation including time, value, and unit.

        :return: A string containing timestamp, value, and unit.
        :rtype: str
        """
        return f"{{{self._time}: {self._data} {self._unit}}}"


class WateringMeasurement(Measurement):
    """
    Represents the watering-specific measurement, which includes the amount of water used,
    humidity levels before and after watering, and the duration of the watering process.

    This class extends a base `Measurement` class, providing additional attributes and methods
    that are specific to watering measurements. It includes functionality for encoding to JSON
    and reconstructing from JSON, as well as a human-readable string representation.

    :ivar _humidity_start: The humidity level before watering.
    :type _humidity_start: float
    :ivar _humidity_end: The humidity level after watering.
    :type _humidity_end: float
    :ivar _duration_sec: The duration of the watering process in seconds.
    :type _duration_sec: int
    """
    def __init__(self, time: datetime, value: float, unit: Unit, humidity_start: float, humidity_end: float, duration_sec: int):
        super().__init__(value, unit, time)
        self._humidity_start = humidity_start
        self._humidity_end = humidity_end
        self._duration_sec = duration_sec

    @property
    def duration_sec(self) -> int:
        """
        Provides the duration in seconds as an integer.

        This property retrieves the `_duration_sec` attribute which represents
        the duration value in seconds. It is read-only.

        :return: The duration in seconds.
        :rtype: int
        """
        return self._duration_sec

    @property
    def humidity_end(self) -> float:
        """
        Retrieve the humidity value at the end of watering.

        This property provides access to the final recorded humidity value.
        The value is returned as a float and represents the percentage of humidity.

        :return: Humidity value at the end of watering.
        :rtype: float
        """
        return self._humidity_end

    @property
    def humidity_start(self) -> float:
        """
        Gets the starting humidity value.

        This property retrieves the initial value of humidity at the start of watering.
        The value is returned as a float and represents the percentage of humidity.

        :return: The starting humidity value
        :rtype: float
        """
        return self._humidity_start

    def convert(self, new_unit: Unit) -> "WateringMeasurement":
        """
        Convert the current measurement to a specified unit.

        This method converts the internal data of the current measurement object
        from its current unit to a new specified unit. The conversion is achieved
        by utilizing the `convert_measurement` function while preserving the
        original time of the measurement and all other attributes.

        :param new_unit: The unit to which the measurement will be converted.
        :type new_unit: Unit
        :return: A new WateringMeasurement object with the converted data and specified unit.
        :rtype: WateringMeasurement
        """
        return WateringMeasurement(self._time, convert_measurement(self._data, self._unit, new_unit), new_unit, self._humidity_start, self._humidity_end, self._duration_sec)

    def json_encode(self):
        return {
            "__type__": "WateringMeasurement",
            "time": self._time,
            "value": self._data,
            "unit": self._unit,
            "humidity_start": self._humidity_start,
            "humidity_end": self._humidity_end,
            "duration_sec": self._duration_sec
        }

    @staticmethod
    def json_decode(obj):
        if "__type__" in obj and obj["__type__"] == "WateringMeasurement":
            time = obj.get("time")
            value = obj.get("value")
            humidity_start = obj.get("humidity_start")
            humidity_end = obj.get("humidity_end")
            duration_sec = obj.get("duration_sec")
            return WateringMeasurement(time, value, Unit(obj.get("unit")), humidity_start, humidity_end, duration_sec)
        return None

    def __str__(self) -> str:
        """
        Returns a string representation including time, value, and unit.

        :return: A string containing timestamp, value, and unit.
        :rtype: str        """
        return f"{{water={self._data} {self._unit} @ {self._time}; duration={self._duration_sec}s; humidity={self._humidity_start}-{self._humidity_end}%}}"