"""
hardware/i2c_manager.py — I2C sensor orchestrator.

Manages all optional I2C telemetry sensors:
  - INA219 / INA226  → voltage, current, power  (PowerReading)
  - BME280           → temperature, humidity, pressure (EnvReading)
  - SHT30 / SHT31   → temperature, humidity (EnvReading)

All sensors are optional. If the library is absent or the I2C bus is
unavailable, that sensor is silently skipped.

A single daemon thread polls all active sensors at a configurable interval
and stores the latest readings. Callers retrieve data via thread-safe getters
or register callbacks that fire after each successful poll cycle.

Configuration (in config/settings.json → "i2c"):
  {
    "bus": 1,
    "poll_interval_ms": 2000,
    "sensors": [
      { "type": "ina219",  "enabled": false, "address": "0x40",
        "label": "Batteria", "shunt_ohms": 0.1, "max_expected_amps": 2.0 },
      { "type": "bme280",  "enabled": false, "address": "0x76",
        "label": "Meteo" },
      { "type": "sht30",   "enabled": false, "address": "0x44",
        "label": "Temp/Umidità" }
    ]
  }

Sensor types supported
----------------------
  "ina219"  — INA219 or INA226 (same pi-ina219 driver, same register map)
  "bme280"  — BME280 (full: temperature + humidity + pressure)
              BMP280 (pressure only; humidity field omitted automatically)
  "sht30"   — SHT30, SHT31, SHT35 (temperature + humidity)
"""

import logging
import threading
import time
from typing import Callable, Optional

from .readings import EnvReading, PowerReading
from .sensor_bme280 import BME280Sensor
from .sensor_ina219 import INA219Sensor
from .sensor_sht30 import SHT30Sensor
from .status import HardwareStatus, StatusLevel

logger = logging.getLogger(__name__)


