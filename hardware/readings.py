"""
hardware/readings.py — Shared telemetry data types.

Consumed by i2c_manager and exposed to UI screens via I2CManager getters.
All dataclasses are immutable snapshots (created fresh on each poll).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class PowerReading:
    """Snapshot from a single INA219/INA226 sensor."""

    label: str
    bus_voltage: float        # V   (load-side rail voltage)
    current_ma: float         # mA  (positive = discharge, negative = charge)
    power_mw: float           # mW
    timestamp: datetime = field(default_factory=datetime.now)

    def format_voltage(self) -> str:
        return f"{self.bus_voltage:.2f} V"

    def format_current(self) -> str:
        if abs(self.current_ma) >= 1000:
            return f"{self.current_ma / 1000:.2f} A"
        return f"{self.current_ma:.0f} mA"

    def format_power(self) -> str:
        if self.power_mw >= 1000:
            return f"{self.power_mw / 1000:.2f} W"
        return f"{self.power_mw:.0f} mW"

    def format_compact(self) -> str:
        """One-line summary for the home screen strip."""
        return f"{self.format_voltage()}  {self.format_current()}  {self.format_power()}"


@dataclass(frozen=True)
class EnvReading:
    """Snapshot from a BME280 or SHT30/SHT31 environmental sensor."""

    label: str
    sensor_type: str              # "BME280" | "SHT30"
    temperature: float            # °C
    humidity: Optional[float]     # % RH  (None if sensor lacks humidity)
    pressure: Optional[float]     # hPa   (None if sensor lacks pressure)
    timestamp: datetime = field(default_factory=datetime.now)

    def format_temperature(self) -> str:
        return f"{self.temperature:.1f} °C"

    def format_humidity(self) -> str:
        if self.humidity is None:
            return ""
        return f"{self.humidity:.0f}%"

    def format_pressure(self) -> str:
        if self.pressure is None:
            return ""
        return f"{self.pressure:.1f} hPa"

    def format_compact(self) -> str:
        """One-line summary for the home screen strip."""
        parts = [self.format_temperature()]
        if self.humidity is not None:
            parts.append(self.format_humidity())
        if self.pressure is not None:
            parts.append(self.format_pressure())
        return "  ".join(parts)
