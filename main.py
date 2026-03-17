#!/usr/bin/env python3
"""
main.py — Meshtastic Terminal UI entry point.

Initialises:
  1. Settings        (config/settings.json)
  2. Radio client    (MeshtasticClient)
  3. Hardware manager (GPIOManager — optional peripherals)
  4. Tkinter root window
  5. Screen manager  (stacked frames, single navigator)
  6. Main loop

Thread model:
  Thread-1  meshtastic-reader   → serial I/O, fires callbacks
  Thread-2  demo-loop (no HW)   → generates demo traffic
  Thread-3  gps-reader          → NMEA serial, fires callbacks
  Thread-4  buzzer-worker       → fire-and-forget tone patterns
  Main      Tkinter + .after()  → all GUI updates

All cross-thread GUI updates go through widget.after(0, fn).
"""

import json
import logging
import os
import sys
import tkinter as tk

# ── local imports ──────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from radio.meshtastic_client import MeshtasticClient
from hardware.gpio_manager import GPIOManager
from ui.home_screen import HomeScreen
from ui.chat_screen import ChatScreen
from ui.nodes_screen import NodesScreen
from ui.debug_screen import DebugScreen
from ui.settings_screen import SettingsScreen
from ui.keyboard import OnScreenKeyboard

# ── logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")

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
                 hw: GPIOManager):
        super().__init__()
        self.cfg = cfg
        self.client = client
        self.hw = hw

        self._configure_window()
        self._build_screens()
        self._wire_hardware()
        self.navigate("home")

        self.protocol("WM_DELETE_WINDOW", self._on_quit)

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

        # Inject hardware manager into settings screen
        self._screens["settings"]._hw_manager = self.hw

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
    # Quit                                                                 #
    # ------------------------------------------------------------------ #

    def _on_quit(self):
        logger.info("shutting down")
        self.hw.stop()
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

    app = App(cfg, client, hw)

    try:
        app.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        hw.stop()
        client.stop()


if __name__ == "__main__":
    main()
