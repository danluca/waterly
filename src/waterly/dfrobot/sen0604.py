#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#

# python
"""
DFRobot SEN0604 RS485 Soil Sensor (Temperature, Moisture, EC, pH) Modbus-RTU library.

References:
- DFRobot SEN0604 Wiki (registers/specs): https://wiki.dfrobot.com/RS485_Soil_Sensor_Temperature_Humidity_EC_PH_SKU_SEN0604

Transport
- RS485 with MODBUS-RTU
- Default 9600 baud, 8N1, slave address 0x01

Registers (per wiki):
- Moisture:    Holding/Input reg 0x0000, value in 0.1 % (volumetric water content)
- Temperature: Holding/Input reg 0x0001, value in 0.1 °C
- EC:          Holding/Input reg 0x0002, value in µS/cm (scaling 1)
- pH:          Holding/Input reg 0x0003, value in 0.01 pH

Some firmware maps expose data in Input Registers (0x04), others in Holding (0x03).
This driver first tries Input Registers then falls back to Holding for robustness.
"""

from time import sleep
from enum import Enum
from .base_sensor import BaseRS485ModbusSensor, RS485_PORT


class SEN0604(BaseRS485ModbusSensor):
    """
    Represents the SEN0604 sensor for measuring soil properties via RS485 Modbus.

    This class provides methods to interact with the SEN0604 soil sensor, enabling
    the reading and writing of sensor data including temperature, moisture,
    electrical conductivity, pH, and related coefficients. It communicates
    via RS485 Modbus protocol and manages register-level operations internally.

    Example usage:
        >>> sensor = SEN0604(port="/dev/ttyUSB0")  # Create sensor instance
        >>> try:
        >>>     # Read all sensor values at once
        >>>     r = sensor.read_all()
        >>>     print(f"Temperature: {r[SEN0604.ReadingType.TEMPERATURE]:.1f} °C")
        >>>     print(f"Moisture: {r[SEN0604.ReadingType.MOISTURE]:.1f} %")
        >>>     print(f"EC: {r[SEN0604.ReadingType.ELECTRICAL_CONDUCTIVITY]} µS/cm")
        >>>     print(f"pH: {r[SEN0604.ReadingType.PH]:.2f}")
        >>>
        >>>     # Or read individual values
        >>>     temp_c = sensor.read_temperature_c()
        >>>     temp_f = sensor.read_temperature_f()
        >>>     moisture = sensor.read_moisture()
        >>>     ec = sensor.read_ec()
        >>>     ph = sensor.read_ph()
        >>> finally:
        >>>     sensor.close()  # Always close the connection

    :ivar REG_MOISTURE: Register address for reading moisture level (0.1% units).
    :type REG_MOISTURE: int
    :ivar REG_TEMPERATURE: Register address for reading temperature (0.1 °C units).
    :type REG_TEMPERATURE: int
    :ivar REG_EC: Register address for reading electrical conductivity (µS/cm).
    :type REG_EC: int
    :ivar REG_PH: Register address for reading pH level (0.1 pH units).
    :type REG_PH: int
    :ivar REG_SALINITY: Register address for reading salinity value (reference only).
    :type REG_SALINITY: int
    :ivar REG_TDS: Register address for reading Total Dissolved Solids (reference only).
    :type REG_TDS: int
    :ivar REG_EC_COEFFICIENT: Register address for reading and writing the EC coefficient.
    :type REG_EC_COEFFICIENT: int
    :ivar REG_SALINITY_COEFFICIENT: Register address for reading and writing the salinity coefficient.
    :type REG_SALINITY_COEFFICIENT: int
    :ivar REG_TDS_COEFFICIENT: Register address for reading and writing the TDS coefficient.
    :type REG_TDS_COEFFICIENT: int
    :ivar REG_TEMP_CALIBRATION: Register address for reading and writing temperature calibration.
    :type REG_TEMP_CALIBRATION: int
    :ivar REG_MOISTURE_CALIBRATION: Register address for reading and writing moisture calibration.
    :type REG_MOISTURE_CALIBRATION: int
    :ivar REG_EC_CALIBRATION: Register address for reading and writing EC calibration.
    :type REG_EC_CALIBRATION: int
    :ivar REG_PH_CALIBRATION: Register address for reading and writing pH calibration.
    :type REG_PH_CALIBRATION: int
    """
    # Register map (per wiki) [[1]](https://wiki.dfrobot.com/RS485_Soil_Sensor_Temperature_Humidity_EC_PH_SKU_SEN0604)
    # READ ONLY
    REG_MOISTURE = 0x0000     # 0.1 %
    REG_TEMPERATURE = 0x0001  # 0.1 °C
    REG_EC = 0x0002           # µS/cm
    REG_PH = 0x0003           # 0.1 pH
    REG_SALINITY = 0x0007     # reference only
    REG_TDS = 0x0008          # Total dissolved solids TDS (reference only)
    # READ-WRITE
    REG_EC_COEFFICIENT = 0x0022         # Conductivity temperature coefficient; 0-100 corresponds to 0.0%-10.0% Default 0.0%
    REG_SALINITY_COEFFICIENT = 0x0023   # Salinity coefficient; 0-100 corresponds to 0.00-1.00 Default 55 (0.55)
    REG_TDS_COEFFICIENT = 0x0024        # TDS coefficient; 0-100 corresponds to 0.00-1.00 Default 50 (0.5)
    REG_TEMP_CALIBRATION = 0x0050       # Temperature calibration value; Integer (expanded 10 times)
    REG_MOISTURE_CALIBRATION = 0x0051   # Water content calibration value; Integer (expanded 10 times)
    REG_EC_CALIBRATION = 0x0052         # Conductivity calibration value; integer
    REG_PH_CALIBRATION = 0x0053         # pH calibration value; integer

    class ReadingType(Enum):
        TEMPERATURE="temperature"
        MOISTURE="moisture"
        ELECTRICAL_CONDUCTIVITY="ec"
        PH="ph"
        SALINITY="salinity"
        TOTAL_DISSOLVED_SOLIDS="tds"

    def __init__(self, deviceaddr: int = BaseRS485ModbusSensor.DEFAULT_DEVICE_ADDR, port: str = RS485_PORT,
                 baudrate: int = BaseRS485ModbusSensor.DEFAULT_BAUD, timeout: float = BaseRS485ModbusSensor.DEFAULT_TIMEOUT_S,
                 bytesize: int = BaseRS485ModbusSensor.DEFAULT_BYTESIZE, parity: str = BaseRS485ModbusSensor.DEFAULT_PARITY,
                 stopbits: int = BaseRS485ModbusSensor.DEFAULT_STOPBITS) -> None:
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

    def read_moisture(self) -> float:
        """
        Reads the moisture level and returns it as a percentage.

        The method retrieves raw moisture data from the sensor, converts it to a
        percentage with 0.1% units, and rounds the result to one decimal place.

        :return: The moisture level as a percentage.
        :rtype: float
        """
        raw = self._read_one(self.REG_MOISTURE)
        # 0.1 % units
        return round(raw / 10.0, 1)

    def read_ec(self) -> int:
        """
        Reads and returns the electrical conductivity (EC) value in microsiemens per centimeter
        (µS/cm) without any scaling. This function interacts with the corresponding register
        to retrieve the EC value.

        :return: The electrical conductivity value in µS/cm obtained from the sensor.
        :rtype: int
        """
        raw = self._read_one(self.REG_EC)
        # EC in µS/cm (no scaling)
        return int(raw)

    def read_ph(self) -> float:
        """
        Reads the pH value from the sensor and converts it to a float representation
        in pH units with precision of 0.1.

        :return: The pH value as a float, rounded to the nearest 0.1.
        :rtype: float
        """
        raw = self._read_one(self.REG_PH)
        # 0.1 pH units
        return round(raw / 10.0, 1)

    def read_salinity(self) -> int:
        """
        Reads the salinity measurement value.

        This method retrieves the salinity value from the sensor by reading
        the data from the specific register designed for salinity. The raw
        data is converted to an integer before being returned.

        :return: The salinity value as an integer.
        :rtype: int
        """
        raw = self._read_one(self.REG_SALINITY)
        return int(raw)

    def read_tds(self) -> int:
        """
        Reads the TDS (Total Dissolved Solids) value from the corresponding register
        and returns it as an integer.

        This function interacts with a specific hardware register to retrieve the
        raw TDS value, processes the retrieved data, and converts it to a meaningful
        numerical value of type integer.

        :return: An int representing the TDS value.
        :rtype: int
        """
        raw = self._read_one(self.REG_TDS)
        return int(raw)

    def read_all(self) -> dict[ReadingType, float|int]:
        """
        Returns (temperature_c, moisture_percent, ec_uScm, ph)
        """
        regs = [self.REG_MOISTURE, self.REG_TEMPERATURE, self.REG_EC, self.REG_PH]
        values = self._read_many(regs)
        result = {
            SEN0604.ReadingType.MOISTURE: round(values[self.REG_MOISTURE] / 10.0, 1),
            SEN0604.ReadingType.TEMPERATURE: round(values[self.REG_TEMPERATURE] / 10.0, 1),
            SEN0604.ReadingType.ELECTRICAL_CONDUCTIVITY: int(values[self.REG_EC]),
            SEN0604.ReadingType.PH: round(values[self.REG_PH] / 10.0, 1)
        }
        sleep(0.25)
        regs = [self.REG_SALINITY, self.REG_TDS]
        values = self._read_many(regs)
        result[SEN0604.ReadingType.SALINITY] = int(values[self.REG_SALINITY])
        result[SEN0604.ReadingType.TOTAL_DISSOLVED_SOLIDS] = int(values[self.REG_TDS])
        return result

    def get_ec_coefficient(self) -> int:
        """
        Retrieves the EC (Electrical Conductivity) coefficient value.

        This method reads the EC coefficient value stored in the configuration
        register and converts it into an integer format.
        0-100 corresponds to 0.0%-10.0% Default 0.0%

        :return: The EC coefficient value as an integer.
        :rtype: int
        """
        data = self._read_one(self.REG_EC_COEFFICIENT)
        return int(data)

    def set_ec_coefficient(self, value: int) -> None:
        """
        Sets the EC (Electrical Conductivity) coefficient value.

        This method writes the provided value to the EC coefficient configuration
        register.
        :param value: The EC coefficient value to be set. 0-100 corresponds to 0.0%-10.0%
        """
        self._write_one(self.REG_EC_COEFFICIENT, value)

    def get_salinity_coefficient(self) -> int:
        """
        Retrieves the salinity coefficient value.

        This method reads the salinity coefficient value stored in the configuration
        register and converts it into an integer format.
        0-100 corresponds to 0.00-1.00 Default 55 (0.55)

        :return: The salinity coefficient value as an integer.
        :rtype: int
        """
        data = self._read_one(self.REG_SALINITY_COEFFICIENT)
        return int(data)

    def set_salinity_coefficient(self, value: int) -> None:
        """
        Sets the salinity coefficient value.

        This method writes the provided value to the salinity coefficient configuration
        register.
        :param value: The salinity coefficient value to be set. 0-100 corresponds to 0.00-1.00
        """
        self._write_one(self.REG_SALINITY_COEFFICIENT, value)

    def get_tds_coefficient(self) -> int:
        """
        Retrieves the TDS (Total Dissolved Solids) coefficient value.

        This method reads the TDS coefficient value stored in the configuration
        register and converts it into an integer format.
        0-100 corresponds to 0.00-1.00 Default 50 (0.5)

        :return: The TDS coefficient value as an integer.
        :rtype: int
        """
        data = self._read_one(self.REG_TDS_COEFFICIENT)
        return int(data)

    def set_tds_coefficient(self, value: int) -> None:
        """
        Sets the TDS (Total Dissolved Solids) coefficient value.

        This method writes the provided value to the TDS coefficient configuration register.
        :param value: The TDS coefficient value to be set. 0-100 corresponds to 0.00-1.00
        """
        self._write_one(self.REG_TDS_COEFFICIENT, value)

    def get_temperature_calibration(self) -> float:
        """
        Retrieves the temperature calibration value.

        This method reads the temperature calibration value stored in the configuration
        register and converts it into float format
        :return: The temperature calibration value as a float.
        :rtype: float
        """
        data = self._read_one(self.REG_TEMP_CALIBRATION)
        return round(data / 10.0, 1)

    def set_temperature_calibration(self, value: float) -> None:
        """
        Sets the temperature calibration value.

        This method writes the provided value to the temperature calibration configuration
        register.
        :param value: The temperature calibration value to be set.
        """
        self._write_one(self.REG_TEMP_CALIBRATION, int(value * 10))

    def get_moisture_calibration(self) -> float:
        """
        Retrieves the moisture calibration value.

        This method reads the moisture calibration value stored in the configuration
        register and converts it into float format.
        :return: The moisture calibration value as a float.
        :rtype: float
        """
        data = self._read_one(self.REG_MOISTURE_CALIBRATION)
        return round(data / 10.0, 1)

    def set_moisture_calibration(self, value: float) -> None:
        """
        Sets the moisture calibration value.

        This method writes the provided value to the moisture calibration configuration
        register.
        :param value: The moisture calibration value to be set.
        """
        self._write_one(self.REG_MOISTURE_CALIBRATION, int(value * 10))

    def get_ec_calibration(self) -> int:
        """
        Retrieves the EC (Electrical Conductivity) calibration value.
        :return: The EC calibration value as an integer.
        :rtype: int
        """
        data = self._read_one(self.REG_EC_CALIBRATION)
        return int(data)

    def set_ec_calibration(self, value: int) -> None:
        """
        Sets the EC (Electrical Conductivity) calibration value.
        :param value: The EC calibration value to be set.
        """
        self._write_one(self.REG_EC_CALIBRATION, value)

    def get_ph_calibration(self) -> int:
        """
        Retrieves the pH calibration value.
        :return: The pH calibration value as an integer.
        :rtype: int
        """
        data = self._read_one(self.REG_PH_CALIBRATION)
        return int(data)

    def set_ph_calibration(self, value: int) -> None:
        """
        Sets the pH calibration value.
        :param value: The pH calibration value to be set.
        """
        self._write_one(self.REG_PH_CALIBRATION, value)
