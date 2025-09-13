#!/usr/bin/bash
#
# MIT License
#
# Copyright (c) 2025 by Dan Luca. All rights reserved.
#
#
cd ~/code/gpy/bin

procid=`pgrep ^waterly`

if [[ -n "$procid" ]]; then
  echo "Waterly is already running with PID $procid"
else
  # launch in background, no stdout file - we have our proper log file
  nohup  ./gpy.sh  > /dev/null 2>&1 &
#  nohup  ./gpy.sh &
fi

