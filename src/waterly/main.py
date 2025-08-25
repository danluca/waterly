import signal
import time
import logging

from .config import HTTP_HOST, HTTP_PORT
from .pulses import PulseCounter
from .scheduler import WateringManager
from .weather import WeatherService
from .web import WebServer
from .storage import record_event
from .log import init_logging

def main():
    init_logging()
    # Hardware/services
    weather = WeatherService()
    pulses = PulseCounter()

    # Start services
    weather.start()
    pulses.start()

    manager = WateringManager(relays, hum_sensors, npk_sensors, weather, pulses)
    manager.start()

    web = WebServer(weather, pulses, HTTP_HOST, HTTP_PORT)
    web.start()

    record_event("System started")

    # Graceful shutdown
    stop = False
    def handle_sig(signum, frame):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    try:
        while not stop:
            time.sleep(0.5)
    finally:
        record_event("Shutting down...")
        web.stop()
        manager.stop()
        weather.stop()
        pulses.stop()

if __name__ == "__main__":
    main()
