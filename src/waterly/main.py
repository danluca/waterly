import signal
import time
import logging

from .config import ZONES
from .patch import Patch
from .storage import init_default_trends, create_trends_store
from .pulses import PulseCounter
from .scheduler import WateringManager
from .weather import WeatherService
from .log import init_logging
from .web import create_app, run_app


def main():
    init_logging()
    logger = logging.getLogger("main")

    logger.info("Starting application...")
    # Storage
    init_default_trends()
    create_trends_store()

    # Hardware/services
    weather = WeatherService()
    pulses = PulseCounter()

    # Start services
    weather.start()
    pulses.start()

    patches = [
        Patch(ZONES[1]),
        Patch(ZONES[2]),
        Patch(ZONES[3])
    ]

    manager = WateringManager(patches, weather, pulses)
    manager.start()

    logger.info("Starting web server...")

    create_app()
    run_app()

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
        logger.info("Shutting down...")
        manager.stop()
        weather.stop()
        pulses.stop()


if __name__ == "__main__":
    main()
