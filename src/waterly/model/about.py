#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class AboutInfo:
    """
    Describes runtime/system information for the Waterly application.

    Attributes:
        os_name: Operating system name (e.g., 'Linux', 'Windows').
        os_release: OS release/version string (e.g., '6.6.51-v7+').
        waterly_version: Installed Waterly software version (e.g., '1.0.0').
        wifi_rssi: Wi‑Fi signal strength (e.g., RSSI in dBm or percentage). Use None if not applicable.
        wifi_bars: Wi‑Fi signal strength in 0-4 bars scale
        ip_address: Primary IPv4 address of the host running Waterly.
        netmask: Network mask corresponding to the primary IPv4 address.
    """

    os_name: str = "n/a"
    os_release: str = "n/a"
    os_version: str = "n/a"
    waterly_version: str = "n/a"
    waterly_sha: str = "n/a"
    waterly_branch: str = "n/a"
    waterly_build_date: str = "n/a"
    waterly_repo_url: str = "n/a"
    wifi_rssi: Optional[float] = None
    wifi_ssid: Optional[str] = None
    wifi_quality: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    netmask: Optional[str] = None

    @property
    def wifi_bars(self) -> int:
        NUMLEVELS = 5
        MINRSSI = -100
        MAXRSSI = -55
        if self.wifi_rssi <= MINRSSI:
            return 0
        if self.wifi_rssi >= MAXRSSI:
            return NUMLEVELS - 1
        in_range = MAXRSSI - MINRSSI
        out_range = NUMLEVELS - 1
        return int((self.wifi_rssi - MINRSSI) * out_range / in_range)

ABOUT = AboutInfo()     # empty object to be populated at runtime