"""
Settings screen — hardware peripheral configuration.

Modular tab structure under ui/settings/:
  tab_display.py  → TabDisplay  (placeholder: font e colori)
  tab_gpio.py     → TabGPIO     (lista pin -> funzione)
  tab_gps.py      → TabGPS      (GPS seriale + fix live)
  tab_sensors.py  → TabSensors  (sensori I2C con label/ruolo)

Internal tabs rendered directly (encoder, buttons, buzzer) are kept in
this file to preserve 100 % backward compatibility.

Layout (480x320):
  +---------------------------------------------+
  |  IMPOSTAZIONI HARDWARE            [SALVA]   |
  +---------------------------------------------+
  | [ENC] [PULS] [BUZ] [GPS] [GPIO] [I2C]      |  <- tab bar
  +---------------------------------------------+
  | (scrollable content for active tab)          |
  +---------------------------------------------+
  | HOME  CHAT  NODI  DEBUG  CONFIG              |
  +---------------------------------------------+

All changes are saved to config/settings.json on tap of "SALVA".
The hardware and I2C managers are restarted hot after saving.
"""

import json
import os
import tkinter as tk
from typing import Optional

from ..base_screen import BaseScreen
from ..icons import ICON_SETTINGS
from hardware.gpio_manager import ACTIONS

from .tab_display import TabDisplay
from .tab_gpio import TabGPIO
from .tab_gps import TabGPS
from .tab_sensors import TabSensors


_SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "settings.json")


