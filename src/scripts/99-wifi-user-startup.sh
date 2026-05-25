#!/usr/bin/bash

#
# MIT License
#
# Copyright (c) by Dan Luca. All rights reserved.
#
# Place in /etc/NetworkManager/dispatcher.d/ folder; file needs to be owned by root user, have execute permissions for all: -rwxr-xr-x 1 root root

# Configuration
TARGET_USER="gardener"
WIFI_INTERFACE="wlan0"       # Replace with your Wi-Fi interface name (e.g., wlan1, wlp3s0)
PROGRAM_TO_RUN="/home/gardener/code/gpy/bin/gardener_start.sh"

# Check if the event is for our Wi-Fi interface and if it's connecting ("up")
if [ "$1" = "$WIFI_INTERFACE" ] && [ "$2" = "up" ]; then
    # Start the program as the target user
    sudo -u "$TARGET_USER" -H DISPLAY=:0 "$PROGRAM_TO_RUN" &
fi