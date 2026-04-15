#  MIT License
#
#  Copyright (c) 2025,2026 by Dan Luca. All rights reserved.
#
"""
DFRobot sensor package - provides access to various DFRobot sensor classes
including soil humidity (SEN0604) and NPK sensor (SEN0605) as well as environmental sensor (SEN0438).
"""


from .sen0604 import SEN0604
from .sen0605 import SEN0605
from .sen0438 import SEN0438

__all__ = ["SEN0604", "SEN0605", "SEN0438"]
