"""
hardware/gps_reader.py — Serial GPS reader (NMEA 0183).

Reads GPGGA / GPRMC sentences in a background thread and exposes the
latest fix via GpsFix dataclass. Fires on_fix callbacks on every update.

Falls back to stub mode if pyserial or pynmea2 are unavailable.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger(__name__)

try:
    import serial
    import pynmea2
    GPS_LIBS_OK = True
except ImportError:
    GPS_LIBS_OK = False
    logger.warning("pyserial/pynmea2 not found — GPS runs in stub mode")


@dataclass
class GpsFix:
    """Current GPS fix. All fields are None when no fix is available."""
    latitude:   Optional[float] = None
    longitude:  Optional[float] = None
    altitude:   Optional[float] = None    # metres
    speed:      Optional[float] = None    # km/h
    course:     Optional[float] = None    # degrees true
    satellites: int  = 0
    quality:    int  = 0    # 0=no fix, 1=GPS, 2=DGPS
    hdop:       float = 99.9
    timestamp:  Optional[datetime] = None
    has_fix:    bool = False

    def format_coords(self) -> str:
        if not self.has_fix:
            return "Nessun fix"
        return f"{self.latitude:.6f}, {self.longitude:.6f}"

    def format_altitude(self) -> str:
        if self.altitude is None:
            return "—"
        return f"{self.altitude:.1f} m"

    def format_speed(self) -> str:
        if self.speed is None:
            return "—"
        return f"{self.speed:.1f} km/h"


class GpsReader:
    """
    Background NMEA reader.

    Parameters
    ----------
    port : str   Serial device, e.g. '/dev/ttyAMA0' or '/dev/ttyUSB1'
    baud : int   Baud rate (GPS modules typically 9600)
    """

    RECONNECT_DELAY = 5  # seconds between reconnection attempts

    def __init__(self, port: str = "/dev/ttyAMA0", baud: int = 9600):
        self.port = port
        self.baud = baud

        self.fix = GpsFix()
        self.active = False

        self._fix_cbs:  list[Callable[[GpsFix], None]] = []
        self._lost_cbs: list[Callable[[], None]] = []
        self._thread: Optional[threading.Thread] = None
        self._ser: Optional[object] = None

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def start(self) -> bool:
        if not GPS_LIBS_OK:
            return False
        self.active = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="gps-reader")
        self._thread.start()
        logger.info("GPS reader avviato — %s @ %d", self.port, self.baud)
        return True

    def stop(self) -> None:
        self.active = False
        self._close_serial()

    # ------------------------------------------------------------------ #
    # Callback registration                                                #
    # ------------------------------------------------------------------ #

    def on_fix(self, cb: Callable[[GpsFix], None]) -> None:
        self._fix_cbs.append(cb)

    def on_fix_lost(self, cb: Callable[[], None]) -> None:
        self._lost_cbs.append(cb)

    # ------------------------------------------------------------------ #
    # Internal — reader loop                                               #
    # ------------------------------------------------------------------ #

    def _loop(self) -> None:
        while self.active:
            try:
                self._ser = serial.Serial(
                    self.port, self.baud, timeout=2.0)
                logger.info("GPS porta aperta: %s", self.port)
                self._read_loop()
            except Exception as exc:
                logger.error("GPS errore connessione: %s", exc)
                self._mark_fix_lost()
                self._close_serial()
                if self.active:
                    time.sleep(self.RECONNECT_DELAY)

    def _read_loop(self) -> None:
        fix_timeout = 10.0   # seconds without GPGGA before declaring fix lost
        last_fix_time = time.monotonic()

        while self.active and self._ser and self._ser.is_open:
            try:
                raw = self._ser.readline().decode("ascii", errors="replace").strip()
                if not raw.startswith("$"):
                    continue

                msg = pynmea2.parse(raw)
                updated = False

                if isinstance(msg, pynmea2.GGA):
                    updated = self._handle_gga(msg)
                    if updated:
                        last_fix_time = time.monotonic()
                elif isinstance(msg, pynmea2.RMC):
                    self._handle_rmc(msg)

                if updated:
                    self._notify_fix()

                # Check fix timeout
                if time.monotonic() - last_fix_time > fix_timeout:
                    if self.fix.has_fix:
                        self._mark_fix_lost()

            except pynmea2.ParseError:
                pass
            except Exception as exc:
                logger.debug("GPS parse: %s", exc)

    def _handle_gga(self, msg) -> bool:
        """Parse GGA sentence. Returns True if fix status changed or updated."""
        quality = int(msg.gps_qual) if msg.gps_qual else 0
        if quality == 0:
            if self.fix.has_fix:
                self._mark_fix_lost()
            return False

        self.fix.latitude   = msg.latitude
        self.fix.longitude  = msg.longitude
        self.fix.altitude   = float(msg.altitude) if msg.altitude else None
        self.fix.satellites = int(msg.num_sats) if msg.num_sats else 0
        self.fix.quality    = quality
        self.fix.hdop       = float(msg.horizontal_dil) if msg.horizontal_dil else 99.9
        self.fix.has_fix    = True
        self.fix.timestamp  = datetime.now()
        return True

    def _handle_rmc(self, msg) -> None:
        """Parse RMC sentence for speed and course."""
        if not msg.status or msg.status != "A":
            return
        try:
            self.fix.speed  = float(msg.spd_over_grnd) * 1.852  # knots→km/h
            self.fix.course = float(msg.true_course) if msg.true_course else None
        except (ValueError, TypeError):
            pass

    def _mark_fix_lost(self) -> None:
        self.fix.has_fix = False
        self.fix.quality = 0
        for cb in self._lost_cbs:
            try:
                cb()
            except Exception:
                pass

    def _notify_fix(self) -> None:
        for cb in self._fix_cbs:
            try:
                cb(self.fix)
            except Exception:
                pass

    def _close_serial(self) -> None:
        try:
            if self._ser and self._ser.is_open:
                self._ser.close()
        except Exception:
            pass
        self._ser = None
