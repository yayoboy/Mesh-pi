"""
hardware/sensor_ina219.py — INA219 / INA226 current & power sensor driver.

Uses the `pi-ina219` library (pip install pi-ina219).
Falls back gracefully if the library or I2C bus is unavailable.

Typical wiring (INA219 breakout, Raspberry Pi I2C-1):
  VCC → 3.3 V          SDA → GPIO 2 (pin 3)
  GND → GND            SCL → GPIO 3 (pin 5)
  IN+ / IN- → in series with load (shunt resistor direction matters)

Default I2C address: 0x40 (A0=A1=GND).
Address range: 0x40–0x4F (A0/A1 solder bridges).
"""

import logging
import threading
from typing import Optional

from .readings import PowerReading

logger = logging.getLogger(__name__)


class INA219Sensor:
    """
    Thin wrapper around the pi-ina219 `INA219` class.

    Parameters
    ----------
    label             : human-readable name shown in the UI
    address           : I2C address as int (e.g. 0x40)
    bus_num           : I2C bus number (1 on all modern Pis)
    shunt_ohms        : shunt resistor value (Ω) — check your breakout board
    max_expected_amps : calibration ceiling in amperes
    """

    def __init__(self, label: str, address: int = 0x40, bus_num: int = 1,
                 shunt_ohms: float = 0.1, max_expected_amps: float = 2.0):
        self.label = label
        self._address = address
        self._bus_num = bus_num
        self._shunt = shunt_ohms
        self._max_amps = max_expected_amps
        self._ina = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def start(self) -> bool:
        """
        Initialise the sensor. Returns True on success, False on any failure
        (missing library, I2C not enabled, wrong address, etc.).
        """
        try:
            from ina219 import INA219
            ina = INA219(
                shunt_ohms=self._shunt,
                max_expected_amps=self._max_amps,
                address=self._address,
                busnum=self._bus_num,
            )
            ina.configure()
            self._ina = ina
            logger.info("INA219 '%s' indirizzo=0x%02X OK", self.label, self._address)
            return True
        except ImportError:
            logger.warning("INA219: libreria pi-ina219 non trovata (pip install pi-ina219)")
            return False
        except Exception as exc:
            logger.warning("INA219 '%s' init fallita: %s", self.label, exc)
            return False

    def stop(self) -> None:
        self._ina = None

    # ------------------------------------------------------------------ #
    # Measurement                                                          #
    # ------------------------------------------------------------------ #

    def read(self) -> Optional[PowerReading]:
        """
        Read voltage, current, and power. Returns None on error.
        Thread-safe — safe to call from the I2C polling thread.
        """
        if not self._ina:
            return None
        try:
            with self._lock:
                bus_v  = float(self._ina.voltage())
                cur_ma = float(self._ina.current())
                pwr_mw = float(self._ina.power())
            return PowerReading(
                label=self.label,
                bus_voltage=bus_v,
                current_ma=cur_ma,
                power_mw=pwr_mw,
            )
        except Exception as exc:
            logger.debug("INA219 '%s' lettura errore: %s", self.label, exc)
            return None
