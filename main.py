#!/usr/bin/env python3
"""
main.py — Meshtastic Terminal UI entry point.

Initialises:
  1. Settings         (config/settings.json)
  2. Radio client     (MeshtasticClient)
  3. Hardware manager (GPIOManager — GPIO peripherals)
  4. I2C manager      (I2CManager — I2C telemetry sensors)
  5. Tkinter root window
  6. Screen manager   (stacked frames, single navigator)
  7. Main loop

Thread model:
  Thread-1  meshtastic-reader   → serial I/O, fires callbacks
  Thread-2  demo-loop (no HW)   → generates demo traffic
  Thread-3  gps-reader          → NMEA serial, fires callbacks
  Thread-4  buzzer-worker       → fire-and-forget tone patterns
  Thread-5  i2c-poll            → I2C sensor polling
  Main      Tkinter + .after()  → all GUI updates

All cross-thread GUI updates go through widget.after(0, fn).
"""

import json
import logging
import logging.handlers
import os
import sys
import tkinter as tk

# ── local imports ──────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from radio.meshtastic_client import MeshtasticClient
from hardware.gpio_manager import GPIOManager
from hardware.i2c_manager import I2CManager
from ui.log_buffer import ui_log_handler
from ui.home_screen import HomeScreen
from ui.chat_screen import ChatScreen
from ui.nodes_screen import NodesScreen
from ui.debug_screen import DebugScreen
from ui.settings import SettingsScreen
from ui.keyboard import OnScreenKeyboard
from data.telemetry_store import TelemetryStore, TelemetrySample

# ── logging ────────────────────────────────────────────────────────────────
_LOG_FORMAT  = "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s"
_LOG_DATEFMT = "%H:%M:%S"

logging.basicConfig(
    level=logging.DEBUG,
    format=_LOG_FORMAT,
    datefmt=_LOG_DATEFMT,
)

# In-memory buffer (shown in the debug screen)
ui_log_handler.setLevel(logging.DEBUG)
logging.getLogger().addHandler(ui_log_handler)

# Rotating file log in /tmp (survives the session, readable via SSH)
# Two 256 KB files → max 512 KB on the SD card / tmpfs
_file_handler = logging.handlers.RotatingFileHandler(
    "/tmp/meshtastic-ui.log",
    maxBytes=256 * 1024,
    backupCount=2,
    encoding="utf-8",
)
_file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _LOG_DATEFMT))
_file_handler.setLevel(logging.DEBUG)
logging.getLogger().addHandler(_file_handler)

logger = logging.getLogger("main")
logger.info("Avvio Meshtastic UI — log su /tmp/meshtastic-ui.log")

_SCREEN_ORDER = ["home", "chat", "nodes", "debug", "settings"]


# ── helpers ────────────────────────────────────────────────────────────────

