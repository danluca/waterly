#  MIT License

#  Copyright (c) 2025 by Dan Luca. All rights reserved.


"""
Water log model for recording watering events.

This module now distinguishes between:
- WateringAssessment: a zone-agnostic decision and schedule with the reasoning JSON.
- WateringRecord: a per-zone execution record with actual outcomes (humidity, amount, executed).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from .measurement import WateringMeasurement
from .zone import Zone
from ..config import ZONES

@dataclass
class WateringAssessment:
    """
    Zone-agnostic watering decision made for a given time window.
    """
    start_time: datetime
    reason: dict
    enabled: bool

    def json_encode(self) -> dict[str, Any]:
        return {
            "__type__": "WateringAssessment",
            "start_time": self.start_time,
            "reason": self.reason,
            "enabled": self.enabled
        }

    @staticmethod
    def json_decode(obj: dict[str, Any]) -> Optional["WateringAssessment"]:
        if obj.get("__type__") != "WateringAssessment":
            return None
        return WateringAssessment(
            start_time=obj.get("start_time"),
            reason=obj.get("reason"),
            enabled=obj.get("enabled"),
        )

    def __str__(self) -> str:
        return f"WateringAssessment{{enabled={self.enabled}, start={self.start_time.isoformat()}, reason={self.reason}}}"

@dataclass
class WateringRecord:
    """
    Per-zone execution for a given assessment.
    """
    zone: Zone
    executed: bool = False
    measurement: WateringMeasurement = None

    def json_encode(self) -> dict[str, Any]:
        return {
            "__type__": "WateringRecord",
            "zone_name": self.zone.name,
            "executed": self.executed,
            "measurement": self.measurement,
        }

    @staticmethod
    def json_decode(obj: dict[str, Any]) -> Optional["WateringRecord"]:
        if obj.get("__type__") != "WateringRecord":
            return None
        zone_name = obj.get("zone_name")
        return WateringRecord(
            zone=next((z for z in ZONES.values() if z.name == zone_name), None),
            executed=bool(obj.get("executed", False)),
            measurement=obj.get("measurement"),
        )

    def __str__(self) -> str:
        return f"WateringRecord{{zone_name={self.zone.name}, executed={self.executed}, measurement={self.measurement}}}"

