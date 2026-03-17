"""
Tab Sensors — lista scrollabile sensori I2C con label/ruolo personalizzabili.

Usa SensorConfig e VALID_ROLES da hardware.i2c_manager.
"""

import tkinter as tk

from hardware.i2c_manager import SensorConfig, VALID_ROLES


class TabSensors(tk.Frame):
    """Configurazione sensori I2C: enable, label, tipo, indirizzo, ruolo."""

    def __init__(self, parent, colors: dict, fonts: dict, cfg: dict,
                 i2c_manager=None, bind_touch_entry=None,
                 render_callback=None, **kw):
        super().__init__(parent, bg=colors["bg"], **kw)
        self.colors = colors
        self.fonts = fonts
        self.cfg = cfg
        self._i2c_manager = i2c_manager
        self._bind_touch_entry = bind_touch_entry
        self._render_callback = render_callback  # called to re-render tab

        self._i2c_rows: list[dict] = []

        self._build(cfg.get("i2c", {}))

    # ------------------------------------------------------------------ #
    # Build                                                                #
    # ------------------------------------------------------------------ #

    def _build(self, i2c: dict):
        bg = self.colors["bg"]
        card = self.colors["card"]
        fg = self.colors["fg"]
        accent = self.colors["accent"]
        accent_dark = self.colors["accent_dark"]

        # Global bus settings card
        hdr = tk.Frame(self, bg=card, highlightthickness=1,
                       highlightbackground=accent_dark)
        hdr.pack(fill="x", padx=8, pady=8)
        self._row_title(hdr, "Bus I2C")
        self.i2c_bus = self._row_entry(hdr, "Bus numero",
                                       str(i2c.get("bus", 1)))
        self.i2c_interval = self._row_entry(hdr, "Intervallo (ms)",
                                            str(i2c.get("poll_interval_ms", 2000)))

        # One card per sensor
        for i, sensor_cfg in enumerate(i2c.get("sensors", [])):
            self._render_sensor_card(sensor_cfg, i)

        # "Add sensor" buttons
        add_frame = tk.Frame(self, bg=bg)
        add_frame.pack(fill="x", padx=8, pady=4)
        for stype, label_text in [("ina219", "+ INA219"),
                                   ("bme280", "+ BME280"),
                                   ("sht30",  "+ SHT30")]:
            tk.Button(
                add_frame, text=label_text,
                font=self.fonts["small"], fg=accent,
                bg=card, activeforeground=bg,
                activebackground=accent,
                relief="flat", bd=0, padx=10, pady=5,
                command=lambda t=stype: self._add_sensor(t),
            ).pack(side="left", padx=(0, 6))

        # Live readings (if I2C manager available)
        if self._i2c_manager and self._i2c_manager.has_sensors():
            self._render_live()

    def _render_sensor_card(self, sensor_cfg: dict, idx: int):
        stype = sensor_cfg.get("type", "sensor").upper()
        card = self.colors["card"]
        accent_dark = self.colors["accent_dark"]
        accent = self.colors["accent"]
        fg = self.colors["fg"]

        c = tk.Frame(self, bg=card, highlightthickness=1,
                     highlightbackground=accent_dark)
        c.pack(fill="x", padx=8, pady=(0, 4))

        self._row_title(c, f"{stype}  --  {sensor_cfg.get('label', '')}")
        row: dict = {"idx": idx}
        row["enabled"] = self._row_toggle(c, "Abilitato",
                                          sensor_cfg.get("enabled", False))
        row["label"] = self._row_entry(c, "Etichetta",
                                       sensor_cfg.get("label", stype))
        row["type_label"] = tk.Label(
            c, text=f"Tipo: {sensor_cfg.get('type', '')}",
            font=self.fonts["small"], fg=self.colors["dim"],
            bg=card, anchor="w")
        row["type_label"].pack(fill="x", padx=12, pady=1)

        row["address"] = self._row_entry(c, "Indirizzo I2C",
                                         sensor_cfg.get("address", "0x40"))

        # Role selector
        role_row = tk.Frame(c, bg=card)
        role_row.pack(fill="x", padx=12, pady=2)
        role_row.columnconfigure(0, weight=1)
        tk.Label(role_row, text="Ruolo", font=self.fonts["normal"],
                 fg=fg, bg=card, anchor="w"
                 ).grid(row=0, column=0, sticky="w")
        role_var = tk.StringVar(value=sensor_cfg.get("role", "custom"))
        om = tk.OptionMenu(role_row, role_var, *VALID_ROLES)
        om.configure(font=self.fonts["small"], fg=accent, bg=card,
                     activeforeground=self.colors["bg"],
                     activebackground=accent,
                     highlightthickness=0, relief="flat", bd=0)
        om["menu"].configure(font=self.fonts["small"], fg=fg, bg=card,
                             activeforeground=self.colors["bg"],
                             activebackground=accent)
        om.grid(row=0, column=1, padx=(8, 0))
        row["role"] = role_var

        # INA219-specific fields
        if sensor_cfg.get("type", "") == "ina219":
            row["shunt_ohms"] = self._row_entry(
                c, "Shunt (ohm)", str(sensor_cfg.get("shunt_ohms", 0.1)))
            row["max_expected_amps"] = self._row_entry(
                c, "Max corrente (A)", str(sensor_cfg.get("max_expected_amps", 2.0)))
        else:
            row["shunt_ohms"] = None
            row["max_expected_amps"] = None

        row["type"] = sensor_cfg.get("type", "")
        self._i2c_rows.append(row)

    def _render_live(self):
        card = self.colors["card"]
        accent_dark = self.colors["accent_dark"]

        live = tk.Frame(self, bg=card, highlightthickness=1,
                        highlightbackground=accent_dark)
        live.pack(fill="x", padx=8, pady=(4, 8))
        self._row_title(live, "Letture live")

        for r in self._i2c_manager.get_power_readings():
            tk.Label(live, text=f"  {r.label}: {r.format_compact()}",
                     font=self.fonts["mono"], fg=self.colors["online"],
                     bg=card, anchor="w"
                     ).pack(fill="x", padx=12, pady=1)

        for r in self._i2c_manager.get_env_readings():
            tk.Label(live, text=f"  {r.label}: {r.format_compact()}",
                     font=self.fonts["mono"], fg=self.colors["accent"],
                     bg=card, anchor="w"
                     ).pack(fill="x", padx=12, pady=1)

    def _add_sensor(self, stype: str):
        defaults = {
            "ina219": {"type": "ina219", "enabled": False, "address": "0x40",
                       "label": "INA219", "role": "alimentazione",
                       "shunt_ohms": 0.1, "max_expected_amps": 2.0},
            "bme280": {"type": "bme280", "enabled": False, "address": "0x76",
                       "label": "BME280", "role": "ambiente"},
            "sht30":  {"type": "sht30",  "enabled": False, "address": "0x44",
                       "label": "SHT30", "role": "interno"},
        }
        self.cfg.setdefault("i2c", {}).setdefault("sensors", []).append(
            defaults[stype])
        if self._render_callback:
            self._render_callback()

    # ------------------------------------------------------------------ #
    # Collect values for save                                              #
    # ------------------------------------------------------------------ #

    def get_sensor_configs(self) -> list[dict]:
        """Restituisce la lista di dict sensore per settings.json i2c.sensors."""
        sensors = self.cfg.get("i2c", {}).get("sensors", [])
        for row in self._i2c_rows:
            idx = row["idx"]
            if idx >= len(sensors):
                continue
            sensors[idx]["enabled"] = row["enabled"].get()
            sensors[idx]["label"] = row["label"].get().strip()
            sensors[idx]["address"] = row["address"].get().strip()
            sensors[idx]["role"] = row["role"].get()
            if row["shunt_ohms"] is not None:
                sensors[idx]["shunt_ohms"] = float(
                    row["shunt_ohms"].get() or 0.1)
            if row["max_expected_amps"] is not None:
                sensors[idx]["max_expected_amps"] = float(
                    row["max_expected_amps"].get() or 2.0)
        return sensors

    def get_bus_config(self) -> dict:
        """Restituisce dict con bus e poll_interval_ms."""
        return {
            "bus": int(self.i2c_bus.get() or 1),
            "poll_interval_ms": int(self.i2c_interval.get() or 2000),
        }

    # ------------------------------------------------------------------ #
    # Row builder helpers                                                  #
    # ------------------------------------------------------------------ #

    def _row_title(self, parent, text: str):
        tk.Label(parent, text=text, font=self.fonts["bold"],
                 fg=self.colors["fg"], bg=self.colors["card"], anchor="w"
                 ).pack(fill="x", padx=12, pady=(8, 2))

    def _row_toggle(self, parent, label: str, initial: bool) -> tk.BooleanVar:
        var = tk.BooleanVar(value=initial)
        row = tk.Frame(parent, bg=self.colors["card"])
        row.pack(fill="x", padx=12, pady=2)
        row.columnconfigure(0, weight=1)

        tk.Label(row, text=label, font=self.fonts["normal"],
                 fg=self.colors["fg"], bg=self.colors["card"], anchor="w"
                 ).grid(row=0, column=0, sticky="w")

        def _refresh():
            if var.get():
                toggle.configure(text="✓  ON", fg=self.colors["bg"],
                                 bg=self.colors["online"])
            else:
                toggle.configure(text="○  OFF", fg=self.colors["dim"],
                                 bg=self.colors["accent_dark"])

        toggle = tk.Button(
            row, text="", font=self.fonts["small"],
            relief="flat", bd=0, padx=10, pady=3,
            command=lambda: (var.set(not var.get()), _refresh()),
        )
        toggle.grid(row=0, column=1, padx=(8, 0))
        _refresh()
        return var

    def _row_entry(self, parent, label: str, initial: str) -> tk.StringVar:
        var = tk.StringVar(value=initial)
        row = tk.Frame(parent, bg=self.colors["card"])
        row.pack(fill="x", padx=12, pady=2)
        row.columnconfigure(0, weight=1)

        tk.Label(row, text=label, font=self.fonts["normal"],
                 fg=self.colors["fg"], bg=self.colors["card"], anchor="w"
                 ).grid(row=0, column=0, sticky="w")

        entry = tk.Entry(row, textvariable=var, width=14,
                         font=self.fonts["mono"], fg=self.colors["fg"],
                         bg=self.colors["bg"],
                         insertbackground=self.colors["accent"],
                         relief="flat", bd=3)
        entry.grid(row=0, column=1, padx=(8, 0))
        if self._bind_touch_entry:
            self._bind_touch_entry(entry)
        return var
