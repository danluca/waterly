#  MIT License
#
#  Copyright (c) by Dan Luca. All rights reserved.
#

from enum import Enum
from typing import Optional

from .base_sensor import BaseRS485ModbusSensor, RS485_PORT

class SEN0438(BaseRS485ModbusSensor):
    """
    Represents the SEN0438 sensor for reading environmental data and configuring alarms.

    This class extends the BaseRS485ModbusSensor to provide specific implementation for the
    SEN0438 sensor, which measures temperature and humidity. It also allows configuration of
    threshold alarms for both temperature and humidity. The class communicates with the sensor
    using RS485 Modbus protocol and provides methods for reading sensor data and managing alarms.

    :ivar REG_BAUD_RATE: The register for configuring the baud rate.
    :type REG_BAUD_RATE: int
    :ivar REG_HUMIDITY: The register for reading humidity data.
    :type REG_HUMIDITY: int
    :ivar REG_TEMPERATURE: The register for reading temperature data.
    :type REG_TEMPERATURE: int
    :ivar REG_DEVICE_MODEL: The register for retrieving the device model information.
    :type REG_DEVICE_MODEL: int
    :ivar REG_VERSION: The register for retrieving the lower 8 bits of device version.
    :type REG_VERSION: int
    :ivar REG_DEVICE_ID_HIGH: The register for the high 16 bits of the 32-bit device ID.
    :type REG_DEVICE_ID_HIGH: int
    :ivar REG_DEVICE_ID_LOW: The register for the low 16 bits of the 32-bit device ID.
    :type REG_DEVICE_ID_LOW: int
    :ivar REG_DEVICE_ADDRESS: Alias for the low 16 bits register of the device address.
    :type REG_DEVICE_ADDRESS: int
    :ivar REG_TEMP_ALARM_UPPER_VAL: The register for high temperature alarm threshold value.
    :type REG_TEMP_ALARM_UPPER_VAL: int
    :ivar REG_TEMP_ALARM_UPPER_ENABLE: The register for enabling/disabling high temperature alarms.
    :type REG_TEMP_ALARM_UPPER_ENABLE: int
    :ivar REG_TEMP_ALARM_LOWER_VAL: The register for low temperature alarm threshold value.
    :type REG_TEMP_ALARM_LOWER_VAL: int
    :ivar REG_TEMP_ALARM_LOWER_ENABLE: The register for enabling/disabling low temperature alarms.
    :type REG_TEMP_ALARM_LOWER_ENABLE: int
    :ivar REG_HUMIDITY_ALARM_UPPER_VAL: The register for high humidity alarm threshold value.
    :type REG_HUMIDITY_ALARM_UPPER_VAL: int
    :ivar REG_HUMIDITY_ALARM_UPPER_ENABLE: The register for enabling/disabling high humidity alarms.
    :type REG_HUMIDITY_ALARM_UPPER_ENABLE: int
    :ivar REG_HUMIDITY_ALARM_LOWER_VAL: The register for low humidity alarm threshold value.
    :type REG_HUMIDITY_ALARM_LOWER_VAL: int
    :ivar REG_HUMIDITY_ALARM_LOWER_ENABLE: The register for enabling/disabling low humidity alarms.
    :type REG_HUMIDITY_ALARM_LOWER_ENABLE: int
    :ivar REG_TEMP_CORRECTION: The register for temperature correction values.
    :type REG_TEMP_CORRECTION: int
    :ivar REG_HUMIDITY_CORRECTION: The register for humidity correction values.
    :type REG_HUMIDITY_CORRECTION: int
    """
    REG_BAUD_RATE = 0xFFFF

    # Register map (per instruction manual) [[1]](https://github.com/May-DFRobot/DFRobot/blob/master/SEN0438%20-%20EN.pdf)
    # READ ONLY
    REG_HUMIDITY = 0x0000
    REG_TEMPERATURE = 0x0001
    REG_DEVICE_MODEL = 0x0008
    REG_VERSION = 0x0009    # lower 8 bits
    REG_DEVICE_ID_HIGH = 0x000A
    REG_DEVICE_ID_LOW = 0x000B
    REG_DEVICE_ADDRESS = REG_DEVICE_ID_LOW
    REG_TEMP_ALARM_UPPER_VAL = 0x000C
    REG_TEMP_ALARM_UPPER_ENABLE = 0x000D
    REG_TEMP_ALARM_LOWER_VAL = 0x000E
    REG_TEMP_ALARM_LOWER_ENABLE = 0x000F
    REG_HUMIDITY_ALARM_UPPER_VAL = 0x0010
    REG_HUMIDITY_ALARM_UPPER_ENABLE = 0x0011
    REG_HUMIDITY_ALARM_LOWER_VAL = 0x0012
    REG_HUMIDITY_ALARM_LOWER_ENABLE = 0x0013
    REG_TEMP_CORRECTION = 0x001D
    REG_HUMIDITY_CORRECTION = 0x001E

    class ReadingType(Enum):
        AIR_TEMPERATURE="air_temperature"
        HUMIDITY="humidity"

    def __init__(self, deviceaddr: int = BaseRS485ModbusSensor.DEFAULT_DEVICE_ADDR, port: str = RS485_PORT,
                 baudrate: int = BaseRS485ModbusSensor.DEFAULT_BAUD, timeout: float = BaseRS485ModbusSensor.DEFAULT_TIMEOUT_S,
                 bytesize: int = BaseRS485ModbusSensor.DEFAULT_BYTESIZE, parity: str = BaseRS485ModbusSensor.DEFAULT_PARITY,
                 stopbits: int = BaseRS485ModbusSensor.DEFAULT_STOPBITS) -> None:
        """
        Initializes the RS485 Modbus sensor with specified configurations.

        This constructor sets up the serial communication parameters for the RS485 device, which include
        device address, serial port configurations like baudrate, timeout, bytesize, parity, and stopbits.
        Default values are provided for these parameters when not specified.

        :param deviceaddr: The address of the device on the RS485 bus.
        :param port: The serial port to which the RS485 device is connected.
        :param baudrate: The communication speed in bits per second.
        :param timeout: The duration to wait for a response from the device in seconds.
        :param bytesize: The number of data bits in each byte.
        :param parity: The parity scheme to be used ('N', 'E', 'O', etc.).
        :param stopbits: The number of stop bits to indicate the end of a byte.
        """
        super().__init__(port, deviceaddr, baudrate, timeout, bytesize, parity, stopbits)

    def read_temperature_c(self) -> float:
        """
        Reads the temperature in degrees Celsius.

        This method retrieves the raw temperature data, processes it by dividing
        it by 10 to convert it from its original unit (0.1 °C) to degrees Celsius,
        and rounds it to one decimal place before returning the value.

        :return: The temperature in degrees Celsius rounded to 1 decimal place.
        :rtype: float
        """
        raw = self._read_one(self.REG_TEMPERATURE)
        # 0.1 °C units
        return round(raw / 10.0, 1)

    def read_temperature_f(self) -> float:
        """
        Read and convert the temperature from a raw reading to Fahrenheit.

        This method reads a raw temperature value from a register, converts it
        to Fahrenheit using the appropriate formula, and rounds it to one decimal
        place to provide the desired level of precision.

        :return: The temperature in degrees Fahrenheit rounded to one decimal place
        :rtype: float
        """
        raw = self._read_one(self.REG_TEMPERATURE)
        # 0.1 °F units
        return round((raw * 9 / 5 / 10.0)+32, 1)

    def read_humidity(self) -> float:
        """
        Reads the humidity level and returns it as a percentage.

        The method retrieves raw humidity data from the sensor, converts it to a
        percentage with 0.1% units, and rounds the result to one decimal place.

        :return: The moisture level as a percentage.
        :rtype: float
        """
        raw = self._read_one(self.REG_HUMIDITY)
        # 0.1 % units
        return round(raw / 10.0, 1)

    def read_all(self) -> dict[ReadingType, float|int]:
        """
        Returns (Temperature 'C, Humidity %)
        """
        regs = [self.REG_HUMIDITY, self.REG_TEMPERATURE]
        values = self._read_many(regs)
        result = {
            SEN0438.ReadingType.HUMIDITY: round(values[self.REG_HUMIDITY] / 10.0, 1),
            SEN0438.ReadingType.AIR_TEMPERATURE: round(values[self.REG_TEMPERATURE] / 10.0, 1)
        }
        return result

    def get_device_model(self) -> int:
        """
        Returns the model of the device.
        """
        return self._read_one(self.REG_DEVICE_MODEL)

    def get_device_address(self) -> Optional[int]:
        """
        This information is not mapped onto a register for SEN0438. The REG_DEVICE_ADDRESS register usually holds 0.
        """
        #return self._read_one(self.REG_DEVICE_ADDRESS)
        # noinspection PyBroadException
        try:
            return int(self._read_one(self.REG_DEVICE_ADDRESS))
        except Exception:
            return None

    def get_device_id(self) -> Optional[int]:
        """
        Returns the 32bit device ID.
        """
        reg = [self.REG_DEVICE_ID_HIGH, self.REG_DEVICE_ID_LOW]
        result = self._read_many(reg)
        return (result[self.REG_DEVICE_ID_HIGH] << 16) | result[self.REG_DEVICE_ID_LOW]

    def get_high_temperature_alarm(self) -> float:
        """
        Returns the high temperature alarm threshold in degrees Celsius.
        """
        return self._read_one(self.REG_TEMP_ALARM_UPPER_VAL) / 10.0

    def set_high_temperature_alarm(self, value: float) -> None:
        """
        Sets the high temperature alarm threshold in degrees Celsius.
        """
        if value < -100 or value > 100:
            raise ValueError("Temperature alarm value must be between -100 and 100 degrees Celsius")
        self._write_one(self.REG_TEMP_ALARM_UPPER_VAL, int(value * 10))

    def is_high_temperature_alarm_enabled(self) -> bool:
        """
        Returns True if the high temperature alarm is enabled, False otherwise.
        """
        return self._read_one(self.REG_TEMP_ALARM_UPPER_ENABLE) == 1

    def enable_high_temperature_alarm(self) -> None:
        """
        Enables the high temperature alarm.
        """
        self._write_one(self.REG_TEMP_ALARM_UPPER_ENABLE, 1)

    def disable_high_temperature_alarm(self) -> None:
        """
        Disables the high temperature alarm.
        """
        self._write_one(self.REG_TEMP_ALARM_UPPER_ENABLE, 0)

    def get_low_temperature_alarm(self) -> float:
        """
        Returns the low temperature alarm threshold in degrees Celsius.
        """
        return self._read_one(self.REG_TEMP_ALARM_LOWER_VAL) / 10.0

    def set_low_temperature_alarm(self, value: float) -> None:
        """
        Sets the low temperature alarm threshold in degrees Celsius.
        """
        if value < -100 or value > 100:
            raise ValueError("Temperature alarm value must be between -100 and 100 degrees Celsius")
        self._write_one(self.REG_TEMP_ALARM_LOWER_VAL, int(value * 10))

    def is_low_temperature_alarm_enabled(self) -> bool:
        """
        Returns True if the low temperature alarm is enabled, False otherwise.
        """
        return self._read_one(self.REG_TEMP_ALARM_LOWER_ENABLE) == 1

    def enable_low_temperature_alarm(self) -> None:
        """
        Enables the low temperature alarm.
        """
        self._write_one(self.REG_TEMP_ALARM_LOWER_ENABLE, 1)

    def disable_low_temperature_alarm(self) -> None:
        """
        Disables the low temperature alarm.
        """
        self._write_one(self.REG_TEMP_ALARM_LOWER_ENABLE, 0)

    def get_high_humidity_alarm(self) -> float:
        """
        Returns the high humidity alarm threshold in percentage.
        """
        return self._read_one(self.REG_HUMIDITY_ALARM_UPPER_VAL) / 10.0

    def set_high_humidity_alarm(self, value: float) -> None:
        """
        Sets the high humidity alarm threshold in percentage.
        """
        if value < 0 or value > 100:
            raise ValueError("Humidity alarm value must be between 0 and 100%")
        self._write_one(self.REG_HUMIDITY_ALARM_UPPER_VAL, int(value * 10))

    def is_high_humidity_alarm_enabled(self) -> bool:
        """
        Returns True if the high humidity alarm is enabled, False otherwise.
        """
        return self._read_one(self.REG_HUMIDITY_ALARM_UPPER_ENABLE) == 1

    def enable_high_humidity_alarm(self) -> None:
        """
        Enables the high humidity alarm.
        """
        self._write_one(self.REG_HUMIDITY_ALARM_UPPER_ENABLE, 1)

    def disable_high_humidity_alarm(self) -> None:
        """
        Disables the high humidity alarm.
        """
        self._write_one(self.REG_HUMIDITY_ALARM_UPPER_ENABLE, 0)

    def get_low_humidity_alarm(self) -> float:
        """
        Returns the low humidity alarm threshold in percentage.
        """
        return self._read_one(self.REG_HUMIDITY_ALARM_LOWER_VAL) / 10.0

    def set_low_humidity_alarm(self, value: float) -> None:
        """
        Sets the low humidity alarm threshold in percentage.
        """
        if value < 0 or value > 100:
            raise ValueError("Humidity alarm value must be between 0 and 100%")
        self._write_one(self.REG_HUMIDITY_ALARM_LOWER_VAL, int(value * 10))

    def is_low_humidity_alarm_enabled(self) -> bool:
        """
        Returns True if the low humidity alarm is enabled, False otherwise.
        """
        return self._read_one(self.REG_HUMIDITY_ALARM_LOWER_ENABLE) == 1

    def enable_low_humidity_alarm(self) -> None:
        """
        Enables the low humidity alarm.
        """
        self._write_one(self.REG_HUMIDITY_ALARM_LOWER_ENABLE, 1)

    def disable_low_humidity_alarm(self) -> None:
        """
        Disables the low humidity alarm.
        """
        self._write_one(self.REG_HUMIDITY_ALARM_LOWER_ENABLE, 0)

    def get_temperature_correction(self) -> float:
        """
        Returns the temperature correction value in degrees Celsius.
        """
        return self._read_one(self.REG_TEMP_CORRECTION) / 10.0

    def set_temperature_correction(self, value: float) -> None:
        """
        Sets the temperature correction value in degrees Celsius.
        """
        if value < -100 or value > 100:
            raise ValueError("Temperature correction value must be between -100 and 100 degrees Celsius")
        self._write_one(self.REG_TEMP_CORRECTION, int(value * 10))

    def get_humidity_correction(self) -> float:
        """
        Returns the humidity correction value in percentage.
        """
        return self._read_one(self.REG_HUMIDITY_CORRECTION) / 10.0

    def set_humidity_correction(self, value: float) -> None:
        """
        Sets the humidity correction value in percentage.
        """
        if value < 0 or value > 100:
            raise ValueError("Humidity correction value must be between 0 and 100%")
        self._write_one(self.REG_HUMIDITY_CORRECTION, int(value * 10))