class SettingsScreen(BaseScreen):

    def build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self._hw_manager  = None   # injected by App
        self._i2c_manager = None   # injected by App
        self._active_tab  = tk.StringVar(value="encoder")
        self._saved_label_after: Optional[str] = None

        # Pre-build color/font dicts for tab modules
        self._tab_colors = {
            "bg":          self.bg,
            "card":        self.cfg["card_color"],
            "fg":          self.fg,
            "dim":         self.dim,
            "accent":      self.accent,
            "accent_dark": self.cfg["accent_dark_color"],
            "online":      self.online,
            "warn":        self.warn,
            "err":         self.err,
        }
        self._tab_fonts = {
            "large":  self.f_large,
            "normal": self.f_normal,
            "small":  self.f_small,
            "bold":   self.f_bold,
            "mono":   self.f_mono,
        }

        self._build_topbar()
        self._build_tab_bar()
        self._build_content_area()
        nav = self.nav_bar(self, "settings")
        nav.grid(row=3, column=0, sticky="ew")

    # ------------------------------------------------------------------ #
    # Top bar                                                              #
    # ------------------------------------------------------------------ #

    def _build_topbar(self):
        bar = tk.Frame(self, bg=self.topbar)
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)

        tk.Label(bar, text=f"{ICON_SETTINGS} IMPOSTAZIONI HARDWARE",
                 font=self.f_bold, fg=self.fg, bg=self.topbar
                 ).pack(side="left", padx=8, pady=4)

        self._lbl_saved = tk.Label(bar, text="", font=self.f_small,
                                   fg=self.online, bg=self.topbar)
        self._lbl_saved.pack(side="right", padx=4)

        tk.Button(bar, text="SALVA", font=self.f_bold,
                  fg=self.bg, bg=self.accent,
                  activeforeground=self.bg, activebackground=self.fg,
                  relief="flat", bd=0, padx=10, pady=3,
                  command=self._save
                  ).pack(side="right", padx=8)

    # ------------------------------------------------------------------ #
    # Tab bar                                                              #
    # ------------------------------------------------------------------ #

    def _build_tab_bar(self):
        bar = tk.Frame(self, bg=self.cfg["card_color"])
        bar.grid(row=1, column=0, sticky="ew")

        tabs = [("ENC",  "encoder"), ("PULS", "buttons"),
                ("BUZ",  "buzzer"),  ("GPS",  "gps"),
                ("GPIO", "gpio"),    ("I2C",  "i2c")]

        self._tab_btns: dict[str, tk.Button] = {}
        for label, key in tabs:
            btn = tk.Button(
                bar, text=label,
                font=self.f_small,
                relief="flat", bd=0, pady=5,
                command=lambda k=key: self._switch_tab(k),
            )
            btn.pack(side="left", expand=True, fill="x")
            self._tab_btns[key] = btn

        self._update_tab_styles()

    def _switch_tab(self, key: str):
        self._active_tab.set(key)
        self._update_tab_styles()
        self._render_tab(key)

    def _update_tab_styles(self):
        active = self._active_tab.get()
        for key, btn in self._tab_btns.items():
            if key == active:
                btn.configure(fg=self.bg, bg=self.accent)
            else:
                btn.configure(fg=self.dim, bg=self.cfg["card_color"])

    # ------------------------------------------------------------------ #
    # Scrollable content area                                              #
    # ------------------------------------------------------------------ #

    def _build_content_area(self):
        outer = tk.Frame(self, bg=self.bg)
        outer.grid(row=2, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(outer, bg=self.bg, highlightthickness=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")

        sb = tk.Scrollbar(outer, orient="vertical",
                          command=self._canvas.yview,
                          bg=self.cfg["card_color"], troughcolor=self.bg,
                          width=6)
        sb.grid(row=0, column=1, sticky="ns")
        self._canvas.config(yscrollcommand=sb.set)

        self._inner = tk.Frame(self._canvas, bg=self.bg)
        self._win_id = self._canvas.create_window(
            (0, 0), window=self._inner, anchor="nw")

        self._inner.bind("<Configure>",
                         lambda _e: self._canvas.configure(
                             scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
                          lambda e: self._canvas.itemconfig(
                              self._win_id, width=e.width))

        self._render_tab("encoder")

    def _clear_inner(self):
        for w in self._inner.winfo_children():
            w.destroy()

    def on_enter(self):
        self._render_tab(self._active_tab.get())

    def on_scroll(self, direction: int):
        self._canvas.yview_scroll(direction, "units")

    # ------------------------------------------------------------------ #
    # Tab renderers                                                        #
    # ------------------------------------------------------------------ #

    def _render_tab(self, key: str):
        self._clear_inner()
        hw = self.cfg.get("hardware", {})

        if key == "encoder":
            self._render_encoder(hw.get("encoder", {}))
        elif key == "buttons":
            self._render_buttons(hw.get("buttons", []))
        elif key == "buzzer":
            self._render_buzzer(hw.get("buzzer", {}))
        elif key == "gps":
            self._tab_gps = TabGPS(
                self._inner, self._tab_colors, self._tab_fonts,
                self.cfg, hw_manager=self._hw_manager,
                bind_touch_entry=self.bind_touch_entry)
            self._tab_gps.pack(fill="both", expand=True)
        elif key == "gpio":
            self._tab_gpio = TabGPIO(
                self._inner, self._tab_colors, self._tab_fonts, self.cfg)
            self._tab_gpio.pack(fill="both", expand=True)
        elif key == "i2c":
            self._tab_sensors = TabSensors(
                self._inner, self._tab_colors, self._tab_fonts,
                self.cfg, i2c_manager=self._i2c_manager,
                bind_touch_entry=self.bind_touch_entry,
                render_callback=lambda: self._render_tab("i2c"))
            self._tab_sensors.pack(fill="both", expand=True)

    # ── Encoder ──────────────────────────────────────────────────────────

    def _render_encoder(self, enc: dict):
        c = self._make_card(self._inner)
        c.pack(fill="x", padx=8, pady=8)

        self._row_title(c, "Encoder Rotativo")
        self._enabled_var = self._row_toggle(c, "Abilitato",
                                             enc.get("enabled", False))
        self._enc_clk  = self._row_pin(c, "Pin CLK",  enc.get("pin_clk", 17))
        self._enc_dt   = self._row_pin(c, "Pin DT",   enc.get("pin_dt", 18))
        self._enc_sw   = self._row_pin(c, "Pin SW",   enc.get("pin_sw", 27))
        self._row_sep(c)

        actions = enc.get("actions", {})
        self._row_title(c, "Azioni")
        self._enc_cw  = self._row_action(c, "Ruota CW",
                                         actions.get("rotate_cw", "scroll_down"))
        self._enc_ccw = self._row_action(c, "Ruota CCW",
                                         actions.get("rotate_ccw", "scroll_up"))
        self._enc_sw_act = self._row_action(c, "Pressione",
                                            actions.get("press", "select"))
        self._enc_lp  = self._row_action(c, "Pressione lunga",
                                         actions.get("long_press", "navigate_prev"))

        # Status indicator
        if self._hw_manager and self._hw_manager.encoder:
            self._row_status(c, "● Attivo", self.online)
        else:
            self._row_status(c, "○ Non attivo", self.dim)

    # ── Buttons ──────────────────────────────────────────────────────────

    def _render_buttons(self, buttons: list):
        self._btn_rows: list[dict] = []

        for i, btn in enumerate(buttons):
            c = self._make_card(self._inner)
            c.pack(fill="x", padx=8, pady=(8 if i == 0 else 4))

            self._row_title(c, btn.get("label", f"Pulsante {i+1}"))
            row: dict = {}
            row["enabled"] = self._row_toggle(c, "Abilitato",
                                               btn.get("enabled", False))
            row["pin"]     = self._row_pin(c, "Pin GPIO", btn.get("pin", 0))
            row["label"]   = self._row_entry(c, "Etichetta",
                                              btn.get("label", f"Pulsante {i+1}"))
            row["action"]  = self._row_action(c, "Azione",
                                               btn.get("action", "navigate_home"))
            self._btn_rows.append(row)

        # Add button button
        add_btn = tk.Button(
            self._inner, text="+ Aggiungi pulsante",
            font=self.f_small, fg=self.accent,
            bg=self.cfg["card_color"], activeforeground=self.bg,
            activebackground=self.accent,
            relief="flat", bd=0, pady=6,
            command=self._add_button,
        )
        add_btn.pack(fill="x", padx=8, pady=4)

    def _add_button(self):
        hw = self.cfg.get("hardware", {})
        hw.setdefault("buttons", []).append({
            "enabled": False, "pin": 0,
            "label": f"Pulsante {len(hw['buttons'])+1}",
            "action": "navigate_home",
            "pull_up": True, "bounce_time": 0.05,
        })
        self._render_tab("buttons")

    # ── Buzzer ───────────────────────────────────────────────────────────

    def _render_buzzer(self, buz: dict):
        c = self._make_card(self._inner)
        c.pack(fill="x", padx=8, pady=8)

        self._row_title(c, "Buzzer")
        self._buz_enabled = self._row_toggle(c, "Abilitato",
                                              buz.get("enabled", False))
        self._buz_pin     = self._row_pin(c, "Pin GPIO", buz.get("pin", 24))
        self._buz_pwm     = self._row_toggle(c, "Modalita PWM (passivo)",
                                              buz.get("pwm", True))

        self._row_sep(c)
        self._row_title(c, "Notifiche")
        events = buz.get("events", {})
        self._buz_ev_msg  = self._row_toggle(c, "Nuovo messaggio",
                                              events.get("new_message", True))
        self._buz_ev_on   = self._row_toggle(c, "Nodo online",
                                              events.get("node_online", False))
        self._buz_ev_off  = self._row_toggle(c, "Nodo offline",
                                              events.get("node_offline", False))

        # Test button
        self._row_sep(c)
        tk.Button(c, text="TEST SUONO",
                  font=self.f_bold, fg=self.bg, bg=self.accent,
                  activeforeground=self.bg, activebackground=self.fg,
                  relief="flat", bd=0, pady=6,
                  command=self._test_buzzer
                  ).pack(fill="x", padx=12, pady=6)

        if self._hw_manager and self._hw_manager.buzzer:
            self._row_status(c, "● Attivo", self.online)
        else:
            self._row_status(c, "○ Non attivo", self.dim)

    def _test_buzzer(self):
        if self._hw_manager and self._hw_manager.buzzer:
            self._hw_manager.buzzer.test()
        else:
            self._show_saved("(Buzzer non attivo -- abilita e salva prima)")

    # ------------------------------------------------------------------ #
    # Card factory (avoids self.card shadowing issue)                      #
    # ------------------------------------------------------------------ #

    def _make_card(self, parent, **kw) -> tk.Frame:
        """Create a styled card frame. Uses BaseScreen.card() method."""
        return BaseScreen.card(self, parent, **kw)

    # ------------------------------------------------------------------ #
    # Row builders (shared between inline tabs)                            #
    # ------------------------------------------------------------------ #

    def _row_title(self, parent, text: str):
        tk.Label(parent, text=text, font=self.f_bold,
                 fg=self.fg, bg=self.cfg["card_color"], anchor="w"
                 ).pack(fill="x", padx=12, pady=(8, 2))

    def _row_sep(self, parent):
        tk.Frame(parent, bg=self.cfg["accent_dark_color"], height=1
                 ).pack(fill="x", padx=12, pady=4)

    def _row_status(self, parent, text: str, color: str):
        tk.Label(parent, text=text, font=self.f_small,
                 fg=color, bg=self.cfg["card_color"], anchor="w"
                 ).pack(fill="x", padx=12, pady=(2, 8))

    def _row_toggle(self, parent, label: str, initial: bool) -> tk.BooleanVar:
        """Touch-friendly toggle row. Returns BooleanVar."""
        var = tk.BooleanVar(value=initial)
        card_color = self.cfg["card_color"]
        row = tk.Frame(parent, bg=card_color)
        row.pack(fill="x", padx=12, pady=2)
        row.columnconfigure(0, weight=1)

        tk.Label(row, text=label, font=self.f_normal,
                 fg=self.fg, bg=card_color, anchor="w"
                 ).grid(row=0, column=0, sticky="w")

        def _refresh(btn=None):
            if var.get():
                toggle.configure(text="✓  ON", fg=self.bg, bg=self.online)
            else:
                toggle.configure(text="○  OFF", fg=self.dim,
                                  bg=self.cfg["accent_dark_color"])

        toggle = tk.Button(
            row, text="", font=self.f_small,
            relief="flat", bd=0, padx=10, pady=3,
            command=lambda: (var.set(not var.get()), _refresh()),
        )
        toggle.grid(row=0, column=1, padx=(8, 0))
        _refresh()
        return var

    def _row_pin(self, parent, label: str, initial: int) -> tk.StringVar:
        """Single-line PIN entry (numeric, keyboard-enabled)."""
        return self._row_entry(parent, label, str(initial))

    def _row_entry(self, parent, label: str, initial: str) -> tk.StringVar:
        """Single-line text entry with on-screen keyboard."""
        var = tk.StringVar(value=initial)
        card_color = self.cfg["card_color"]
        row = tk.Frame(parent, bg=card_color)
        row.pack(fill="x", padx=12, pady=2)
        row.columnconfigure(0, weight=1)

        tk.Label(row, text=label, font=self.f_normal,
                 fg=self.fg, bg=card_color, anchor="w"
                 ).grid(row=0, column=0, sticky="w")

        entry = tk.Entry(row, textvariable=var, width=14,
                         font=self.f_mono, fg=self.fg,
                         bg=self.bg, insertbackground=self.accent,
                         relief="flat", bd=3)
        entry.grid(row=0, column=1, padx=(8, 0))
        self.bind_touch_entry(entry)
        return var

    def _row_action(self, parent, label: str, initial: str) -> tk.StringVar:
        """Action selector -- tapping cycles through ACTIONS list."""
        var = tk.StringVar(value=initial)
        card_color = self.cfg["card_color"]

        row = tk.Frame(parent, bg=card_color)
        row.pack(fill="x", padx=12, pady=2)
        row.columnconfigure(0, weight=1)

        tk.Label(row, text=label, font=self.f_normal,
                 fg=self.fg, bg=card_color, anchor="w"
                 ).grid(row=0, column=0, sticky="w")

        def _cycle():
            idx = ACTIONS.index(var.get()) if var.get() in ACTIONS else 0
            var.set(ACTIONS[(idx + 1) % len(ACTIONS)])
            btn.configure(text=var.get())

        btn = tk.Button(row, text=var.get(), font=self.f_small,
                        fg=self.accent,
                        bg=self.cfg["accent_dark_color"],
                        activeforeground=self.bg,
                        activebackground=self.accent,
                        relief="flat", bd=0, padx=8, pady=3,
                        command=_cycle)
        btn.grid(row=0, column=1, padx=(8, 0))
        return var

    # ------------------------------------------------------------------ #
    # Save                                                                 #
    # ------------------------------------------------------------------ #

    def _save(self):
        """Collect all widget values, merge into cfg, persist to disk,
        hot-restart hardware manager."""
        hw = self.cfg.setdefault("hardware", {})
        active = self._active_tab.get()

        try:
            if active == "encoder" and hasattr(self, "_enc_clk"):
                hw["encoder"] = {
                    "enabled":       self._enabled_var.get(),
                    "pin_clk":       int(self._enc_clk.get()  or 0),
                    "pin_dt":        int(self._enc_dt.get()   or 0),
                    "pin_sw":        int(self._enc_sw.get()   or 0),
                    "long_press_sec": 0.8,
                    "actions": {
                        "rotate_cw":  self._enc_cw.get(),
                        "rotate_ccw": self._enc_ccw.get(),
                        "press":      self._enc_sw_act.get(),
                        "long_press": self._enc_lp.get(),
                    },
                }

            elif active == "buttons" and hasattr(self, "_btn_rows"):
                saved = hw.get("buttons", [])
                for i, row in enumerate(self._btn_rows):
                    if i < len(saved):
                        saved[i]["enabled"] = row["enabled"].get()
                        saved[i]["pin"]     = int(row["pin"].get() or 0)
                        saved[i]["label"]   = row["label"].get()
                        saved[i]["action"]  = row["action"].get()
                hw["buttons"] = saved

            elif active == "buzzer" and hasattr(self, "_buz_pin"):
                hw["buzzer"] = {
                    "enabled": self._buz_enabled.get(),
                    "pin":     int(self._buz_pin.get() or 0),
                    "pwm":     self._buz_pwm.get(),
                    "events": {
                        "new_message":  self._buz_ev_msg.get(),
                        "node_online":  self._buz_ev_on.get(),
                        "node_offline": self._buz_ev_off.get(),
                    },
                }

            elif active == "gps" and hasattr(self, "_tab_gps"):
                hw["gps"] = self._tab_gps.get_gps_config()

            elif active == "gpio" and hasattr(self, "_tab_gpio"):
                errors = self._tab_gpio.validate()
                if errors:
                    self._show_saved(f"Errore: {errors[0]}")
                    return
                gpio_settings = self._tab_gpio.get_config().to_settings_dict()
                # Merge GPIO pin assignments into hardware config
                # (only updates pin numbers, does not overwrite other fields)
                for section in ("encoder", "buzzer", "gps"):
                    if gpio_settings.get(section):
                        hw.setdefault(section, {}).update(gpio_settings[section])
                if gpio_settings.get("buttons"):
                    # Preserve existing button configs, update pins
                    existing = hw.get("buttons", [])
                    for gb in gpio_settings["buttons"]:
                        # Check if pin already assigned to an existing button
                        found = False
                        for eb in existing:
                            if eb.get("pin") == gb["pin"]:
                                found = True
                                break
                        if not found:
                            existing.append({
                                "enabled": False, "pin": gb["pin"],
                                "label": f"Pulsante {len(existing)+1}",
                                "action": "navigate_home",
                                "pull_up": True, "bounce_time": 0.05,
                            })
                    hw["buttons"] = existing

            elif active == "i2c" and hasattr(self, "_tab_sensors"):
                i2c = self.cfg.setdefault("i2c", {})
                bus_cfg = self._tab_sensors.get_bus_config()
                i2c["bus"] = bus_cfg["bus"]
                i2c["poll_interval_ms"] = bus_cfg["poll_interval_ms"]
                i2c["sensors"] = self._tab_sensors.get_sensor_configs()

        except ValueError as exc:
            self._show_saved(f"Errore: {exc}")
            return

        # Write to disk
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.cfg, f, indent=4, ensure_ascii=False)

        # Hot-restart hardware and I2C managers
        if self._hw_manager:
            self._hw_manager.cfg = self.cfg
            self._hw_manager.restart()
        if self._i2c_manager:
            self._i2c_manager.cfg = self.cfg
            self._i2c_manager.restart()

        self._show_saved("Salvato")
        self._render_tab(active)

    def _show_saved(self, msg: str):
        self._lbl_saved.config(text=msg)
        if self._saved_label_after:
            self.after_cancel(self._saved_label_after)
        self._saved_label_after = self.after(
            3000, lambda: self._lbl_saved.config(text=""))

    # ------------------------------------------------------------------ #
    # Manager injection                                                    #
    # ------------------------------------------------------------------ #

    def inject_managers(self, hw_manager, i2c_manager):
        """Inject hardware and I2C managers (called by App)."""
        self._hw_manager = hw_manager
        self._i2c_manager = i2c_manager
