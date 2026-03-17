"""
Debug screen — live radio telemetry + application log viewer.

Layout (480×320):
  ┌─────────────────────────────────────────────┐
  │  ≡ DEBUG RADIO                  ⚠2  ● OK   │  ← topbar (row 0)
  ├─────────────────────────────────────────────┤
  │  RSSI   ██████████░░░  -85 dBm              │  ← meters (row 1)
  │  SNR    ██████████████  7.5 dB              │
  ├─────────────────────────────────────────────┤
  │  │HOP 1│ │RX 142│ │TX 37│ │CH 4%│  ▁▂▄▆▄  │  ← chips + mini-sparkline (row 2)
  ├─────────────────────────────────────────────┤
  │  REGISTRO APPLICAZIONE            [PULISCI] │  ← log viewer header (row 3)
  │  10:23 I  main: Radio connesso              │
  │  10:23 W  i2c_manager: BME280 non trovato   │  (expandable, scrollable)
  │  10:24 E  gps_reader: timeout seriale       │
  ├─────────────────────────────────────────────┤
  │  ⌂ HOME  ✉ CHAT  ◉ NODI  ≡ DEBUG  ⚙ CONFIG │  ← nav (row 4)
  └─────────────────────────────────────────────┘

Colour coding in the log viewer:
  DEBUG   → fg_dim_color  (grey)
  INFO    → fg_color      (light)
  WARNING → warning_color (orange)
  ERROR / CRITICAL → error_color (red)
"""

import logging
import tkinter as tk
from collections import deque

from .base_screen import BaseScreen
from .icons import DOT_ON, DOT_OFF
from .log_buffer import ui_log_handler


_HISTORY_LEN = 60
_BAR_MAX_W   = 256    # max pixel width for meter bars (slightly narrower than before)
_POLL_MS     = 1000


