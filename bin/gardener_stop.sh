#!/usr/bin/bash
#
# MIT License
#
# Copyright (c) by Dan Luca. All rights reserved.
#
#
cd ~/code/gpy/bin

procid=`pgrep ^waterly`
if [[ -n "$procid" ]]; then
  kill -s SIGINT $procid # this stops the Flask web server
  sleep 1
  kill -s SIGTERM $procid  # this stops the app entirely and cleans up resources
  echo "Waterly process $procid has been stopped"
else
  echo "No 'waterly' process found to stop."
fi

