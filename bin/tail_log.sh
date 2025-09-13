#!/usr/bin/bash
#
# MIT License
#
# Copyright (c) 2025 by Dan Luca. All rights reserved.
#
#

cd ~/code/gpy/src

log_sfx=`date +%Y-%m`
log_file=`realpath ./logs/app-${log_sfx}.log`

if [[ -f "$log_file" ]]; then
  tail -f $log_file
else
  # inform user can't find the log file
  echo "Log file $log_file cannot be found"
fi