def load_settings(path: str = None) -> dict:
    path = path or os.path.join(ROOT, "config", "settings.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── App ────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    """
    Root window and screen manager.

    Screens are created once and stacked (grid/raise).
    navigate(name) raises the appropriate frame without destroying it.

    Hardware action dispatch
    -----------------------
    GPIOManager calls dispatch_action(name) from background threads.
    The method schedules the actual work on the Tkinter thread via .after(0).
    """

    SCREENS = {
        "home":     HomeScreen,
        "chat":     ChatScreen,
        "nodes":    NodesScreen,
        "debug":    DebugScreen,
        "settings": SettingsScreen,
    }

    def __init__(self, cfg: dict, client: MeshtasticClient,
                 hw: GPIOManager, i2c: I2CManager):
        super().__init__()
        self.cfg = cfg
        self.client = client
        self.hw = hw
        self.i2c = i2c

        # Telemetry store (persistent history)
        self.telemetry_store = TelemetryStore()
        self.telemetry_store.load()

        self._unread_messages = 0

        self._configure_window()
        self._build_screens()
        self._wire_hardware()
        self.navigate("home")

        self.protocol("WM_DELETE_WINDOW", self._on_quit)

        # Start periodic telemetry sampling (every 30s)
        self.after(30000, self._sample_telemetry)

    # ------------------------------------------------------------------ #
    # Window setup                                                         #
    # ------------------------------------------------------------------ #

    def _configure_window(self):
        self.title("Meshtastic Terminal")
        self.configure(bg=self.cfg["bg_color"])

        w = self.cfg["display_width"]
        h = self.cfg["display_height"]
        self.geometry(f"{w}x{h}")
        self.resizable(False, False)

        if os.environ.get("MESHTASTIC_FULLSCREEN", "0") == "1":
            self.attributes("-fullscreen", True)

        if os.environ.get("MESHTASTIC_HIDE_CURSOR", "0") == "1":
            self.config(cursor="none")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    # ------------------------------------------------------------------ #
    # Screen manager                                                       #
    # ------------------------------------------------------------------ #

    def _build_screens(self):
        self._screens: dict[str, tk.Frame] = {}
        for name, ScreenClass in self.SCREENS.items():
            screen = ScreenClass(
                parent=self,
                cfg=self.cfg,
                client=self.client,
                navigate=self.navigate,
            )
            screen.grid(row=0, column=0, sticky="nsew")
            self._screens[name] = screen

        # Shared on-screen keyboard
        self._keyboard = OnScreenKeyboard(self, self.cfg)
        for screen in self._screens.values():
            screen.keyboard = self._keyboard

        # Inject hardware and I2C managers into settings screen
        self._screens["settings"]._hw_manager  = self.hw
        self._screens["settings"]._i2c_manager = self.i2c

        # Inject I2C manager into home screen for the sensor strip
        self._screens["home"]._i2c_manager = self.i2c

        # Inject telemetry store into debug screen for the telemetry tab
        self._screens["debug"].set_telemetry_store(self.telemetry_store)

        self._current: str = ""

    def navigate(self, name: str):
        if name not in self._screens:
            logger.warning("unknown screen: %s", name)
            return
        if self._current and self._current in self._screens:
            self._screens[self._current].on_leave()

        screen = self._screens[name]
        screen.tkraise()
        screen.on_enter()
        self._current = name
        self._on_screen_shown(name)
        logger.debug("navigated → %s", name)

    # ------------------------------------------------------------------ #
    # Hardware wiring                                                      #
    # ------------------------------------------------------------------ #

    def _wire_hardware(self):
        """Connect hardware action dispatcher and buzzer to radio events."""
        # Action dispatcher: called from GPIO threads, re-routed to main thread
        self.hw.on_action(self.dispatch_action)

        # Buzzer notifications from Meshtastic callbacks (already background)
        self.client.on_message(
            lambda msg: self.hw.buzz("new_message"))
        self.client.on_node_update(
            lambda node: self.hw.buzz("node_online"))

        # Unread message badge tracking
        self.client.on_message(self._on_new_message)

    # ------------------------------------------------------------------ #
    # Unread message badges                                                #
    # ------------------------------------------------------------------ #

    def _on_new_message(self, msg):
        """Increment unread badge when a message arrives while not on chat."""
        def _update():
            if self._current != "chat":
                self._unread_messages += 1
                self._update_all_badges()
        self.after(0, _update)

    def _update_all_badges(self):
        badges = {"chat": self._unread_messages}
        for screen in self._screens.values():
            if hasattr(screen, "update_nav_badges"):
                screen.update_nav_badges(badges)

    def _on_screen_shown(self, name):
        """Reset unread count when user navigates to chat."""
        if name == "chat":
            self._unread_messages = 0
            self._update_all_badges()

    def dispatch_action(self, action: str):
        """Dispatch a hardware action to the main Tkinter thread."""
        self.after(0, self._handle_action, action)

    def _handle_action(self, action: str):
        """Execute hardware action on the Tkinter thread."""
        # Navigation actions
        if action.startswith("navigate_"):
            target = action[len("navigate_"):]
            if target == "prev":
                self._navigate_relative(-1)
            elif target == "next":
                self._navigate_relative(+1)
            elif target in self._screens:
                self.navigate(target)
            return

        # Scroll actions → forward to active screen
        if action in ("scroll_up", "scroll_down"):
            screen = self._screens.get(self._current)
            if screen and hasattr(screen, "on_scroll"):
                screen.on_scroll(-1 if action == "scroll_up" else +1)
            return

        # Select → synthesise a Return key event on focused widget
        if action == "select":
            focused = self.focus_get()
            if focused:
                focused.event_generate("<Return>")
            return

        # Buzzer test
        if action == "buzzer_test":
            self.hw.buzz("test")
            return

        logger.debug("unhandled action: %s", action)

    def _navigate_relative(self, delta: int):
        if self._current in _SCREEN_ORDER:
            idx = _SCREEN_ORDER.index(self._current)
            new = _SCREEN_ORDER[(idx + delta) % len(_SCREEN_ORDER)]
            self.navigate(new)

    # ------------------------------------------------------------------ #
    # Telemetry sampling                                                   #
    # ------------------------------------------------------------------ #

    def _sample_telemetry(self):
        """Sample radio stats + I2C sensors and store in telemetry history."""
        sensors: dict[str, float] = {}

        # I2C environmental sensors
        for r in self.i2c.get_env_readings():
            sensors[f"{r.label} (\u00b0C)"] = r.temperature
            if r.humidity is not None:
                sensors[f"{r.label} (%RH)"] = r.humidity
            if r.pressure is not None:
                sensors[f"{r.label} (hPa)"] = r.pressure

        # I2C power sensors
        for r in self.i2c.get_power_readings():
            sensors[f"{r.label} (V)"] = r.bus_voltage
            sensors[f"{r.label} (mA)"] = r.current_ma

        sample = TelemetrySample(
            rssi=self.client.stats.rssi,
            snr=self.client.stats.snr,
            sensors=sensors,
        )
        self.telemetry_store.add(sample)
        self.telemetry_store.save()

        # Reschedule
        self.after(30000, self._sample_telemetry)

    # ------------------------------------------------------------------ #
    # Quit                                                                 #
    # ------------------------------------------------------------------ #

    def _on_quit(self):
        logger.info("shutting down")
        self.hw.stop()
        self.i2c.stop()
        self.client.stop()
        self.destroy()


# ── entry point ────────────────────────────────────────────────────────────

def main():
    cfg = load_settings()

    client = MeshtasticClient(
        port=cfg["serial_port"],
        baud=cfg["serial_baud"],
    )
    client.start()

    hw = GPIOManager(cfg)
    hw.start()

    i2c = I2CManager(cfg)
    i2c.start()

    app = App(cfg, client, hw, i2c)

    try:
        app.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        hw.stop()
        i2c.stop()
        client.stop()


if __name__ == "__main__":
    main()
