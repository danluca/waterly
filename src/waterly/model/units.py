#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#
from enum import StrEnum

class UnitType(StrEnum):
    """
    Represents a unit system for measurement.

    This class is an enumeration of the two used unit systems: Metric and Imperial. It is used to specify
    and work with the measurement systems in different contexts.

    :cvar METRIC: The metric measurement system, commonly used worldwide.
    :cvar IMPERIAL: The imperial measurement system, primarily used in the United States.
    """
    METRIC = "metric"
    IMPERIAL = "imperial"

class Unit(StrEnum):
    """
    Enumeration of measurement units.

    This class defines various constants representing different units of
    measurement used in scientific, industrial, or everyday contexts. Each
    unit is represented as a string. This enumeration serves to standardize
    the representation of units in the program, ensuring consistency.
    """
    CELSIUS = "°C"
    FAHRENHEIT = "°F"
    LITERS = "L"
    GALLONS = "gal"
    PPM = "ppm"
    PPT = "ppt"
    CONDUCTIVITY = "µS/cm"  # Microsiemens per centimeter
    PH = "pH"
    PERCENT = "%"
    MG_PER_KG = "mg/kg"
    INCHES = "in"
    MM = "mm"
    M3_PER_M3 = "m³/m³"
    HPA = "hPa"
    SECONDS = "s"
    MILLIS = "ms"