"""
hardware/sensor_sht30.py — SHT30 / SHT31 temperature + humidity sensor driver.

Uses only `smbus2` for raw I2C access — no extra library required.
CRC-8 validation (Sensirion polynomial 0x31) is applied to all readings.

SHT30 measures: temperature (°C), relative humidity (% RH).
Compatible with SHT30-D, SHT31-D, SHT35-D.

Typical wiring (Raspberry Pi I2C-1):
  VCC → 3.3 V      SDA → GPIO 2 (pin 3)
  GND → GND        SCL → GPIO 3 (pin 5)
  ADDR → GND       → address 0x44
  ADDR → 3.3 V     → address 0x45
"""

import logging
import struct
import threading
import time
from typing import Optional

from .readings import EnvReading

logger = logging.getLogger(__name__)

# Single-shot measurement — high repeatability, no clock stretching
_CMD_MSB   = 0x2C
_CMD_LSB   = 0x06
_MEAS_WAIT = 0.025    # 25 ms > 15.5 ms datasheet max for high repeatability


def _crc8(data: bytes) -> int:
    """CRC-8 per Sensirion: polynomial 0x31, init 0xFF."""
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) if (crc & 0x80) else (crc << 1)
            crc &= 0xFF
    return crc


class SHT30Sensor:
    """
    Minimal smbus2-based driver for SHT30/SHT31 sensors.

    Parameters
    ----------
    label   : human-readable name shown in the UI
    address : I2C address (0x44 or 0x45)
    bus_num : I2C bus number (default 1)
    """

    def __init__(self, label: str, address: int = 0x44, bus_num: int = 1):
        self.label = label
        self._address = address
        self._bus_num = bus_num
        self._bus = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def start(self) -> bool:
        try:
            import smbus2
            bus = smbus2.SMBus(self._bus_num)
            # Soft reset to verify the sensor is reachable
            bus.write_i2c_block_data(self._address, 0x30, [0xA2])
            time.sleep(0.02)
            self._bus = bus
            logger.info("SHT30 '%s' indirizzo=0x%02X OK", self.label, self._address)
            return True
        except ImportError:
            logger.warning("SHT30: libreria smbus2 non trovata (pip install smbus2)")
            return False
        except Exception as exc:
            logger.warning("SHT30 '%s' init fallita: %s", self.label, exc)
            return False

    def stop(self) -> None:
        if self._bus:
            try:
                self._bus.close()
            except Exception:
                pass
        self._bus = None

    # ------------------------------------------------------------------ #
    # Measurement                                                          #
    # ------------------------------------------------------------------ #

    def read(self) -> Optional[EnvReading]:
        """
        Trigger a single-shot measurement and return an EnvReading.
        Returns None if the bus is unavailable or the CRC check fails.
        Thread-safe.
        """
        if not self._bus:
            return None
        try:
            with self._lock:
                self._bus.write_i2c_block_data(
                    self._address, _CMD_MSB, [_CMD_LSB])
                time.sleep(_MEAS_WAIT)
                raw = self._bus.read_i2c_block_data(self._address, 0x00, 6)

            # CRC validation
            if _crc8(bytes(raw[0:2])) != raw[2]:
                logger.warning("SHT30 '%s' CRC errato (temperatura)", self.label)
                return None
            if _crc8(bytes(raw[3:5])) != raw[5]:
                logger.warning("SHT30 '%s' CRC errato (umidità)", self.label)
                return None

            t_raw, h_raw = struct.unpack(">HH", bytes([*raw[0:2], *raw[3:5]]))
            temperature = -45.0 + 175.0 * t_raw / 65535.0
            humidity    = 100.0 * h_raw  / 65535.0
            # Clamp humidity to physical range
            humidity    = max(0.0, min(100.0, humidity))

            return EnvReading(
                label=self.label,
                sensor_type="SHT30",
                temperature=temperature,
                humidity=humidity,
                pressure=None,
            )
        except Exception as exc:
            logger.debug("SHT30 '%s' lettura errore: %s", self.label, exc)
            return None
