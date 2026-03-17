"""
Tab GPS — configurazione modulo GPS seriale NMEA.

Estratto da settings_screen.py — render GPS + status fix live.
"""

import tkinter as tk


class TabGPS(tk.Frame):
    """Configurazione GPS: porta seriale, baud, abilitazione, fix live."""

    def __init__(self, parent, colors: dict, fonts: dict, cfg: dict,
                 hw_manager=None, bind_touch_entry=None, **kw):
        super().__init__(parent, bg=colors["bg"], **kw)
        self.colors = colors
        self.fonts = fonts
        self.cfg = cfg
        self._hw_manager = hw_manager
        self._bind_touch_entry = bind_touch_entry

        self._build(cfg.get("hardware", {}).get("gps", {}))

    # ------------------------------------------------------------------ #
    # Build                                                                #
    # ------------------------------------------------------------------ #

    def _build(self, gps: dict):
        bg = self.colors["bg"]
        card = self.colors["card"]
        fg = self.colors["fg"]
        dim = self.colors["dim"]
        accent_dark = self.colors["accent_dark"]
        online = self.colors["online"]
        warn = self.colors["warn"]

        # Main card
        c = tk.Frame(self, bg=card, highlightthickness=1,
                     highlightbackground=accent_dark)
        c.pack(fill="x", padx=8, pady=8)

        self._row_title(c, "Modulo GPS (NMEA seriale)")
        self.gps_enabled = self._row_toggle(c, "Abilitato",
                                            gps.get("enabled", False))
        self.gps_port = self._row_entry(c, "Porta seriale",
                                        gps.get("port", "/dev/ttyAMA0"))
        self.gps_baud = self._row_entry(c, "Baud rate",
                                        str(gps.get("baud", 9600)))
        self.gps_mesh = self._row_toggle(c, "Aggiorna pos. Meshtastic",
                                         gps.get("update_mesh_position", False))

        # Live GPS status
        self._row_sep(c)
        self._row_title(c, "Fix GPS")

        self._lbl_gps_coords = tk.Label(c, text="--", font=self.fonts["mono"],
                                        fg=fg, bg=card, anchor="w")
        self._lbl_gps_coords.pack(fill="x", padx=12, pady=1)

        self._lbl_gps_alt = tk.Label(c, text="", font=self.fonts["small"],
                                     fg=dim, bg=card, anchor="w")
        self._lbl_gps_alt.pack(fill="x", padx=12, pady=1)

        self._lbl_gps_sats = tk.Label(c, text="", font=self.fonts["small"],
                                      fg=dim, bg=card, anchor="w")
        self._lbl_gps_sats.pack(fill="x", padx=12, pady=(1, 8))

        if self._hw_manager:
            if self._hw_manager.gps:
                fix = self._hw_manager.gps.fix
                self._update_gps_labels(fix)
                self._hw_manager.on_gps_fix(
                    lambda f: self._lbl_gps_coords.after(
                        0, self._update_gps_labels, f))
            else:
                self._row_status(c, "○ Non attivo", dim)

    # ------------------------------------------------------------------ #
    # GPS label updater                                                    #
    # ------------------------------------------------------------------ #

    def _update_gps_labels(self, fix):
        if not fix.has_fix:
            self._lbl_gps_coords.config(text="Nessun fix",
                                        fg=self.colors["warn"])
            self._lbl_gps_alt.config(text="")
            self._lbl_gps_sats.config(text="")
        else:
            self._lbl_gps_coords.config(
                text=fix.format_coords(), fg=self.colors["online"])
            self._lbl_gps_alt.config(
                text=f"Alt {fix.format_altitude()}  "
                     f"Vel {fix.format_speed()}  "
                     f"HDOP {fix.hdop:.1f}")
            self._lbl_gps_sats.config(
                text=f"Satelliti: {fix.satellites}  "
                     f"Qualita: {fix.quality}")

    # ------------------------------------------------------------------ #
    # Collect values for save                                              #
    # ------------------------------------------------------------------ #

    def get_gps_config(self) -> dict:
        """Restituisce dict pronto per settings.json hardware.gps."""
        return {
            "enabled":              self.gps_enabled.get(),
            "port":                 self.gps_port.get().strip(),
            "baud":                 int(self.gps_baud.get() or 9600),
            "update_mesh_position": self.gps_mesh.get(),
        }

    # ------------------------------------------------------------------ #
    # Row builder helpers (same style as original SettingsScreen)          #
    # ------------------------------------------------------------------ #

    def _row_title(self, parent, text: str):
        tk.Label(parent, text=text, font=self.fonts["bold"],
                 fg=self.colors["fg"], bg=self.colors["card"], anchor="w"
                 ).pack(fill="x", padx=12, pady=(8, 2))

    def _row_sep(self, parent):
        tk.Frame(parent, bg=self.colors["accent_dark"], height=1
                 ).pack(fill="x", padx=12, pady=4)

    def _row_status(self, parent, text: str, color: str):
        tk.Label(parent, text=text, font=self.fonts["small"],
                 fg=color, bg=self.colors["card"], anchor="w"
                 ).pack(fill="x", padx=12, pady=(2, 8))

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
                         bg=self.colors["bg"], insertbackground=self.colors["accent"],
                         relief="flat", bd=3)
        entry.grid(row=0, column=1, padx=(8, 0))
        if self._bind_touch_entry:
            self._bind_touch_entry(entry)
        return var
