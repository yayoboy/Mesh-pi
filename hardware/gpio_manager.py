"""
hardware/gpio_manager.py — Hardware I/O orchestrator.

Manages all optional GPIO peripherals:
  - Rotary encoder  (navigation)
  - Push buttons    (configurable actions)
  - Buzzer          (notifications)
  - GPS module      (serial NMEA)

All peripherals are optional. If the library is absent or the pin is
invalid, that peripheral is silently skipped.

Inter-module communication
--------------------------
The manager translates raw hardware events into named *actions* and
dispatches them via action_callback(action_name).  The App registers
this callback and routes it to the active screen or performs navigation.

Action names
------------
  scroll_up / scroll_down
  navigate_home / navigate_chat / navigate_nodes
  navigate_debug / navigate_settings / navigate_prev / navigate_next
  select
  buzzer_test
"""

import logging
from typing import Callable, Optional

from .encoder import RotaryEncoder
from .buzzer import BuzzerController
from .gps_reader import GpsReader, GpsFix

logger = logging.getLogger(__name__)

# Available actions for encoder / buttons
ACTIONS = [
    "scroll_up",
    "scroll_down",
    "navigate_prev",
    "navigate_next",
    "navigate_home",
    "navigate_chat",
    "navigate_nodes",
    "navigate_debug",
    "navigate_settings",
    "select",
    "buzzer_test",
]

try:
    from gpiozero import Button as _GZButton
    GPIOZERO_OK = True
except ImportError:
    GPIOZERO_OK = False


