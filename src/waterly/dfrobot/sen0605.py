#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#

# python
"""
DFRobot SEN0605 RS485 Soil Sensor (N, P, K) Modbus-RTU driver.

Reference:
- DFRobot SEN0605 Wiki (Register address): https://wiki.dfrobot.com/RS485_Soil_Sensor_N_P_K_SKU_SEN0605

Transport:
- RS485, MODBUS-RTU
- Factory defaults typically 9600 baud, 8N1, slave address 0x01

Registers (per wiki):
- Nitrogen (N):   0x001E  (mg/kg)
- Phosphorus (P): 0x001F  (mg/kg)
- Potassium (K):  0x0020  (mg/kg)

Common device configuration registers (same pattern as other DFRobot RS485 sensors):
- Device address (RW): 0x07D0 (1..254)
- Baud rate (RW):      0x07D1 (0=2400, 1=4800, 2=9600)

Note:
- Some firmware maps expose data in Input Registers (0x04), others in Holding (0x03).
This driver first tries Input Registers then falls back to Holding for robustness.
"""

from enum import Enum
from time import sleep

import struct
from .base_sensor import BaseRS485ModbusSensor, RS485_PORT


class SEN0605(BaseRS485ModbusSensor):
    """
    Represents the SEN0605 sensor for measuring soil nutrient levels, including nitrogen,
    phosphorus, and potassium concentrations. This class provides methods for reading
    and writing nutrient concentrations, coefficients, and deviations, allowing for
    detailed nutrient monitoring and adjustment.

    SEN0605 is designed to interact with soil and provide accurate measurements in mg/kg
    for various nutrient types. It also supports configuration of calibration coefficients
    and deviation values for improved accuracy during nutrient readings.

    Example usage:
        >>> sensor = SEN0605(port=RS485_PORT)
        >>> try:
        >>>     r = sensor.read_all()
        >>>     print(f"N: {r[SEN0605.ReadingType.NITROGEN]} mg/kg")
        >>>     print(f"P: {r[SEN0605.ReadingType.PHOSPHORUS]} mg/kg")
        >>>     print(f"K: {r[SEN0605.ReadingType.POTASSIUM]} mg/kg")
        >>> finally:
        >>>     sensor.close()

    :ivar REG_NITROGEN: Register address for nitrogen concentration measurement (mg/kg).
    :type REG_NITROGEN: int
    :ivar REG_PHOSPHORUS: Register address for phosphorus concentration measurement (mg/kg).
    :type REG_PHOSPHORUS: int
    :ivar REG_POTASSIUM: Register address for potassium concentration measurement (mg/kg).
    :type REG_POTASSIUM: int
    :ivar REG_NITROGEN_COEFFICIENT_HI: Register address for the high 16 bits of
        the temporary nitrogen coefficient (floating point).
    :type REG_NITROGEN_COEFFICIENT_HI: int
    :ivar REG_NITROGEN_COEFFICIENT_LO: Register address for the low 16 bits of
        the temporary nitrogen coefficient (floating point).
    :type REG_NITROGEN_COEFFICIENT_LO: int
    :ivar REG_NITROGEN_DEVIATION: Register address for nitrogen deviation value (integer).
    :type REG_NITROGEN_DEVIATION: int
    :ivar REG_PHOSPHORUS_COEFFICIENT_HI: Register address for the high 16 bits of
        the temporary phosphorus coefficient (floating point).
    :type REG_PHOSPHORUS_COEFFICIENT_HI: int
    :ivar REG_PHOSPHORUS_COEFFICIENT_LO: Register address for the low 16 bits of
        the temporary phosphorus coefficient (floating point).
    :type REG_PHOSPHORUS_COEFFICIENT_LO: int
    :ivar REG_PHOSPHORUS_DEVIATION: Register address for phosphorus deviation value (integer).
    :type REG_PHOSPHORUS_DEVIATION: int
    :ivar REG_POTASSIUM_COEFFICIENT_HI: Register address for the high 16 bits of
        the temporary potassium coefficient (floating point).
    :type REG_POTASSIUM_COEFFICIENT_HI: int
    :ivar REG_POTASSIUM_COEFFICIENT_LO: Register address for the low 16 bits of
        the temporary potassium coefficient (floating point).
    :type REG_POTASSIUM_COEFFICIENT_LO: int
    :ivar REG_POTASSIUM_DEVIATION: Register address for potassium deviation value (integer).
    :type REG_POTASSIUM_DEVIATION: int
    """
    # Register map (per wiki)
    REG_NITROGEN = 0x001E    # mg/kg
    REG_PHOSPHORUS = 0x001F  # mg/kg
    REG_POTASSIUM = 0x0020   # mg/kg
    REG_NITROGEN_COEFFICIENT_HI = 0x03E8    # Temporary value of nitrogen content High 16 bits of coefficient (floating point value)
    REG_NITROGEN_COEFFICIENT_LO = 0x03E9    # Temporary value of nitrogen content Low 16 bits of coefficient (floating point value)
    REG_NITROGEN_DEVIATION = 0x03EA         # Deviation value of the temporary value of nitrogen content (integer value)
    REG_PHOSPHORUS_COEFFICIENT_HI = 0x03F2  # Temporary storage value of phosphorus content High 16 bits of coefficient (floating point value)
    REG_PHOSPHORUS_COEFFICIENT_LO = 0x03F3  # Temporary storage value of phosphorus content Low 16 bits of coefficient (floating point value)
    REG_PHOSPHORUS_DEVIATION = 0x03F4       # Deviation value of the temporary value of phosphorus content (integer value)
    REG_POTASSIUM_COEFFICIENT_HI = 0x03FC   # Temporary storage value of potassium content High 16 bits of coefficient (floating point value)
    REG_POTASSIUM_COEFFICIENT_LO = 0x03FD   # Temporary storage value of potassium content Low 16 bits of coefficient (floating point value)
    REG_POTASSIUM_DEVIATION = 0x03FE        # Deviation value of the temporary value of potassium content (integer value)

    class ReadingType(Enum):
        NITROGEN="nitrogen"
        PHOSPHORUS="phosphorus"
        POTASSIUM="potassium"

    def __init__(self, deviceaddr: int = BaseRS485ModbusSensor.DEFAULT_DEVICE_ADDR, port: str = RS485_PORT,
                 baudrate: int = BaseRS485ModbusSensor.DEFAULT_BAUD, timeout: float = BaseRS485ModbusSensor.DEFAULT_TIMEOUT_S,
                 bytesize: int = BaseRS485ModbusSensor.DEFAULT_BYTESIZE, parity: str = BaseRS485ModbusSensor.DEFAULT_PARITY,
                 stopbits: int = BaseRS485ModbusSensor.DEFAULT_STOPBITS) -> None:
        super().__init__(port, deviceaddr, baudrate, timeout, bytesize, parity, stopbits)
        self._pref_data_func = self.DATA_FUNCTIONS[1]   # this sensor prefers input registers

    def read_nitrogen(self) -> int:
        """
        Reads nitrogen concentration (mg/kg).
        """
        return int(self._read_one(self.REG_NITROGEN))

    def read_phosphorus(self) -> int:
        """
        Reads phosphorus concentration (mg/kg).
        """
        return int(self._read_one(self.REG_PHOSPHORUS))

    def read_potassium(self) -> int:
        """
        Reads potassium concentration (mg/kg).
        """
        return int(self._read_one(self.REG_POTASSIUM))

    def read_all(self) -> dict[ReadingType, int]:
        """
        Returns (nitrogen_mgkg, phosphorus_mgkg, potassium_mgkg)
        in a single, efficient batch transaction when possible.
        """
        regs = [self.REG_NITROGEN, self.REG_PHOSPHORUS, self.REG_POTASSIUM]
        values = self._read_many(regs)
        result = {
            SEN0605.ReadingType.NITROGEN: int(values[self.REG_NITROGEN]),
            SEN0605.ReadingType.PHOSPHORUS: int(values[self.REG_PHOSPHORUS]),
            SEN0605.ReadingType.POTASSIUM: int(values[self.REG_POTASSIUM])
        }
        return result

    def get_nitrogen_coefficient(self) -> float:
        """
        Reads the temporary value of nitrogen content coefficient (floating point value).
        """
        hi = int(self._read_one(self.REG_NITROGEN_COEFFICIENT_HI))
        sleep(0.25)
        lo = int(self._read_one(self.REG_NITROGEN_COEFFICIENT_LO))
        return struct.unpack('>f', (hi << 16 | lo).to_bytes(4))[0]

    def set_nitrogen_coefficient(self, value: float) -> None:
        """
        Sets the temporary value of nitrogen content coefficient (floating point value).
        """
        hi, lo = struct.unpack('>HH', struct.pack('>f', value))
        self._write_one(self.REG_NITROGEN_COEFFICIENT_HI, hi)
        sleep(0.25)
        self._write_one(self.REG_NITROGEN_COEFFICIENT_LO, lo)

    def get_nitrogen_deviation(self) -> int:
        """
        Reads the temporary value of nitrogen content deviation (integer value).
        """
        return int(self._read_one(self.REG_NITROGEN_DEVIATION))

    def set_nitrogen_deviation(self, value: int) -> None:
        """
        Sets the temporary value of nitrogen content deviation (integer value).
        """
        self._write_one(self.REG_NITROGEN_DEVIATION, value)

    def get_phosphorus_coefficient(self) -> float:
        """
        Reads the temporary value of phosphorus content coefficient (floating point value).
        """
        hi = int(self._read_one(self.REG_PHOSPHORUS_COEFFICIENT_HI))
        sleep(0.25)
        lo = int(self._read_one(self.REG_PHOSPHORUS_COEFFICIENT_LO))
        return struct.unpack('>f', (hi << 16 | lo).to_bytes(4))[0]

    def set_phosphorus_coefficient(self, value: float) -> None:
        """
        Sets the temporary value of phosphorus content coefficient (floating point value).
        """
        hi, lo = struct.unpack('>HH', struct.pack('>f', value))
        self._write_one(self.REG_PHOSPHORUS_COEFFICIENT_HI, hi)
        sleep(0.25)
        self._write_one(self.REG_PHOSPHORUS_COEFFICIENT_LO, lo)

    def get_phosphorus_deviation(self) -> int:
        """
        Reads the temporary value of phosphorus content deviation (integer value).
        """
        return int(self._read_one(self.REG_PHOSPHORUS_DEVIATION))

    def set_phosphorus_deviation(self, value: int) -> None:
        """
        Sets the temporary value of phosphorus content deviation (integer value).
        """
        self._write_one(self.REG_PHOSPHORUS_DEVIATION, value)

    def get_potassium_coefficient(self) -> float:
        """
        Reads the temporary value of potassium content coefficient (floating point value).
        """
        hi = int(self._read_one(self.REG_POTASSIUM_COEFFICIENT_HI))
        sleep(0.25)
        lo = int(self._read_one(self.REG_POTASSIUM_COEFFICIENT_LO))
        return struct.unpack('>f', (hi << 16 | lo).to_bytes(4))[0]

    def set_potassium_coefficient(self, value: float) -> None:
        """
        Sets the temporary value of potassium content coefficient (floating point value).
        """
        hi, lo = struct.unpack('>HH', struct.pack('>f', value))
        self._write_one(self.REG_POTASSIUM_COEFFICIENT_HI, hi)
        sleep(0.25)
        self._write_one(self.REG_POTASSIUM_COEFFICIENT_LO, lo)

    def get_potassium_deviation(self) -> int:
        """
        Reads the temporary value of potassium content deviation (integer value).
        """
        return int(self._read_one(self.REG_POTASSIUM_DEVIATION))

    def set_potassium_deviation(self, value: int) -> None:
        """
        Sets the temporary value of potassium content deviation (integer value).
        """
        self._write_one(self.REG_POTASSIUM_DEVIATION, value)
