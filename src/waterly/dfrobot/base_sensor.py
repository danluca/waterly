# python
"""
Base class providing common RS485 Modbus-RTU plumbing and helpers
for DFRobot sensors.
"""

from __future__ import annotations

from typing import Optional

import modbus_tk
import serial
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
from modbus_tk import exceptions as mdb_exc


RS485_PORT = "/dev/serial0"


class BaseRS485ModbusSensor:
    """
    Base class providing common RS485 Modbus-RTU plumbing and helpers
    for DFRobot sensors.
    """

    # Modbus defaults (can be overridden in subclasses)
    DEFAULT_DEVICE_ADDR = 0x01
    DEFAULT_BAUD = 9600
    DEFAULT_BYTESIZE = 8
    DEFAULT_PARITY = "N"
    DEFAULT_STOPBITS = 1
    DEFAULT_TIMEOUT_S = 1.0

    # Common device configuration registers (typical across DFRobot RS485 sensors)
    REG_DEVICE_ADDRESS = 0x07D0  # 1..254
    REG_BAUD_RATE = 0x07D1       # 0=2400, 1=4800, 2=9600

    def __init__(
        self,
        port: str = RS485_PORT,
        deviceaddr: int = DEFAULT_DEVICE_ADDR,
        baudrate: int = DEFAULT_BAUD,
        timeout: float = DEFAULT_TIMEOUT_S,
        bytesize: int = DEFAULT_BYTESIZE,
        parity: str = DEFAULT_PARITY,
        stopbits: int = DEFAULT_STOPBITS,
    ) -> None:
        self.device_addr = deviceaddr
        self._serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=bytesize,
            parity=parity,
            stopbits=stopbits,
            timeout=timeout,
        )
        self._master = modbus_rtu.RtuMaster(self._serial)
        self._master.set_timeout(timeout)
        self._is_present:bool = False

    def close(self) -> None:
        """
        Closes the serial connection if it is open.

        This method attempts to close an open serial connection. If the connection
        is already closed, no action is performed. Any encountered exceptions
        during the closure process are silently ignored.

        :return: None
        """
        # noinspection PyBroadException
        try:
            self._serial.close() if self._serial.is_open else None
        except Exception:
            pass

    def open(self) -> None:
        """
        Opens a serial connection if it is not already open.

        The method attempts to open the serial connection by calling the appropriate
        function from the underlying serial object. If the connection is already open,
        no action is performed.

        :return: None
        """
        # noinspection PyBroadException
        try:
            self._serial.open() if not self._serial.is_open else None
            self.get_device_address()   # forces a read to update the device presence status
        except Exception:
            pass

    @property
    def is_open(self) -> bool:
        """
        Indicates whether the serial connection is currently open.

        :return: A boolean indicating if the serial connection is open.
        :rtype: bool
        """
        return self._serial.is_open

    @property
    def is_present(self) -> bool:
        """
        Indicates whether the sensor is present - i.e. the device address was valid at least once.
        This is not an indication of whether the sensor is connected. Use `is_connected()` for that.

        :return: A boolean indicating if the sensor is present
        :rtype: bool
        """
        return self._is_present

    def is_connected(self) -> bool:
        """
        Checks if the device is connected by verifying the presence of a valid device address.

        This method determines whether the device is connected by checking if a non-
        `None` device address is available. The result is `True` when two conditions are met:
        - The serial connection is open.
        - The device address is not `None` (can be verified lively by reading the register).

        :return: True if the device is connected, otherwise False
        :rtype: bool
        """
        if not self._serial.is_open:
            return False
        return self.get_device_address() is not None

    # Optional helpers (if supported by firmware)
    def get_device_address(self) -> Optional[int]:
        """
        Fetches the device address by reading a specific register.

        Attempts to read the device address from the associated register. If the
        operation fails due to exceptions, it returns `None`.

        :return: Device address as an integer if available, otherwise `None`.
        :rtype: Optional[int]
        """
        # noinspection PyBroadException
        try:
            return int(self._read_one(self.REG_DEVICE_ADDRESS))
        except Exception:
            return None

    def set_device_address(self, new_addr: int) -> None:
        """
        Sets a new address for the device. The address must be in the range
        1 to 247, inclusive. Any value outside this range will result in an
        exception being raised. This function modifies the `device_addr`
        attribute to reflect the updated device address.

        :param new_addr: The new Modbus device address to be set.
        :type new_addr: int
        :raises ValueError: If the `new_addr` is not within the valid range [1, 247].
        :return: None
        """
        if not (1 <= new_addr <= 247):
            raise ValueError("Modbus slave address must be in 1..247")
        self._write_one(self.REG_DEVICE_ADDRESS, new_addr)
        self.device_addr = new_addr

    def get_baud_rate(self) -> Optional[int]:
        """
        Possible rates 0=2400, 1=4800, 2=9600.
        """
        # noinspection PyBroadException
        try:
            match int(self._read_one(self.REG_BAUD_RATE)):
                case 0:
                    return 2400
                case 1:
                    return 4800
                case 2:
                    return 9600
                case other:
                    raise ValueError(f"Read a baud rate code {other} from device {self.device_addr:#X} that is unsupported. Must be 0=2400, 1=4800, or 2=9600")
        except Exception:
            return None

    def set_baud_rate(self, rate: int) -> None:
        """
        Sets the baud rate using a code: 0=2400, 1=4800, 2=9600.
        You may need to reopen the serial port after changing baud.
        """
        match rate:
            case 2400:
                code = 0
            case 4800:
                code = 1
            case 9600:
                code = 2
            case _:
                raise ValueError("Baud rate must be 2400 (0), 4800 (1), or 9600 (2)")
        if self._serial.baudrate == rate:
            return
        print(f"Changing baud rate from {self._serial.baudrate} to {rate} baud for device {self.device_addr:#X}..")
        self._write_one(self.REG_BAUD_RATE, code)
        self._serial.close()
        self._serial.baudrate = rate
        self._serial.open()

    # Low-level utilities
    def __read_registers(self, func:int, addr:int, count:int):
        """
        Reads registers from a Modbus device using the specified function code, starting
        address, and count of registers to read. Updates the device presence status based
        on the outcome.

        :param func: Modbus function code used to read the registers
        :param addr: Starting address of the registers to read
        :param count: Number of registers to read
        :return: Data read from the Modbus device as returned by the master instance, or
            None if an exception occurs
        """
        try:
            data = self._master.execute(self.device_addr, func, addr, count)
            self._is_present = True
            return data
        except mdb_exc.ModbusError as _:
            self._is_present = True
        except (serial.SerialTimeoutException, TimeoutError, OSError) as _:
            self._is_present = False

    def _read_one(self, reg_addr: int) -> int:
        """
        Try reading as Input Register first (0x04), then Holding Register (0x03).
        Returns an unsigned 16-bit integer.
        """
        # noinspection PyBroadException
        try:
            data = self.__read_registers(cst.READ_HOLDING_REGISTERS, reg_addr, 1)
            return int(data[0] & 0xFFFF)
        except Exception:
            data = self.__read_registers(cst.READ_INPUT_REGISTERS, reg_addr, 1)
            return int(data[0] & 0xFFFF)

    def _read_many(self, reg_addrs: list[int]) -> dict[int, int]:
        """
        Efficient batched read when registers are near each other, with
        fallback to per-register reads. Returns a dict mapping reg -> value.
        """
        if not reg_addrs:
            return {}
        reg_addrs = sorted(reg_addrs)
        first = reg_addrs[0]
        last = reg_addrs[-1]
        span = last - first + 1
        for func in (cst.READ_HOLDING_REGISTERS, cst.READ_INPUT_REGISTERS):
            # noinspection PyBroadException
            try:
                block = self.__read_registers(func, first, span)
                return {addr: int(block[addr - first] & 0xFFFF) for addr in reg_addrs}
            except Exception:
                continue
        return {addr: self._read_one(addr) for addr in reg_addrs}

    def _write_one(self, reg_addr: int, value: int) -> None:
        """
        Writes a single value to a register via Modbus communication. This function internally
        handles whether the operation sets the device as present or not based on success or failure
        of the operation. The implementation ensures that device presence status is updated even
        in case of exceptions like `ModbusError`, `SerialTimeoutException`, `TimeoutError` or `OSError`.

        The method communicates with the device using its specific address and attempts to
        write the provided value to the specified register address.

        :param reg_addr: Register address to which the value needs to be written.
        :type reg_addr: int
        :param value: The value to be written to the register.
        :type value: int
        :return: None
        """
        try:
            _ = self._master.execute(self.device_addr, cst.WRITE_SINGLE_REGISTER, reg_addr, output_value=value)
            self._is_present = True
        except mdb_exc.ModbusError as _:
            self._is_present = True
        except (serial.SerialTimeoutException, TimeoutError, OSError) as _:
            self._is_present = False