class I2CManager:
    """
    Central I2C telemetry manager.

    Parameters
    ----------
    cfg : full settings dict — the `i2c` sub-dict is read via cfg["i2c"].
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg

        self._sensors_power: list[INA219Sensor] = []
        self._sensors_env: list[BME280Sensor | SHT30Sensor] = []

        self._readings_power: list[PowerReading] = []
        self._readings_env: list[EnvReading] = []
        self._lock = threading.Lock()

        self._power_cbs: list[Callable[[list[PowerReading]], None]] = []
        self._env_cbs:   list[Callable[[list[EnvReading]],   None]] = []

        self._running = False
        self._poll_thread: Optional[threading.Thread] = None

        self.status = HardwareStatus("i2c")
        self.status.set_disabled("Nessun sensore configurato")

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Initialise all enabled sensors and launch the polling thread."""
        i2c_cfg = self.cfg.get("i2c", {})
        if not i2c_cfg:
            return

        self._init_sensors(i2c_cfg)

        if not self._sensors_power and not self._sensors_env:
            logger.debug("I2C: nessun sensore attivo")
            self.status.set_disabled("Nessun sensore configurato")
            return

        n = len(self._sensors_power) + len(self._sensors_env)
        self.status.set_ok(f"{n} sensore/i configurati")

        self._running = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="i2c-poll")
        self._poll_thread.start()
        logger.info("I2C: avviato (%d potenza, %d ambiente)",
                    len(self._sensors_power), len(self._sensors_env))

    def stop(self) -> None:
        """Stop the polling thread and release all sensor resources."""
        self._running = False
        for s in self._sensors_power + self._sensors_env:  # type: ignore[operator]
            try:
                s.stop()
            except Exception:
                pass
        self._sensors_power.clear()
        self._sensors_env.clear()

    def restart(self) -> None:
        """Hot-reload after settings change."""
        self.stop()
        time.sleep(0.1)   # allow thread to exit cleanly
        self._readings_power.clear()
        self._readings_env.clear()
        self.start()

    # ------------------------------------------------------------------ #
    # Thread-safe data access                                              #
    # ------------------------------------------------------------------ #

    def get_power_readings(self) -> list[PowerReading]:
        with self._lock:
            return list(self._readings_power)

    def get_env_readings(self) -> list[EnvReading]:
        with self._lock:
            return list(self._readings_env)

    def has_sensors(self) -> bool:
        """True if at least one sensor successfully initialised."""
        return bool(self._sensors_power or self._sensors_env)

    # ------------------------------------------------------------------ #
    # Callback registration                                                #
    # ------------------------------------------------------------------ #

    def on_power_update(self, cb: Callable[[list[PowerReading]], None]) -> None:
        """Register callback fired after each power poll cycle (background thread)."""
        self._power_cbs.append(cb)

    def on_env_update(self, cb: Callable[[list[EnvReading]], None]) -> None:
        """Register callback fired after each environment poll cycle."""
        self._env_cbs.append(cb)

    # ------------------------------------------------------------------ #
    # Sensor initialisation                                                #
    # ------------------------------------------------------------------ #

    def _init_sensors(self, i2c_cfg: dict) -> None:
        bus = int(i2c_cfg.get("bus", 1))

        for sensor_cfg in i2c_cfg.get("sensors", []):
            if not sensor_cfg.get("enabled", False):
                continue

            stype   = sensor_cfg.get("type", "").lower()
            label   = sensor_cfg.get("label", stype.upper())
            addr_s  = sensor_cfg.get("address", "0x40")
            address = int(addr_s, 16) if isinstance(addr_s, str) else int(addr_s)

            try:
                if stype == "ina219":
                    s = INA219Sensor(
                        label=label,
                        address=address,
                        bus_num=bus,
                        shunt_ohms=float(sensor_cfg.get("shunt_ohms", 0.1)),
                        max_expected_amps=float(
                            sensor_cfg.get("max_expected_amps", 2.0)),
                    )
                    if s.start():
                        self._sensors_power.append(s)

                elif stype == "bme280":
                    s = BME280Sensor(label=label, address=address, bus_num=bus)
                    if s.start():
                        self._sensors_env.append(s)

                elif stype in ("sht30", "sht31"):
                    s = SHT30Sensor(label=label, address=address, bus_num=bus)
                    if s.start():
                        self._sensors_env.append(s)

                else:
                    logger.warning("I2C: tipo sensore sconosciuto '%s'", stype)

            except Exception as exc:
                logger.error("I2C: init '%s' fallita: %s", label, exc)

    # ------------------------------------------------------------------ #
    # Polling loop (daemon thread)                                         #
    # ------------------------------------------------------------------ #

    def _poll_loop(self) -> None:
        i2c_cfg  = self.cfg.get("i2c", {})
        interval = i2c_cfg.get("poll_interval_ms", 2000) / 1000.0

        while self._running:
            try:
                # ── Power sensors ─────────────────────────────────────────
                if self._sensors_power:
                    new_power: list[PowerReading] = []
                    for s in self._sensors_power:
                        r = s.read()
                        if r:
                            new_power.append(r)

                    if new_power:
                        with self._lock:
                            self._readings_power = new_power
                        for cb in self._power_cbs:
                            try:
                                cb(list(new_power))
                            except Exception as exc:
                                logger.debug("power callback error: %s", exc)

                # ── Environmental sensors ─────────────────────────────────
                if self._sensors_env:
                    new_env: list[EnvReading] = []
                    for s in self._sensors_env:
                        r = s.read()
                        if r:
                            new_env.append(r)

                    if new_env:
                        with self._lock:
                            self._readings_env = new_env
                        for cb in self._env_cbs:
                            try:
                                cb(list(new_env))
                            except Exception as exc:
                                logger.debug("env callback error: %s", exc)

            except Exception as e:
                logger.error("I2C: errore polling: %s", e)
                self.status.set_error(str(e))

            # Sleep interruptibly in 100 ms slices
            remaining = interval
            while remaining > 0 and self._running:
                time.sleep(min(0.1, remaining))
                remaining -= 0.1
