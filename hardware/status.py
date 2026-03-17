"""
hardware/status.py — Stato unificato per ogni periferica hardware.
"""
from enum import Enum


class StatusLevel(Enum):
    OK       = "ok"
    WARNING  = "warning"
    ERROR    = "error"
    DISABLED = "disabled"


class HardwareStatus:
    """Stato osservabile di una periferica hardware."""

    def __init__(self, name: str):
        self.name    = name
        self.level   = StatusLevel.DISABLED
        self.message = ""

    def set_ok(self, message: str = ""):
        self.level   = StatusLevel.OK
        self.message = message

    def set_warning(self, message: str = ""):
        self.level   = StatusLevel.WARNING
        self.message = message

    def set_error(self, message: str = ""):
        self.level   = StatusLevel.ERROR
        self.message = message

    def set_disabled(self, message: str = ""):
        self.level   = StatusLevel.DISABLED
        self.message = message

    def __repr__(self):
        return f"<HardwareStatus name={self.name!r} level={self.level.value} msg={self.message!r}>"
