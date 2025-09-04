#!/usr/bin/bash
cd ~/code/gpy/bin

procid=`pgrep ^waterly`
if [[ -n "$procid" ]]; then
  kill -s SIGINT $procid # this stops the Flask web server
  sleep 1
  kill -s SIGTERM $procid  # this stops the app entirely and cleans up resources
else
  echo "No 'waterly' process found to stop."
fi

