"""
hardware/sensor_bme280.py — BME280 temperature / humidity / pressure sensor.

Uses the `RPi.bme280` library together with `smbus2`:
  pip install RPi.bme280 smbus2

BME280 measures: temperature (°C), relative humidity (% RH), air pressure (hPa).
BMP280 (no humidity) is also supported — the humidity field will read ~0 % RH
and should be treated as absent; i2c_manager skips it automatically.

Typical wiring (Raspberry Pi I2C-1):
  VCC → 3.3 V      SDA → GPIO 2 (pin 3)
  GND → GND        SCL → GPIO 3 (pin 5)
  SDO → GND        → address 0x76
  SDO → 3.3 V      → address 0x77
"""

import logging
import threading
from typing import Optional

from .readings import EnvReading

logger = logging.getLogger(__name__)


class BME280Sensor:
    """
    Wrapper around the RPi.bme280 / smbus2 stack.

    Parameters
    ----------
    label   : human-readable name shown in the UI
    address : I2C address (0x76 or 0x77)
    bus_num : I2C bus number (default 1)
    """

    def __init__(self, label: str, address: int = 0x76, bus_num: int = 1):
        self.label = label
        self._address = address
        self._bus_num = bus_num
        self._bus = None
        self._params = None
        self._bme280_mod = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def start(self) -> bool:
        try:
            import smbus2
            import bme280 as _bme280
            bus    = smbus2.SMBus(self._bus_num)
            params = _bme280.load_calibration_params(bus, self._address)
            self._bus = bus
            self._params = params
            self._bme280_mod = _bme280
            logger.info("BME280 '%s' indirizzo=0x%02X OK", self.label, self._address)
            return True
        except ImportError:
            logger.warning("BME280: libreria RPi.bme280/smbus2 non trovata "
                           "(pip install RPi.bme280 smbus2)")
            return False
        except Exception as exc:
            logger.warning("BME280 '%s' init fallita: %s", self.label, exc)
            return False

    def stop(self) -> None:
        if self._bus:
            try:
                self._bus.close()
            except Exception:
                pass
        self._bus = None
        self._params = None

    # ------------------------------------------------------------------ #
    # Measurement                                                          #
    # ------------------------------------------------------------------ #

    def read(self) -> Optional[EnvReading]:
        if not self._bus or not self._params:
            return None
        try:
            with self._lock:
                data = self._bme280_mod.sample(
                    self._bus, self._address, self._params)
            # BMP280 returns humidity ≈ 0; treat as absent
            humidity = data.humidity if data.humidity > 0.5 else None
            return EnvReading(
                label=self.label,
                sensor_type="BME280",
                temperature=float(data.temperature),
                humidity=float(humidity) if humidity is not None else None,
                pressure=float(data.pressure),
            )
        except Exception as exc:
            logger.debug("BME280 '%s' lettura errore: %s", self.label, exc)
            return None
