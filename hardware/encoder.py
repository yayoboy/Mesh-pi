"""
hardware/encoder.py — Rotary encoder via gpiozero.

Emits:
  on_rotate(direction: int)   +1 = clockwise, -1 = counter-clockwise
  on_press()                  SW button pressed
  on_long_press()             SW held for >= long_press_sec

Falls back to stub mode if gpiozero is unavailable or pins are invalid.
"""

import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

try:
    from gpiozero import RotaryEncoder as _GZEncoder, Button as _GZButton
    GPIOZERO_OK = True
except ImportError:
    GPIOZERO_OK = False
    logger.warning("gpiozero not found — encoder runs in stub mode")


class RotaryEncoder:
    """
    Thread-safe rotary encoder wrapper.

    Parameters
    ----------
    pin_clk : int   BCM pin for CLK/A
    pin_dt  : int   BCM pin for DT/B
    pin_sw  : int   BCM pin for push button (0 to disable)
    long_press_sec : float  threshold for long-press detection
    """

    def __init__(self, pin_clk: int, pin_dt: int,
                 pin_sw: int = 0, long_press_sec: float = 0.8):
        self.pin_clk = pin_clk
        self.pin_dt = pin_dt
        self.pin_sw = pin_sw
        self.long_press_sec = long_press_sec

        self._rotate_cb:     list[Callable[[int], None]] = []
        self._press_cb:      list[Callable[[], None]] = []
        self._long_press_cb: list[Callable[[], None]] = []

        self._enc: Optional[object] = None
        self._btn: Optional[object] = None
        self._press_start: float = 0.0
        self.active = False

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def start(self) -> bool:
        """Initialise hardware. Returns True on success."""
        if not GPIOZERO_OK:
            return False
        try:
            self._enc = _GZEncoder(self.pin_clk, self.pin_dt, max_steps=0)
            self._enc.when_rotated_clockwise         = self._on_cw
            self._enc.when_rotated_counter_clockwise = self._on_ccw

            if self.pin_sw:
                self._btn = _GZButton(self.pin_sw, pull_up=True,
                                      bounce_time=0.05)
                self._btn.when_pressed  = self._on_pressed
                self._btn.when_released = self._on_released

            self.active = True
            logger.info("Encoder avviato — CLK=%d DT=%d SW=%d",
                        self.pin_clk, self.pin_dt, self.pin_sw)
            return True
        except Exception as exc:
            logger.error("Encoder init error: %s", exc)
            return False

    def stop(self) -> None:
        self.active = False
        try:
            if self._enc:
                self._enc.close()
            if self._btn:
                self._btn.close()
        except Exception:
            pass
        self._enc = None
        self._btn = None

    # ------------------------------------------------------------------ #
    # Callback registration                                                #
    # ------------------------------------------------------------------ #

    def on_rotate(self, cb: Callable[[int], None]) -> None:
        self._rotate_cb.append(cb)

    def on_press(self, cb: Callable[[], None]) -> None:
        self._press_cb.append(cb)

    def on_long_press(self, cb: Callable[[], None]) -> None:
        self._long_press_cb.append(cb)

    # ------------------------------------------------------------------ #
    # Internal gpiozero callbacks                                         #
    # ------------------------------------------------------------------ #

    def _on_cw(self):
        for cb in self._rotate_cb:
            try:
                cb(+1)
            except Exception:
                pass

    def _on_ccw(self):
        for cb in self._rotate_cb:
            try:
                cb(-1)
            except Exception:
                pass

    def _on_pressed(self):
        self._press_start = time.monotonic()

    def _on_released(self):
        held = time.monotonic() - self._press_start
        if held >= self.long_press_sec:
            for cb in self._long_press_cb:
                try:
                    cb()
                except Exception:
                    pass
        else:
            for cb in self._press_cb:
                try:
                    cb()
                except Exception:
                    pass
