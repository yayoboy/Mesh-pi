"""
Debug screen — live radio layer telemetry.

Layout (480×320):
  ┌─────────────────────────────────────┐
  │  DEBUG RADIO                        │
  ├─────────────────────────────────────┤
  │  RSSI     ████████░░  -85 dBm       │
  │  SNR      █████████░   7.5 dB       │
  │  HOP COUNT            1             │
  │  RX PKTS              142           │
  │  TX PKTS              37            │
  │  CH UTIL              4.2 %         │
  ├─────────────────────────────────────┤
  │  RSSI history (sparkline)           │
  ├─────────────────────────────────────┤
  │ [HOME] [CHAT] [NODI] [DEBUG]        │
  └─────────────────────────────────────┘
"""

import tkinter as tk
from collections import deque
from .base_screen import BaseScreen


_HISTORY_LEN = 60      # number of samples kept for sparkline
_BAR_MAX_W = 200       # px, max bar width for meter bars
_POLL_MS = 1000        # stats refresh interval


class DebugScreen(BaseScreen):

    def build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._rssi_history: deque[int] = deque(maxlen=_HISTORY_LEN)

        self._build_header()
        self._build_meters()
        self._build_sparkline()
        nav = self.nav_bar(self, "debug")
        nav.grid(row=3, column=0, sticky="ew")

        self._poll()

    # ------------------------------------------------------------------ #
    # Header                                                               #
    # ------------------------------------------------------------------ #

    def _build_header(self):
        hdr = tk.Frame(self, bg=self.dim)
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(hdr, text="DEBUG RADIO", font=self.font_large,
                 fg=self.fg, bg=self.dim).pack(side="left", padx=8, pady=2)

        self._lbl_conn = tk.Label(hdr, text="", font=self.font_small,
                                  fg=self.accent, bg=self.dim)
        self._lbl_conn.pack(side="right", padx=8)

    # ------------------------------------------------------------------ #
    # Meter rows                                                           #
    # ------------------------------------------------------------------ #

    def _build_meters(self):
        frame = tk.Frame(self, bg=self.bg)
        frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        frame.columnconfigure(2, weight=1)

        self._meters = {}

        rows = [
            ("RSSI",     "rssi",    "dBm",  self._rssi_fraction),
            ("SNR",      "snr",     "dB",   self._snr_fraction),
            ("HOP COUNT","hops",    "",     None),
            ("RX PKTS",  "rx_pkts", "",     None),
            ("TX PKTS",  "tx_pkts", "",     None),
            ("CH UTIL",  "ch_util", "%",    None),
        ]

        for i, (label, key, unit, frac_fn) in enumerate(rows):
            lbl_key = tk.Label(frame, text=label, font=self.font_bold,
                               fg=self.dim, bg=self.bg, width=12, anchor="w")
            lbl_key.grid(row=i, column=0, sticky="w", pady=2)

            if frac_fn is not None:
                bar_bg = tk.Frame(frame, bg=self.dim, width=_BAR_MAX_W, height=12)
                bar_bg.grid(row=i, column=1, padx=4, sticky="w")
                bar_bg.pack_propagate(False)

                bar_fg = tk.Frame(bar_bg, bg=self.accent, height=12)
                bar_fg.place(x=0, y=0, relheight=1.0, width=0)
            else:
                bar_bg = None
                bar_fg = None

            lbl_val = tk.Label(frame, text="—", font=self.font_normal,
                               fg=self.fg, bg=self.bg, anchor="w", width=14)
            lbl_val.grid(row=i, column=2, sticky="w")

            self._meters[key] = {
                "lbl": lbl_val, "unit": unit,
                "bar_bg": bar_bg, "bar_fg": bar_fg, "frac_fn": frac_fn,
            }

    # ------------------------------------------------------------------ #
    # Sparkline                                                            #
    # ------------------------------------------------------------------ #

    def _build_sparkline(self):
        frame = tk.Frame(self, bg=self.bg)
        frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 4))

        tk.Label(frame, text="RSSI  (ultimi 60 campioni)",
                 font=self.font_small, fg=self.dim, bg=self.bg).pack(anchor="w")

        self._canvas = tk.Canvas(frame, bg="#0a0a0a", height=48,
                                 highlightthickness=0)
        self._canvas.pack(fill="x")
        self._canvas.bind("<Configure>", lambda _e: self._draw_sparkline())

    # ------------------------------------------------------------------ #
    # Polling                                                              #
    # ------------------------------------------------------------------ #

    def _poll(self):
        self._refresh()
        self.after(_POLL_MS, self._poll)

    def _refresh(self):
        s = self.client.stats

        conn_text = "● OK" if self.client.connected else "○ OFF"
        conn_color = self.accent if self.client.connected else self.err
        self._lbl_conn.config(text=conn_text, fg=conn_color)

        values = {
            "rssi":    (s.rssi,         lambda v: f"{v} dBm"),
            "snr":     (s.snr,          lambda v: f"{v:.1f} dB"),
            "hops":    (s.hops,         str),
            "rx_pkts": (s.rx_packets,   str),
            "tx_pkts": (s.tx_packets,   str),
            "ch_util": (s.channel_util, lambda v: f"{v:.1f} %"),
        }

        for key, (val, fmt) in values.items():
            m = self._meters[key]
            m["lbl"].config(text=fmt(val))

            if m["frac_fn"] and m["bar_fg"] and m["bar_bg"]:
                frac = m["frac_fn"](val)
                w = max(2, int(_BAR_MAX_W * frac))
                color = self._bar_color(frac)
                m["bar_fg"].place(width=w)
                m["bar_fg"].config(bg=color)

        self._rssi_history.append(s.rssi)
        self._draw_sparkline()

    # ------------------------------------------------------------------ #
    # Sparkline drawing                                                    #
    # ------------------------------------------------------------------ #

    def _draw_sparkline(self):
        c = self._canvas
        c.delete("all")

        if len(self._rssi_history) < 2:
            return

        w = c.winfo_width()
        h = c.winfo_height()
        if w < 4 or h < 4:
            return

        data = list(self._rssi_history)
        lo, hi = -120, -40
        n = len(data)
        step = w / max(n - 1, 1)

        points = []
        for i, val in enumerate(data):
            x = i * step
            frac = (val - lo) / (hi - lo)
            y = h - frac * (h - 4) - 2
            points.append((x, y))

        for i in range(len(points) - 1):
            x0, y0 = points[i]
            x1, y1 = points[i + 1]
            frac = (data[i] - lo) / (hi - lo)
            color = self._bar_color(frac)
            c.create_line(x0, y0, x1, y1, fill=color, width=2)

        # Zero line at -100 dBm
        zero_frac = (-100 - lo) / (hi - lo)
        zy = h - zero_frac * (h - 4) - 2
        c.create_line(0, zy, w, zy, fill=self.dim, dash=(2, 4))

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _rssi_fraction(rssi: int) -> float:
        lo, hi = -120, -40
        return max(0.0, min(1.0, (rssi - lo) / (hi - lo)))

    @staticmethod
    def _snr_fraction(snr: float) -> float:
        lo, hi = -20.0, 15.0
        return max(0.0, min(1.0, (snr - lo) / (hi - lo)))

    def _bar_color(self, frac: float) -> str:
        if frac >= 0.6:
            return self.accent
        if frac >= 0.3:
            return "#ffcc00"
        return self.err
