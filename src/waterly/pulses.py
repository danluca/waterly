import threading
import logging

from typing import Optional
from gpiozero import Button
from .config import PULSE_GPIO_PIN, WATER_FLOW_FREQUENCY_FACTOR

class PulseCounter:
    """
    Manages counting pulses from a GPIO pin and calculates corresponding water flow in liters.

    This class is designed to handle pulse counting using a GPIO pin, typically coming
    from a water flow sensor, and calculates the flow in liters based on the predefined
    specifications. It provides methods to start and stop the monitoring process, simulate
    pulses for testing purposes, and compute the flow rate in liters over a given period.

    :ivar _count: Internal counter for the number of pulses detected.
    :type _count: int
    :ivar _lock: Thread lock to ensure thread-safe operations during pulse counting.
    :type _lock: threading.RLock
    :ivar _started: Indicates whether the pulse counter has been started.
    :type _started: bool
    """
    def __init__(self):
        self._count: int = 0
        self._lock = threading.RLock()
        self._started = False
        self._button: Optional[Button] = None

    def start(self):
        """
        Starts the PulseCounter, setting up the necessary GPIO configuration and enabling
        event detection on a specified GPIO pin. This method ensures that the GPIO setup
        is performed only if the counter has not already been started. It also attaches
        a callback to the GPIO pin for handling pulse events.

        :raises RuntimeError: If the GPIO library is not properly configured.
        :return: None
        """
        if self._started:
            return
        # Using gpiozero Button with pull_up=True matches the original FALLING-edge approach:
        # the sensor pulls the line low; when_pressed corresponds to the falling edge.
        self._button = Button(PULSE_GPIO_PIN, pull_up=True, bounce_time=0.005)
        self._button.when_pressed = self._cb
        self._started = True
        logging.getLogger(__name__).info(f"PulseCounter started on GPIO {PULSE_GPIO_PIN}")

    def stop(self):
        """
        Stops the active process if it has been started. Cleans up GPIO resources
        and updates the internal state to indicate the process is no longer running.

        :return: None
        """
        if not self._started:
            return
        if self._button is not None:
            # Detach callback and release the GPIO resource
            self._button.when_pressed = None
            self._button.close()
            self._button = None
        self._started = False
        logging.getLogger(__name__).info(f"PulseCounter stopped on GPIO {PULSE_GPIO_PIN}")

    def _cb(self, channel):
        """
        Handles the callback invocation for an associated channel. This method is responsible
        for managing the internal count of callback executions in a thread-safe manner.

        :param channel: The channel for which the callback is invoked.
        :type channel: Any
        :return: None
        """
        with self._lock:
            self._count += 1

    def simulate_pulses(self, pulses: int):
        """
        Simulates pulses by incrementing an internal counter. The method ensures thread
        safety while updating the count and allows only positive pulse values to be added.

        :param pulses: Number of pulses to simulate. Must be a non-negative integer.
        :type pulses: int
        :return: None
        """
        # For dummy mode/testing via web endpoint
        with self._lock:
            self._count += max(0, int(pulses))

    def read_and_reset_liters(self, seconds: float) -> float:
        """
        Calculates the amount of water (in liters) that passed within a given duration
        and resets the current pulse count to zero.

        The calculation is based on the relationship between pulses, frequency, and
        water flow rate specified as:
            freq(Hz) = 5.5 * flow(L/min)

        This function assumes that pulse measurements are accumulated until this call
        and resets the count upon execution.

        :param seconds: Duration in seconds over which the pulses were counted.
        :type seconds: float
        :return: Calculated volume of water in liters based on the measured pulses and
            duration.
        :rtype: float
        """
        # Convert counted pulses to liters based on duration.
        # Spec: freq(Hz) = 5.5 * flow(L/min)
        # pulses = freq * seconds
        # flow(L/min) = freq / 5.5 = pulses/seconds / 5.5
        # liters = flow(L/min) * (seconds / 60)
        with self._lock:
            pulses = self._count
            self._count = 0
        if seconds <= 0:
            return 0.0
        freq = pulses / seconds
        flow_lpm = freq / WATER_FLOW_FREQUENCY_FACTOR
        liters = flow_lpm * (seconds / 60.0)
        return liters
