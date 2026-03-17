"""
Debug screen — live radio layer telemetry, Meshtastic-style.

Layout (480×320):
  ┌─────────────────────────────────────────────┐
  │  ⚙ DEBUG RADIO                     ● OK     │
  ├─────────────────────────────────────────────┤
  │  ┌─────────────────────────────────────┐    │
  │  │ RSSI   ██████████░░░░░░  -85 dBm    │    │
  │  │ SNR    ██████████████░░   7.5 dB    │    │
  │  └─────────────────────────────────────┘    │
  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │
  │  │HOP  1│ │RX 142│ │TX  37│ │CH 4% │       │
  │  └──────┘ └──────┘ └──────┘ └──────┘       │
  │  RSSI ▁▂▄▆▄▂▁▄▆█▄▂▁ (60 campioni)          │
  ├─────────────────────────────────────────────┤
  │  ⌂ HOME   ✉ CHAT   ◉ NODI   ⚙ DEBUG        │
  └─────────────────────────────────────────────┘
"""

import tkinter as tk
from collections import deque
from .base_screen import BaseScreen
from .icons import DOT_ON, DOT_OFF


_HISTORY_LEN = 60
_BAR_MAX_W   = 260    # max pixel width for meter bars
_POLL_MS     = 1000


class DebugScreen(BaseScreen):

    def build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self._rssi_history: deque[int] = deque(maxlen=_HISTORY_LEN)

        self._build_topbar()
        self._build_meters()
        self._build_stat_chips()
        self._build_sparkline()
        nav = self.nav_bar(self, "debug")
        nav.grid(row=4, column=0, sticky="ew")

        self._poll()

    # ------------------------------------------------------------------ #
    # Top bar                                                              #
    # ------------------------------------------------------------------ #

    def _build_topbar(self):
        bar = tk.Frame(self, bg=self.topbar)
        bar.grid(row=0, column=0, sticky="ew")

        tk.Label(bar, text="⚙ DEBUG RADIO", font=self.f_bold,
                 fg=self.fg, bg=self.topbar).pack(side="left", padx=8, pady=4)

        self._lbl_status = tk.Label(bar, text="", font=self.f_small,
                                    fg=self.online, bg=self.topbar)
        self._lbl_status.pack(side="right", padx=10)

    # ------------------------------------------------------------------ #
    # Meter bars (RSSI + SNR)                                             #
    # ------------------------------------------------------------------ #

    def _build_meters(self):
        outer = tk.Frame(self, bg=self.bg)
        outer.grid(row=1, column=0, sticky="ew", padx=8, pady=6)
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
            row.pack(fill="x", padx=8, pady=(6 if i == 0 else 2,
                                              6 if i == len(meter_defs) - 1 else 2))
            row.columnconfigure(2, weight=1)

            tk.Label(row, text=label, font=self.f_bold,
                     fg=self.dim, bg=self.card, width=5, anchor="w"
                     ).pack(side="left")

            # Bar track
            track = tk.Frame(row, bg=self.cfg["accent_dark_color"],
                             height=10, width=_BAR_MAX_W)
            track.pack(side="left", padx=6)
            track.pack_propagate(False)

            fill = tk.Frame(track, bg=self.accent, height=10)
            fill.place(x=0, y=0, relheight=1.0, width=0)

            val_lbl = tk.Label(row, text="—", font=self.f_mono_s,
                               fg=self.fg, bg=self.card, anchor="w", width=12)
            val_lbl.pack(side="left")

            self._meters[key] = {"fill": fill, "lbl": val_lbl,
                                  "unit": unit, "frac_fn": frac_fn}

    # ------------------------------------------------------------------ #
    # Stat chips (hop / rx / tx / ch-util)                                #
    # ------------------------------------------------------------------ #

    def _build_stat_chips(self):
        row = tk.Frame(self, bg=self.bg)
        row.grid(row=2, column=0, sticky="ew", padx=8)

        defs = [
            ("HOP",  "hops",    "",  lambda v: str(v)),
            ("RX",   "rx_pkts", "",  lambda v: str(v)),
            ("TX",   "tx_pkts", "",  lambda v: str(v)),
            ("CH",   "ch_util", "%", lambda v: f"{v:.0f}%"),
        ]

        self._chips: dict[str, tk.Label] = {}

        for j, (label, key, unit, fmt) in enumerate(defs):
            f = self.card(row)
            f.grid(row=0, column=j, sticky="ew", padx=3, pady=2)
            row.columnconfigure(j, weight=1)

            tk.Label(f, text=label, font=self.f_small,
                     fg=self.dim, bg=self.card).pack(pady=(4, 0))

            val = tk.Label(f, text="—", font=self.f_bold,
                           fg=self.fg, bg=self.card)
            val.pack(pady=(0, 4))

            self._chips[key] = val
            self._chips[key]._fmt = fmt

    # ------------------------------------------------------------------ #
    # Sparkline                                                            #
    # ------------------------------------------------------------------ #

    def _build_sparkline(self):
        frame = tk.Frame(self, bg=self.bg)
        frame.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 6))
        frame.columnconfigure(0, weight=1)

        tk.Label(frame, text="RSSI — ultimi 60 campioni",
                 font=self.f_small, fg=self.dim, bg=self.bg,
                 anchor="w").grid(row=0, column=0, sticky="w")

        self._spark = tk.Canvas(frame, bg=self.card, height=44,
                                highlightthickness=1,
                                highlightbackground=self.cfg["accent_dark_color"])
        self._spark.grid(row=1, column=0, sticky="ew")
        self._spark.bind("<Configure>", lambda _e: self._draw_spark())

    # ------------------------------------------------------------------ #
    # Poll                                                                 #
    # ------------------------------------------------------------------ #

    def _poll(self):
        self._refresh()
        self.after(_POLL_MS, self._poll)

    def _refresh(self):
        s = self.client.stats
        connected = self.client.connected

        # Status
        if connected:
            self._lbl_status.config(text=f"{DOT_ON} OK", fg=self.online)
        else:
            self._lbl_status.config(text=f"{DOT_OFF} OFF", fg=self.err)

        # Meter bars
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

        # Chips
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
            y = h - frac * (h - 4) - 2
            pts.append((x, y))

        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            frac = (data[i] - lo) / (hi - lo)
            c.create_line(x0, y0, x1, y1, fill=self._bar_color(frac), width=2)

        # -100 dBm reference line
        zy = h - ((-100 - lo) / (hi - lo)) * (h - 4) - 2
        c.create_line(0, zy, w, zy, fill=self.cfg["accent_dark_color"],
                      dash=(3, 5))
        c.create_text(4, zy - 6, text="-100", anchor="w",
                      font=self.f_small, fill=self.dim)

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

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
