import logging
from typing import Optional
from gpiozero import OutputDevice

from .zone import Zone
from .dfrobot import SEN0604, SEN0605

class Patch:
    """
    Represents a patch of land with sensors for monitoring and managing and a relay device for watering the zone.

    This class provides an interface to interact with various sensors and devices associated
    with a specific zone, such as retrieving environmental data (humidity, temperature, pH,
    salinity, etc.), controlling water flow through a relay device, and reading soil nutrients levels
    like nitrogen, phosphorus, and potassium. It abstracts the hardware interaction into an
    easy-to-use API for both monitoring and control purposes.

    :ivar zone: The zone associated with this patch, containing its configuration and details.
    :type zone: Zone
    :ivar relay_device: The relay device responsible for controlling water flow in the patch.
    :type relay_device: OutputDevice
    :ivar npk_sensor: The NPK sensor measuring nitrogen, phosphorus, and potassium levels in the patch soil.
    :type npk_sensor: SEN0605
    :ivar rh_sensor: The sensor measuring relative humidity, temperature, and additional parameters.
    :type rh_sensor: SEN0604
    """
    def __init__(self, zone: Zone):
        """
        Initializes the ZoneManager with a given zone.

        :param zone: The Zone instance containing configuration details like relay
            address, NPK sensor address, and RH sensor address.
        :type zone: Zone
        """
        self.zone = zone
        self.relay_device: OutputDevice = OutputDevice(self.zone.relay_address)
        self.npk_sensor: Optional[SEN0605] = SEN0605(self.zone.npk_sensor_address) if self.zone.npk_sensor_address else None
        self.rh_sensor: SEN0604 = SEN0604(self.zone.rh_sensor_address)
        self._logger = logging.getLogger(__name__)

    @property
    def name(self) -> str:
        """
        Gets the name of the zone.

        This property retrieves the name of the zone associated with this
        instance. The name is returned as a string and represents the
        name assigned to the zone.

        :return: The name of the zone
        :rtype: str
        """
        return self.zone.name

    @property
    def description(self) -> str:
        """
        Gets the description of the zone.

        This property retrieves the description of the zone associated with this
        instance.

        :return: The description of the zone
        :rtype: str
        """
        return self.zone.description

    @property
    def water_state(self) -> bool:
        """
        Property to access the current state of water flow.

        The state is determined by the value of the `relay_device`. If the relay device's value
        is `True`, water flow is currently on. If it is `False`, the water flow is off.

        :return: Current state of the water flow.
        :rtype: bool
        """
        return self.relay_device.value

    @water_state.setter
    def water_state(self, on: bool) -> None:
        """
        Sets the water state of the relay device.

        This method allows the adjustment of the relay device state
        by enabling or disabling it. The state is logged for record-keeping
        purposes based on the current status of the water zone.

        :param on: Indicates whether the relay should be enabled (True) - water flow is on
                   or disabled (False) - water flow is off.
        :type on: bool
        """
        self.relay_device.value = on
        self._logger.info(f"Water relay for zone {self.zone.name} set to {'ON' if on else 'OFF'}")

    @property
    def has_npk_sensor(self) -> bool:
        """
        Checks if the patch has an NPK sensor.

        :return: True if the patch has an NPK sensor, False otherwise.
        :rtype: bool
        """
        return self.npk_sensor is not None

    def humidity(self) -> float:
        """
        Reads and returns the relative humidity measured by the sensor in percentages.

        :return: The relative humidity as a float.
        :rtype: float
        """
        try:
            self.rh_sensor.open()
            return self.rh_sensor.read_moisture()
        finally:
            self.rh_sensor.close()

    def temperature(self, iso: bool = False) -> float:
        """
        Fetches the current temperature read by the sensor, either in Celsius or Fahrenheit degrees based on
        the input parameter. Defaults to Fahrenheit.

        :param iso: Determines the unit system for the temperature. When `True`, the temperature is returned in Celsius.
         When `False`, the temperature is returned in Fahrenheit.
        :return: The current temperature as reported by the sensor.
        :rtype: float
        """
        try:
            self.rh_sensor.open()
            return self.rh_sensor.read_temperature_c() if iso else self.rh_sensor.read_temperature_f()
        finally:
            self.rh_sensor.close()

    def electric_conductivity(self) -> int:
        """
        Reads the electric conductivity using the RH sensor.

        This method uses the RH sensor to measure and return the electric conductivity value in
        microsiemens per centimeter (µS/cm). The electric conductivity measurement can be useful for various
        applications such as water quality assessment or other environmental analysis tasks.

        :return: The electric conductivity value measured by the RH sensor.
        :rtype: int
        """
        try:
            self.rh_sensor.open()
            return self.rh_sensor.read_ec()
        finally:
            self.rh_sensor.close()

    def ph(self) -> float:
        """
        Reads the pH value from the connected sensor.

        The method communicates with the pH sensor to retrieve the measured pH value. It ensures that the reading
        is current and accurately reflects the sensor's state.

        :return: The pH value measured by the sensor.
        :rtype: float
        """
        try:
            self.rh_sensor.open()
            return self.rh_sensor.read_ph()
        finally:
            self.rh_sensor.close()

    def salinity(self) -> int:
        """
        Reads and returns the salinity value from the RH sensor.

        This method interacts with the RH sensor to retrieve the salinity measurement.

        :return: The salinity value as an integer.
        :rtype: int
        """
        try:
            self.rh_sensor.open()
            return self.rh_sensor.read_salinity()
        finally:
            self.rh_sensor.close()

    def total_dissolved_solids(self) -> int:
        """
        Calculates and retrieves the total dissolved solids (TDS) value.

        This method uses the `rh_sensor` to read the TDS value. The TDS is typically used to measure the
        amount of dissolved substances in water or other liquids, providing a concise indication of water quality.

        :return: Total dissolved solids (TDS) value as an integer.
        :rtype: int
        """
        try:
            self.rh_sensor.open()
            return self.rh_sensor.read_tds()
        finally:
            self.rh_sensor.close()

    def nitrogen(self) -> int | None:
        """
        Reads the nitrogen level from the NPK sensor.

        This method interacts with an NPK sensor to get the nitrogen level reading.
        It returns the nitrogen value as an integer in mg/kg unit.

        :return: The nitrogen level as an integer from the sensor.
        :rtype: int
        """
        if not self.has_npk_sensor:
            return None
        try:
            self.npk_sensor.open()
            return self.npk_sensor.read_nitrogen()
        finally:
            self.npk_sensor.close()

    def phosphorus(self) -> int | None:
        """
        Reads the phosphorus level from the NPK sensor.

        This method retrieves the phosphorus level detected by the NPK sensor and
        returns it as an integer value in mg/kg unit.

        :return: The phosphorus level as detected by the NPK sensor.
        :rtype: int
        """
        if not self.has_npk_sensor:
            return None
        try:
            self.npk_sensor.open()
            return self.npk_sensor.read_phosphorus()
        finally:
            self.npk_sensor.close()

    def potassium(self) -> int | None:
        """
        Reads the potassium level from the NPK sensor.

        This method retrieves the potassium level detected by the NPK sensor and
        returns it as an integer value in mg/kg unit.

        :return: The potassium level as detected by the NPK sensor.
        :rtype: int
        """
        if not self.has_npk_sensor:
            return None
        try:
            self.npk_sensor.open()
            return self.npk_sensor.read_potassium()
        finally:
            self.npk_sensor.close()

    def measurements(self) -> tuple[float, float, int, float, int, int] | tuple[float, float, int, float, int, int, int, int, int]:
        """
        Convenience method to retrieve all measurements from the sensors.

        This method retrieves all measurements from the sensors and returns them as a tuple. If the patch has an NPK sensor,
        it will also include the measurements from the NPK sensor; otherwise, only the measurements from the RH sensor are returned.
        Note the temperature measurement is returned in Celsius.

        :return: A tuple containing the measurements from the sensors: either (temperature, humidity, ec, ph, salinity, tds, nitrogen, phosphorus, potassium) or (temperature, humidity, ec, ph, salinity, tds)
        :rtype: tuple[float, float, int, float, int, int] | tuple[float, float, int, float, int, int, int, int, int]
        """
        try:
            self.rh_sensor.open()
            rh_all = self.rh_sensor.read_all()
            sal = self.rh_sensor.read_salinity()
            tds = self.rh_sensor.read_tds()
            # both sensors are on the same serial port (RS485), opening RH sensor above also covered NPK sensor
            if self.has_npk_sensor:
                npk_all = self.npk_sensor.read_all()
                return rh_all + (sal, tds) + npk_all
            else:
                return rh_all + (sal, tds)
        finally:
            self.rh_sensor.close()
