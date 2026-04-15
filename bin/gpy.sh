#!/usr/bin/bash
#
# MIT License
#
# Copyright (c) 2025,2026 by Dan Luca. All rights reserved.
#
#
cd ~/code
source ./pycenvs/gpy/bin/activate
cd  ./gpy/bin
# lgpio uses the modern /dev/gpiochip interface; required on kernel 6.x where
# the legacy sysfs GPIO (/sys/class/gpio) used by gpiozero's native factory was removed.
export GPIOZERO_PIN_FACTORY=lgpio
waterly
deactivate