class GPIOManager:
    """
    Central hardware manager.

    Parameters
    ----------
    cfg : dict   Full settings dict (hardware section read via cfg["hardware"])
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._hw = cfg.get("hardware", {})

        self._action_cb: Optional[Callable[[str], None]] = None
        self._gps_fix_cbs: list[Callable[[GpsFix], None]] = []
        self._gps_lost_cbs: list[Callable[[], None]] = []

        self.encoder: Optional[RotaryEncoder] = None
        self.buzzer:  Optional[BuzzerController] = None
        self.gps:     Optional[GpsReader] = None

        self._buttons: list[object] = []   # gpiozero Button instances

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Initialise all configured and enabled peripherals."""
        self._init_encoder()
        self._init_buttons()
        self._init_buzzer()
        self._init_gps()

    def stop(self) -> None:
        if self.encoder:
            self.encoder.stop()
        if self.buzzer:
            self.buzzer.stop()
        if self.gps:
            self.gps.stop()
        for btn in self._buttons:
            try:
                btn.close()
            except Exception:
                pass

    def restart(self) -> None:
        """Hot-reload after settings change."""
        self.stop()
        self._hw = self.cfg.get("hardware", {})
        self.encoder = None
        self.buzzer = None
        self.gps = None
        self._buttons = []
        self.start()

    # ------------------------------------------------------------------ #
    # Callback registration                                                #
    # ------------------------------------------------------------------ #

    def on_action(self, cb: Callable[[str], None]) -> None:
        """Register callback for hardware action events."""
        self._action_cb = cb

    def on_gps_fix(self, cb: Callable[[GpsFix], None]) -> None:
        self._gps_fix_cbs.append(cb)

    def on_gps_lost(self, cb: Callable[[], None]) -> None:
        self._gps_lost_cbs.append(cb)

    # ------------------------------------------------------------------ #
    # Buzzer shortcuts (called by MeshtasticClient callbacks)             #
    # ------------------------------------------------------------------ #

    def buzz(self, event: str) -> None:
        """Trigger a buzzer notification event if buzzer is active."""
        if self.buzzer:
            self.buzzer.notify(event)

    # ------------------------------------------------------------------ #
    # Encoder init                                                         #
    # ------------------------------------------------------------------ #

    def _init_encoder(self) -> None:
        enc_cfg = self._hw.get("encoder", {})
        if not enc_cfg.get("enabled", False):
            return

        pin_clk = enc_cfg.get("pin_clk", 0)
        pin_dt  = enc_cfg.get("pin_dt",  0)
        pin_sw  = enc_cfg.get("pin_sw",  0)

        if not pin_clk or not pin_dt:
            logger.warning("Encoder: pin_clk/pin_dt non configurati")
            return

        enc = RotaryEncoder(pin_clk, pin_dt, pin_sw,
                            long_press_sec=enc_cfg.get("long_press_sec", 0.8))

        actions = enc_cfg.get("actions", {})
        cw_action  = actions.get("rotate_cw",  "scroll_down")
        ccw_action = actions.get("rotate_ccw", "scroll_up")
        sw_action  = actions.get("press",       "select")
        lp_action  = actions.get("long_press",  "navigate_prev")

        enc.on_rotate(lambda d: self._dispatch(cw_action if d > 0 else ccw_action))
        enc.on_press(lambda: self._dispatch(sw_action))
        enc.on_long_press(lambda: self._dispatch(lp_action))

        if enc.start():
            self.encoder = enc

    # ------------------------------------------------------------------ #
    # Buttons init                                                         #
    # ------------------------------------------------------------------ #

    def _init_buttons(self) -> None:
        if not GPIOZERO_OK:
            return

        for btn_cfg in self._hw.get("buttons", []):
            if not btn_cfg.get("enabled", False):
                continue
            pin    = btn_cfg.get("pin", 0)
            action = btn_cfg.get("action", "")
            label  = btn_cfg.get("label", f"BTN{pin}")
            if not pin or not action:
                continue
            try:
                btn = _GZButton(pin,
                                pull_up=btn_cfg.get("pull_up", True),
                                bounce_time=btn_cfg.get("bounce_time", 0.05))
                btn.when_pressed = lambda a=action: self._dispatch(a)
                self._buttons.append(btn)
                logger.info("Pulsante '%s' pin=%d azione=%s", label, pin, action)
            except Exception as exc:
                logger.error("Pulsante pin=%d errore: %s", pin, exc)

    # ------------------------------------------------------------------ #
    # Buzzer init                                                          #
    # ------------------------------------------------------------------ #

    def _init_buzzer(self) -> None:
        buz_cfg = self._hw.get("buzzer", {})
        if not buz_cfg.get("enabled", False):
            return

        pin = buz_cfg.get("pin", 0)
        if not pin:
            logger.warning("Buzzer: pin non configurato")
            return

        buz = BuzzerController(
            pin=pin,
            pwm_mode=buz_cfg.get("pwm", True),
            events=buz_cfg.get("events", {}),
        )
        if buz.start():
            self.buzzer = buz

    # ------------------------------------------------------------------ #
    # GPS init                                                             #
    # ------------------------------------------------------------------ #

    def _init_gps(self) -> None:
        gps_cfg = self._hw.get("gps", {})
        if not gps_cfg.get("enabled", False):
            return

        port = gps_cfg.get("port", "/dev/ttyAMA0")
        baud = gps_cfg.get("baud", 9600)

        gps = GpsReader(port=port, baud=baud)
        gps.on_fix(self._on_gps_fix)
        gps.on_fix_lost(self._on_gps_lost)

        if gps.start():
            self.gps = gps

    # ------------------------------------------------------------------ #
    # Internal dispatching                                                 #
    # ------------------------------------------------------------------ #

    def _dispatch(self, action: str) -> None:
        if self._action_cb and action:
            try:
                self._action_cb(action)
            except Exception as exc:
                logger.error("Action dispatch error: %s", exc)

    def _on_gps_fix(self, fix: GpsFix) -> None:
        for cb in self._gps_fix_cbs:
            try:
                cb(fix)
            except Exception:
                pass

    def _on_gps_lost(self) -> None:
        for cb in self._gps_lost_cbs:
            try:
                cb()
            except Exception:
                pass
