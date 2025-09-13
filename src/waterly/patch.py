#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#

import logging
from typing import Optional
from gpiozero import OutputDevice
from time import sleep

from .model.measurement import Measurement
from .model.zone import Zone
from .model.times import now_local
from .model.units import Unit
from .dfrobot import SEN0604, SEN0605
from .storage import TrendName
from .config import CONFIG, Settings

def convert_celsius_fahrenheit(celsius: float) -> float:
    """
    Converts a temperature value from Celsius to Fahrenheit.

    This function takes a temperature in degrees Celsius and converts it to
    its equivalent in degrees Fahrenheit using the formula
    Fahrenheit = Celsius * (9/5) + 32.

    :param celsius: Temperature value in degrees Celsius to be converted.
    :type celsius: float
    :return: The temperature value converted to degrees Fahrenheit.
    :rtype: float
    """
    return celsius * 9/5 + 32

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
        #minimum sensor reading to trigger watering - depending on environmental conditions, sensor placement, this can vary from zone to zone
        self.min_sensor_humidity: float = CONFIG[Settings.MINIMUM_SENSOR_HUMIDITY_PERCENT][self.zone.name]
        self.target_humidity: float = CONFIG[Settings.HUMIDITY_TARGET_PERCENT][self.zone.name]
        self._logger = logging.getLogger(__name__)
        self._last_humidity_reading: Optional[Measurement] = None

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

    @property
    def current_humidity(self) -> Optional[Measurement]:
        """
        Gets the most recent humidity reading.

        This property retrieves the latest humidity reading recorded by the system. It
        is useful in applications where real-time or most recent humidity levels are
        required.

        :return: The most recent humidity reading.
        :rtype: float
        """
        return self._last_humidity_reading

    def start_watering(self) -> None:
        """
        Starts the watering process by activating the water relay. This updates
        the state of the relay device and logs the transition from its previous
        state.

        :raises Exception: If the relay device fails to update.
        :return: None
        """
        prev_state = "ON" if self.water_state else "OFF"
        self.relay_device.value = True
        if prev_state == "OFF":
            self._logger.info(f"Water relay for zone {self.zone.name} turned 'ON' from '{prev_state}'")
        else:
            self._logger.info(f"Water relay for zone {self.zone.name} remains 'ON'")

    def stop_watering(self) -> None:
        """
        Stops the watering process by deactivating the water relay. This updates
        the state of the relay device and logs the transition from its previous
        state.

        :raises Exception: If the relay device fails to update.
        :return: None
        """
        prev_state = "ON" if self.water_state else "OFF"
        self.relay_device.value = False
        if prev_state == "ON":
            self._logger.info(f"Water relay for zone {self.zone.name} turned 'OFF' from '{prev_state}'")
        else:
            self._logger.info(f"Water relay for zone {self.zone.name} remains 'OFF'")

    @property
    def has_npk_sensor(self) -> bool:
        """
        Checks if the patch has an NPK sensor.

        :return: True if the patch has an NPK sensor, False otherwise.
        :rtype: bool
        """
        return self.npk_sensor is not None and self.npk_sensor.is_present

    @property
    def has_rh_sensor(self) -> bool:
        """
        Checks if the patch has a relative humidity sensor.

        :return: True if the patch has a relative humidity sensor, False otherwise.
        :rtype: bool
        """
        return self.rh_sensor is not None and self.rh_sensor.is_present

    def open_sensor_bus(self):
        """
        Opens the serial connection to the sensors.

        :return: None
        :rtype: None
        """
        self.rh_sensor.open() if self.rh_sensor else None
        self.npk_sensor.open() if self.npk_sensor else None

    def close_sensor_bus(self):
        """
        Closes the serial connection to the sensors

        :return: None
        """
        self.rh_sensor.close() if self.has_rh_sensor else None
        self.npk_sensor.close() if self.has_npk_sensor else None

    def humidity(self) -> Optional[Measurement]:
        """
        Reads and returns the relative humidity measured by the sensor in percentages.

        :return: The relative humidity as a float.
        :rtype: Measurement|None
        """
        moisture = self.rh_sensor.read_moisture() if self.has_rh_sensor and self.rh_sensor.is_open else None
        if moisture is not None:
            humid = Measurement(moisture, Unit.PERCENT, now_local())
            self._last_humidity_reading = humid
            return humid
        return None

    def temperature(self) -> Optional[Measurement]:
        """
        Fetches the current temperature read by the sensor, in Celsius

        :return: The current temperature as reported by the sensor.
        :rtype: Measurement|None
        """
        if not (self.has_rh_sensor and self.rh_sensor.is_open):
            return None
        return Measurement(self.rh_sensor.read_temperature_c(), Unit.CELSIUS, now_local())

    def electric_conductivity(self) -> Optional[Measurement]:
        """
        Reads the electric conductivity using the RH sensor.

        This method uses the RH sensor to measure and return the electric conductivity value in
        microsiemens per centimeter (µS/cm). The electric conductivity measurement can be useful for various
        applications such as water quality assessment or other environmental analysis tasks.

        :return: The electric conductivity value measured by the RH sensor.
        :rtype: Measurement
        """
        if not (self.has_rh_sensor and self.rh_sensor.is_open):
            return None
        return Measurement(self.rh_sensor.read_ec(), Unit.CONDUCTIVITY, now_local())

    def ph(self) -> Optional[Measurement]:
        """
        Reads the pH value from the connected sensor.

        The method communicates with the pH sensor to retrieve the measured pH value. It ensures that the reading
        is current and accurately reflects the sensor's state.

        :return: The pH value measured by the sensor.
        :rtype: Measurement|None
        """
        if not (self.has_rh_sensor and self.rh_sensor.is_open):
            return None
        return Measurement(self.rh_sensor.read_ph(), Unit.PH, now_local())

    def salinity(self) -> Optional[Measurement]:
        """
        Reads and returns the salinity value from the RH sensor.

        This method interacts with the RH sensor to retrieve the salinity measurement.

        :return: The salinity value as an integer ppt.
        :rtype: Measurement|None
        """
        if not (self.has_rh_sensor and self.rh_sensor.is_open):
            return None
        return Measurement(self.rh_sensor.read_salinity(), Unit.PPT, now_local())

    def total_dissolved_solids(self) -> Optional[Measurement]:
        """
        Calculates and retrieves the total dissolved solids (TDS) value.

        This method uses the `rh_sensor` to read the TDS value. The TDS is typically used to measure the
        amount of dissolved substances in water or other liquids, providing a concise indication of water quality.

        :return: Total dissolved solids (TDS) value as an integer.
        :rtype: Measurement|None
        """
        if not (self.has_rh_sensor and self.rh_sensor.is_open):
            return None
        return Measurement(self.rh_sensor.read_tds(), Unit.PPM, now_local())

    def nitrogen(self) -> Optional[Measurement]:
        """
        Reads the nitrogen level from the NPK sensor.

        This method interacts with an NPK sensor to get the nitrogen level reading.
        It returns the nitrogen value as an integer in mg/kg unit.

        :return: The nitrogen level as an integer from the sensor.
        :rtype: Measurement|None
        """
        if not (self.has_npk_sensor and self.npk_sensor.is_open):
            return None
        return Measurement(self.npk_sensor.read_nitrogen(), Unit.MG_PER_KG, now_local())

    def phosphorus(self) -> Optional[Measurement]:
        """
        Reads the phosphorus level from the NPK sensor.

        This method retrieves the phosphorus level detected by the NPK sensor and
        returns it as an integer value in mg/kg unit.

        :return: The phosphorus level as detected by the NPK sensor.
        :rtype: Measurement|None
        """
        if not (self.has_npk_sensor and self.npk_sensor.is_open):
            return None
        return Measurement(self.npk_sensor.read_phosphorus(), Unit.MG_PER_KG, now_local())

    def potassium(self) -> Optional[Measurement]:
        """
        Reads the potassium level from the NPK sensor.

        This method retrieves the potassium level detected by the NPK sensor and
        returns it as an integer value in mg/kg unit.

        :return: The potassium level as detected by the NPK sensor.
        :rtype: Measurement|None
        """
        if not (self.has_npk_sensor and self.npk_sensor.is_open):
            return None
        return Measurement(self.npk_sensor.read_potassium(), Unit.MG_PER_KG, now_local())

    def measurements(self) -> dict[TrendName, Measurement]:
        """
        Convenience method to retrieve all measurements from the sensors.

        This method retrieves all measurements from the sensors and returns them as a tuple. If the patch has an NPK sensor,
        it will also include the measurements from the NPK sensor; otherwise, only the measurements from the RH sensor are returned.
        Note the temperature measurement is returned in Celsius.

        :return: A map containing the measurements from the sensors
        :rtype: dict[TrendName, Measurement]
        """
        readings: dict[TrendName, Measurement] = {}
        now = now_local()
        if self.has_rh_sensor and self.rh_sensor.is_open:
            rh_all = self.rh_sensor.read_all()
            readings[TrendName.TEMPERATURE] = Measurement(rh_all[SEN0604.ReadingType.TEMPERATURE], Unit.CELSIUS, now)
            readings[TrendName.HUMIDITY] = Measurement(rh_all[SEN0604.ReadingType.MOISTURE], Unit.PERCENT, now)
            self._last_humidity_reading = readings[TrendName.HUMIDITY]
            readings[TrendName.ELECTRICAL_CONDUCTIVITY] = Measurement(rh_all[SEN0604.ReadingType.ELECTRICAL_CONDUCTIVITY], Unit.CONDUCTIVITY, now)
            readings[TrendName.PH] = Measurement(rh_all[SEN0604.ReadingType.PH], Unit.PH, now)
            readings[TrendName.SALINITY] = Measurement(rh_all[SEN0604.ReadingType.SALINITY], Unit.PPT, now)
            readings[TrendName.TOTAL_DISSOLVED_SOLIDS] = Measurement(rh_all[SEN0604.ReadingType.TOTAL_DISSOLVED_SOLIDS], Unit.PPM, now)
        # both sensors are on the same serial port (RS485)
        if self.has_npk_sensor and self.npk_sensor.is_open:
            sleep(0.25)
            npk_all = self.npk_sensor.read_all()
            readings[TrendName.NITROGEN] = Measurement(npk_all[SEN0605.ReadingType.NITROGEN], Unit.MG_PER_KG, now)
            readings[TrendName.PHOSPHORUS] = Measurement(npk_all[SEN0605.ReadingType.PHOSPHORUS], Unit.MG_PER_KG, now)
            readings[TrendName.POTASSIUM] = Measurement(npk_all[SEN0605.ReadingType.POTASSIUM], Unit.MG_PER_KG, now)
        return readings

    def needs_watering(self):
        """
        Determines whether this patch requires watering based on the last humidity reading compared to the target humidity.

        :return: True if watering is needed; False otherwise
        :rtype: bool
        """
        needs_watering: bool = self._last_humidity_reading.value < self.target_humidity
        if needs_watering:
            self._logger.info(f"Watering needed in zone {self.zone.name} - last humidity {self._last_humidity_reading.value:.2f}% < {self.target_humidity:.2f}%")
        return needs_watering

    def check_needs_watering(self):
        """
        Determines if this patch requires watering based on reading its current humidity levels.

        The method evaluates the humidity of the patch and compares with target humidity

        :return: A boolean value indicating whether the patch needs watering, based on current readings
        :rtype: bool
        """
        self.humidity()
        return self.needs_watering()

    def has_drought(self):
        """
        Determines if a drought condition exists based on the last humidity reading
        compared to the minimum sensor humidity threshold. Logs a warning if a
        drought is detected.

        :return: Whether a drought condition exists (True/False)
        """
        drought: bool = self._last_humidity_reading.value < self.min_sensor_humidity
        if drought:
            self._logger.warning(f"Drought detected in zone {self.zone.name} - last humidity {self._last_humidity_reading.value:.2f}% < {self.min_sensor_humidity:.2f}%")
        return drought