"""
hardware/buzzer.py — Buzzer (active or passive PWM) via gpiozero.

Supports two modes
  active  → GPIO on/off (active buzzer, no frequency control)
  passive → PWM tone via TonalBuzzer (passive buzzer)

Notification events configurable:
  new_message  / node_online / node_offline

Falls back to stub mode silently if gpiozero is unavailable.
"""

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from gpiozero import TonalBuzzer, Buzzer as SimpleBuzzer
    from gpiozero.tones import Tone
    GPIOZERO_OK = True
except ImportError:
    GPIOZERO_OK = False
    logger.warning("gpiozero not found — buzzer runs in stub mode")


# Default tone patterns (frequency Hz, duration s)
_PATTERNS = {
    "new_message":  [(880, 0.08), (0, 0.04), (880, 0.08)],
    "node_online":  [(660, 0.12), (0, 0.04), (880, 0.12)],
    "node_offline": [(880, 0.12), (0, 0.04), (660, 0.12)],
    "test":         [(440, 0.1), (0, 0.05), (880, 0.1), (0, 0.05), (440, 0.1)],
}


class BuzzerController:
    """
    Thread-safe buzzer controller.

    Parameters
    ----------
    pin      : BCM GPIO pin
    pwm_mode : True → TonalBuzzer (passive), False → SimpleBuzzer (active)
    events   : dict of event_name → bool (whether to buzz on that event)
    """

    def __init__(self, pin: int, pwm_mode: bool = True,
                 events: Optional[dict] = None):
        self.pin = pin
        self.pwm_mode = pwm_mode
        self.events = events or {
            "new_message": True,
            "node_online":  False,
            "node_offline": False,
        }

        self._dev: Optional[object] = None
        self._lock = threading.Lock()
        self._worker: Optional[threading.Thread] = None
        self.active = False

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def start(self) -> bool:
        if not GPIOZERO_OK:
            return False
        try:
            if self.pwm_mode:
                self._dev = TonalBuzzer(self.pin)
            else:
                self._dev = SimpleBuzzer(self.pin)
            self.active = True
            logger.info("Buzzer avviato — pin=%d pwm=%s", self.pin, self.pwm_mode)
            return True
        except Exception as exc:
            logger.error("Buzzer init error: %s", exc)
            return False

    def stop(self) -> None:
        self.active = False
        self._silence()
        try:
            if self._dev:
                self._dev.close()
        except Exception:
            pass
        self._dev = None

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def notify(self, event: str) -> None:
        """Play notification pattern for event if enabled."""
        if not self.active:
            return
        if not self.events.get(event, False):
            return
        pattern = _PATTERNS.get(event)
        if pattern:
            self._play_async(pattern)

    def test(self) -> None:
        """Play test pattern regardless of event settings."""
        if not self.active:
            logger.info("Buzzer stub — test suono (nessun HW)")
            return
        self._play_async(_PATTERNS["test"])

    def silence(self) -> None:
        self._silence()

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _play_async(self, pattern: list) -> None:
        """Fire-and-forget pattern playback in a daemon thread."""
        if self._worker and self._worker.is_alive():
            return   # skip if already playing
        self._worker = threading.Thread(
            target=self._play, args=(pattern,), daemon=True,
            name="buzzer-worker")
        self._worker.start()

    def _play(self, pattern: list) -> None:
        with self._lock:
            for freq, dur in pattern:
                if not self.active:
                    break
                self._set_freq(freq)
                time.sleep(dur)
            self._silence()

    def _set_freq(self, freq: int) -> None:
        if not self._dev:
            return
        try:
            if self.pwm_mode:
                if freq:
                    self._dev.play(Tone(frequency=freq))
                else:
                    self._dev.stop()
            else:
                if freq:
                    self._dev.on()
                else:
                    self._dev.off()
        except Exception as exc:
            logger.debug("Buzzer freq error: %s", exc)

    def _silence(self) -> None:
        self._set_freq(0)