class DebugScreen(BaseScreen):

    def build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)   # log viewer gets all extra vertical space

        self._rssi_history: deque[int] = deque(maxlen=_HISTORY_LEN)
        self._warn_count = 0             # unread warnings/errors

        self._build_topbar()
        self._build_meters()
        self._build_chips_spark()        # chips + mini sparkline on the same row
        self._build_log_viewer()
        nav = self.nav_bar(self, "debug")
        nav.grid(row=4, column=0, sticky="ew")

        self._poll()

    # ------------------------------------------------------------------ #
    # Top bar                                                              #
    # ------------------------------------------------------------------ #

    def _build_topbar(self):
        bar = tk.Frame(self, bg=self.topbar)
        bar.grid(row=0, column=0, sticky="ew")

        tk.Label(bar, text="≡ DEBUG RADIO", font=self.f_bold,
                 fg=self.fg, bg=self.topbar).pack(side="left", padx=8, pady=4)

        # Radio status (right side)
        self._lbl_status = tk.Label(bar, text="", font=self.f_small,
                                    fg=self.online, bg=self.topbar)
        self._lbl_status.pack(side="right", padx=(4, 8))

        # Warning / error badge
        self._lbl_warn = tk.Label(bar, text="", font=self.f_small,
                                  fg=self.warn, bg=self.topbar)
        self._lbl_warn.pack(side="right", padx=2)

    # ------------------------------------------------------------------ #
    # Meter bars (RSSI + SNR)                                             #
    # ------------------------------------------------------------------ #

    def _build_meters(self):
        outer = tk.Frame(self, bg=self.bg)
        outer.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 2))
        outer.columnconfigure(0, weight=1)

        c = self.card(outer)
        c.pack(fill="x")

        self._meters: dict[str, dict] = {}

        meter_defs = [
            ("RSSI", "rssi", "dBm", self._rssi_frac),
            ("SNR",  "snr",  "dB",  self._snr_frac),
        ]

        for i, (label, key, unit, frac_fn) in enumerate(meter_defs):
            row = tk.Frame(c, bg=self.card)
            row.pack(fill="x", padx=8,
                     pady=(4 if i == 0 else 2,
                            4 if i == len(meter_defs) - 1 else 2))
            row.columnconfigure(2, weight=1)

            tk.Label(row, text=label, font=self.f_bold,
                     fg=self.dim, bg=self.card, width=5, anchor="w"
                     ).pack(side="left")

            track = tk.Frame(row, bg=self.cfg["accent_dark_color"],
                             height=8, width=_BAR_MAX_W)
            track.pack(side="left", padx=6)
            track.pack_propagate(False)

            fill = tk.Frame(track, bg=self.accent, height=8)
            fill.place(x=0, y=0, relheight=1.0, width=0)

            val_lbl = tk.Label(row, text="—", font=self.f_mono_s,
                               fg=self.fg, bg=self.card, anchor="w", width=12)
            val_lbl.pack(side="left")

            self._meters[key] = {"fill": fill, "lbl": val_lbl,
                                  "unit": unit, "frac_fn": frac_fn}

    # ------------------------------------------------------------------ #
    # Stat chips + mini sparkline (combined compact row)                  #
    # ------------------------------------------------------------------ #

    def _build_chips_spark(self):
        outer = tk.Frame(self, bg=self.bg)
        outer.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 2))
        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=0)

        # ── chips (left) ──────────────────────────────────────────────
        chips_frame = tk.Frame(outer, bg=self.bg)
        chips_frame.grid(row=0, column=0, sticky="w")

        defs = [
            ("HOP",  "hops",    lambda v: str(v)),
            ("RX",   "rx_pkts", lambda v: str(v)),
            ("TX",   "tx_pkts", lambda v: str(v)),
            ("CH",   "ch_util", lambda v: f"{v:.0f}%"),
        ]

        self._chips: dict[str, tk.Label] = {}

        for j, (label, key, fmt) in enumerate(defs):
            f = self.card(chips_frame)
            f.grid(row=0, column=j, sticky="ew",
                   padx=(0 if j == 0 else 3, 0), pady=2)
            chips_frame.columnconfigure(j, weight=1)

            tk.Label(f, text=label, font=self.f_small,
                     fg=self.dim, bg=self.card).pack(pady=(3, 0), padx=6)

            val = tk.Label(f, text="—", font=self.f_bold,
                           fg=self.fg, bg=self.card)
            val.pack(pady=(0, 3), padx=6)

            self._chips[key] = val
            self._chips[key]._fmt = fmt

        # ── mini sparkline (right) ────────────────────────────────────
        spark_frame = tk.Frame(outer, bg=self.bg)
        spark_frame.grid(row=0, column=1, sticky="ns", padx=(6, 0))

        tk.Label(spark_frame, text="RSSI", font=self.f_small,
                 fg=self.dim, bg=self.bg).pack(anchor="w")

        self._spark = tk.Canvas(spark_frame, bg=self.card, height=32, width=96,
                                highlightthickness=1,
                                highlightbackground=self.cfg["accent_dark_color"])
        self._spark.pack()
        self._spark.bind("<Configure>", lambda _e: self._draw_spark())

    # ------------------------------------------------------------------ #
    # Log viewer                                                           #
    # ------------------------------------------------------------------ #

    def _build_log_viewer(self):
        frame = tk.Frame(self, bg=self.bg)
        frame.grid(row=3, column=0, sticky="nsew", padx=8, pady=(0, 4))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        # Header row
        hdr = tk.Frame(frame, bg=self.bg)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.columnconfigure(0, weight=1)

        tk.Label(hdr, text="REGISTRO APPLICAZIONE",
                 font=self.f_small, fg=self.dim,
                 bg=self.bg, anchor="w").grid(row=0, column=0, sticky="w")

        tk.Button(hdr, text="PULISCI",
                  font=self.f_small, fg=self.dim,
                  bg=self.bg, activeforeground=self.bg,
                  activebackground=self.dim,
                  relief="flat", bd=0,
                  command=self._clear_log
                  ).grid(row=0, column=1, sticky="e")

        # Scrollable text area
        txt_frame = tk.Frame(frame, bg=self.card,
                             highlightthickness=1,
                             highlightbackground=self.cfg["accent_dark_color"])
        txt_frame.grid(row=1, column=0, sticky="nsew")
        txt_frame.columnconfigure(0, weight=1)
        txt_frame.rowconfigure(0, weight=1)

        self._log_text = tk.Text(
            txt_frame,
            font=self.f_mono_s,
            fg=self.dim, bg=self.card,
            insertbackground=self.accent,
            relief="flat", bd=0,
            state="disabled",
            wrap="none",
            cursor="",
        )
        self._log_text.grid(row=0, column=0, sticky="nsew")

        sb = tk.Scrollbar(txt_frame, orient="vertical",
                          command=self._log_text.yview,
                          bg=self.card, troughcolor=self.bg, width=5)
        sb.grid(row=0, column=1, sticky="ns")
        self._log_text.config(yscrollcommand=sb.set)

        # Colour tags
        self._log_text.tag_config("D", foreground=self.dim)
        self._log_text.tag_config("I", foreground=self.fg)
        self._log_text.tag_config("W", foreground=self.warn)
        self._log_text.tag_config("E", foreground=self.err)

        # Subscribe to new records
        ui_log_handler.on_new_record(
            lambda r: self._log_text.after(0, self._append_record, r))

    def on_enter(self):
        """Reload the full buffer when the screen becomes active."""
        self._reload_log()
        self._warn_count = 0
        self._lbl_warn.config(text="")

    def _reload_log(self):
        self._log_text.config(state="normal")
        self._log_text.delete("1.0", tk.END)
        for record in ui_log_handler.get_records():
            self._insert_record(record)
        self._log_text.config(state="disabled")
        self._log_text.see(tk.END)

    def _append_record(self, record: logging.LogRecord):
        """Append a single record (called on Tkinter thread via after())."""
        self._log_text.config(state="normal")
        self._insert_record(record)
        self._log_text.config(state="disabled")
        self._log_text.see(tk.END)

        # Update warn badge for warnings/errors received while not viewing
        if record.levelno >= logging.WARNING:
            self._warn_count += 1
            self._lbl_warn.config(text=f"⚠{self._warn_count}")

    def _insert_record(self, record: logging.LogRecord):
        line = getattr(record, "_ui_line",
                       f"{record.levelname[0]}  {record.getMessage()}")
        tag = {
            logging.DEBUG:    "D",
            logging.INFO:     "I",
            logging.WARNING:  "W",
            logging.ERROR:    "E",
            logging.CRITICAL: "E",
        }.get(record.levelno, "I")
        self._log_text.insert(tk.END, line + "\n", tag)

    def _clear_log(self):
        ui_log_handler.clear()
        self._log_text.config(state="normal")
        self._log_text.delete("1.0", tk.END)
        self._log_text.config(state="disabled")
        self._warn_count = 0
        self._lbl_warn.config(text="")

    # ------------------------------------------------------------------ #
    # Poll                                                                 #
    # ------------------------------------------------------------------ #

    def _poll(self):
        self._refresh()
        self.after(_POLL_MS, self._poll)

    def _refresh(self):
        s = self.client.stats
        connected = self.client.connected

        if connected:
            self._lbl_status.config(text=f"{DOT_ON} OK", fg=self.online)
        else:
            self._lbl_status.config(text=f"{DOT_OFF} OFF", fg=self.err)

        for key, m in self._meters.items():
            val = getattr(s, key) if hasattr(s, key) else 0
            frac = m["frac_fn"](val)
            w = max(2, int(_BAR_MAX_W * frac))
            color = self._bar_color(frac)
            m["fill"].config(bg=color)
            m["fill"].place(width=w)
            unit = m["unit"]
            if key == "rssi":
                m["lbl"].config(text=f"{val} {unit}")
            elif key == "snr":
                m["lbl"].config(text=f"{val:.1f} {unit}")

        chip_vals = {
            "hops":    s.hops,
            "rx_pkts": s.rx_packets,
            "tx_pkts": s.tx_packets,
            "ch_util": s.channel_util,
        }
        for key, val in chip_vals.items():
            if key in self._chips:
                self._chips[key].config(text=self._chips[key]._fmt(val))

        self._rssi_history.append(s.rssi)
        self._draw_spark()

    # ------------------------------------------------------------------ #
    # Sparkline drawing                                                    #
    # ------------------------------------------------------------------ #

    def _draw_spark(self):
        c = self._spark
        c.delete("all")
        if len(self._rssi_history) < 2:
            return

        w = c.winfo_width()
        h = c.winfo_height()
        if w < 4 or h < 4:
            return

        data = list(self._rssi_history)
        lo, hi = -120, -40
        step = w / max(len(data) - 1, 1)

        pts = []
        for i, val in enumerate(data):
            x = i * step
            frac = (val - lo) / (hi - lo)
            y = h - frac * (h - 3) - 1
            pts.append((x, y))

        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            frac = (data[i] - lo) / (hi - lo)
            c.create_line(x0, y0, x1, y1, fill=self._bar_color(frac), width=1)

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def on_scroll(self, direction: int):
        self._log_text.yview_scroll(direction, "units")

    @staticmethod
    def _rssi_frac(rssi: int) -> float:
        return max(0.0, min(1.0, (rssi - (-120)) / (-40 - (-120))))

    @staticmethod
    def _snr_frac(snr: float) -> float:
        return max(0.0, min(1.0, (snr - (-20)) / (15 - (-20))))

    def _bar_color(self, frac: float) -> str:
        if frac >= 0.6:  return self.online
        if frac >= 0.3:  return self.warn
        return self.err
