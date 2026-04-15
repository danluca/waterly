#!/usr/bin/bash
#
# MIT License
#
# Copyright (c) 2025-2026 by Dan Luca. All rights reserved.
#
#
cd ~/code/gpy/tests

procid=`pgrep ^waterly`

if [[ -n "$procid" ]]; then
  echo "Waterly is already running with PID $procid - Cannot run sensor test while waterly is running."
else
  source ../../pycenvs/gpy/bin/activate
  python3 rs485_scan.py
  deactivate
  cd -
fi

