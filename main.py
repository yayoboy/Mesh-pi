#!/usr/bin/env python3
"""
main.py — Meshtastic Terminal UI entry point.

Initialises:
  1. Settings  (config/settings.json)
  2. Radio client  (MeshtasticClient)
  3. Tkinter root window
  4. Screen manager (stacked frames, single navigator)
  5. Main loop

Thread model (three layers as designed):
  Thread-1  meshtastic-reader   → serial I/O, fires callbacks
  Thread-2  demo-loop (if no HW) → generates demo traffic
  Thread-3  Tkinter main thread  → GUI + .after() scheduling

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
from ui.home_screen import HomeScreen
from ui.chat_screen import ChatScreen
from ui.nodes_screen import NodesScreen
from ui.debug_screen import DebugScreen

# ── logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


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
    """

    SCREENS = {
        "home":  HomeScreen,
        "chat":  ChatScreen,
        "nodes": NodesScreen,
        "debug": DebugScreen,
    }

    def __init__(self, cfg: dict, client: MeshtasticClient):
        super().__init__()
        self.cfg = cfg
        self.client = client

        self._configure_window()
        self._build_screens()
        self.navigate("home")

        self.protocol("WM_DELETE_WINDOW", self._on_quit)

    def _configure_window(self):
        self.title("Meshtastic Terminal")
        self.configure(bg=self.cfg["bg_color"])

        w = self.cfg["display_width"]
        h = self.cfg["display_height"]
        self.geometry(f"{w}x{h}")
        self.resizable(False, False)

        # Fullscreen on the actual Pi display; comment out for dev desktop
        if os.environ.get("MESHTASTIC_FULLSCREEN", "0") == "1":
            self.attributes("-fullscreen", True)

        # Hide mouse cursor on touchscreen
        if os.environ.get("MESHTASTIC_HIDE_CURSOR", "0") == "1":
            self.config(cursor="none")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

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
        logger.info("navigated → %s", name)

    def _on_quit(self):
        logger.info("shutting down")
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

    app = App(cfg, client)

    try:
        app.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        client.stop()


if __name__ == "__main__":
    main()
