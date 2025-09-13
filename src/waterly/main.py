#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#

import signal
import sys
import threading
import time
import logging
import platform

from importlib.metadata import version, PackageNotFoundError
from .config import ZONES
from .patch import Patch
from .storage import init_db, get_config_from_db, get_zones_from_db
from .pulses import PulseCounter
from .scheduler import WateringManager
from .weather import WeatherService
from .log import init_logging
from .web import create_app, run_app

def uncaught_global_exception_handler(exc_type, exc_value, exc_traceback):
    logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

def uncaught_thread_exception_handler(exc_args: threading.ExceptHookArgs):
    logging.critical("Uncaught exception in thread %s", exc_args.thread.name, exc_info=(exc_args.exc_type, exc_args.exc_value, exc_args.exc_traceback))

def get_app_version() -> str:
    try:
        return version("waterly")
    except PackageNotFoundError:
        return "unknown"


def main():
    init_logging()
    logger = logging.getLogger("main")
    sys.excepthook = uncaught_global_exception_handler
    threading.excepthook = uncaught_thread_exception_handler

    os_name = platform.system()
    os_release = platform.release()
    os_version = platform.version()
    logger.info("\n\n====================================================================================================\n")
    logger.info("Starting Waterly application version %s on %s %s %s...", get_app_version(), os_name, os_release, os_version)

    # Storage
    init_db()
    get_zones_from_db()
    get_config_from_db()

    # Hardware/services
    weather = WeatherService()
    pulses = PulseCounter()

    # Start services
    weather.start()
    pulses.start()

    patches = [Patch(z) for z in ZONES.values() if z.rh_sensor_address]

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
            time.sleep(2)
    finally:
        logger.info("Shutting down...")
        manager.stop()
        weather.stop()
        pulses.stop()


if __name__ == "__main__":
    main()
