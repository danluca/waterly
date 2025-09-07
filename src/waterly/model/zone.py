#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class Zone:
    """
    Represents a garden zone definition and its associated hardware addresses.

    Attributes:
        name: Human-friendly name for the zone.
        description: Optional description of the zone.
        rh_sensor_address: Address for the relative humidity (RH) sensor (e.g., I2C address).
        npk_sensor_address: Address for the NPK sensor (e.g., I2C/Modbus address).
        relay_address: Address of the relay controlling this zone.
    """
    name: str
    description: str = ""
    rh_sensor_address: int = None
    npk_sensor_address: Optional[int] = None
    relay_address: int = None

    def __post_init__(self) -> None:
        # Basic validation to ensure a non-empty zone name is provided.
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("zone_name must be a non-empty string")

