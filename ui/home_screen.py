"""
Home screen — Meshtastic-style dashboard.

Layout (480×320):
  ┌─────────────────────────────────────────────┐
  │ ◉ MESH-PI             ● 3 nodi   ⚡████░    │  ← top bar
  ├─────────────────────────────────────────────┤
  │  ┌───────────────────────────────────────┐  │
  │  │  ● CONNESSO   RSSI  -85 dBm    0:12:34 │  │  ← status card
  │  │  ▂▄▆█  7.5dB  SNR   7.5 dB   1 hop   │  │
  │  └───────────────────────────────────────┘  │
  │  ┌──────────────┐  ┌──────────────────────┐ │
  │  │ ↑ TX  37 pkt │  │ ↓ RX  142 pkt        │ │  ← metric chips
  │  └──────────────┘  └──────────────────────┘ │
  │  EVENTI ─────────────────────────────────── │
  │  ↗ Connesso  14:22                          │
  │  ✉ [Base Alpha] Posizione conf...            │
  ├─────────────────────────────────────────────┤
  │ ⌂ HOME   ✉ CHAT   ◉ NODI   ⚙ DEBUG         │
  └─────────────────────────────────────────────┘
"""

import time
import tkinter as tk
from .base_screen import BaseScreen
from .icons import signal_bars, battery_icon, DOT_ON, DOT_OFF, rssi_color


class HomeScreen(BaseScreen):

    def build(self):
        self._start_time = time.time()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self._build_topbar()
        self._build_status_card()
        self._build_events()
        nav = self.nav_bar(self, "home")
        nav.grid(row=3, column=0, sticky="ew")

        self.client.on_status_change(self._on_status)
        self.client.on_message(self._on_message)

        self._poll()

    # ------------------------------------------------------------------ #
    # Top bar                                                              #
    # ------------------------------------------------------------------ #

    def _build_topbar(self):
        bar = tk.Frame(self, bg=self.topbar)
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)

        # App icon + title
        tk.Label(bar, text="◉ MESH-PI", font=self.f_bold,
                 fg=self.accent, bg=self.topbar).pack(side="left", padx=8, pady=4)

        # Right: node count chip + battery
        self._lbl_node_count = tk.Label(bar, text="",
                                        font=self.f_small, fg=self.fg,
                                        bg=self.topbar)
        self._lbl_node_count.pack(side="right", padx=(0, 10))

        self._lbl_battery = tk.Label(bar, text="",
                                     font=self.f_small, fg=self.online,
                                     bg=self.topbar)
        self._lbl_battery.pack(side="right", padx=2)

        self._lbl_conn_dot = tk.Label(bar, text=DOT_ON,
                                      font=self.f_icon, fg=self.online,
                                      bg=self.topbar)
        self._lbl_conn_dot.pack(side="right", padx=(8, 2))

    # ------------------------------------------------------------------ #
    # Status card                                                          #
    # ------------------------------------------------------------------ #

    def _build_status_card(self):
        outer = tk.Frame(self, bg=self.bg)
        outer.grid(row=1, column=0, sticky="ew", padx=8, pady=6)
        outer.columnconfigure(0, weight=1)

        c = self.card(outer)
        c.pack(fill="x")
        c.columnconfigure(1, weight=1)
        c.columnconfigure(3, weight=1)

        # Row 0: status dot + label | RSSI value | uptime
        self._lbl_status = tk.Label(c, text="", font=self.f_bold,
                                    fg=self.online, bg=self.card)
        self._lbl_status.grid(row=0, column=0, columnspan=2,
                               sticky="w", padx=10, pady=(6, 2))

        self._lbl_uptime = tk.Label(c, text="", font=self.f_small,
                                    fg=self.dim, bg=self.card)
        self._lbl_uptime.grid(row=0, column=3, sticky="e", padx=10)

        # Row 1: signal bars | RSSI | SNR | hop
        self._lbl_sigbars = tk.Label(c, text="", font=("DejaVu Sans Mono", 13),
                                     fg=self.accent, bg=self.card)
        self._lbl_sigbars.grid(row=1, column=0, padx=(10, 4), pady=(0, 6))

        self._lbl_rssi = tk.Label(c, text="", font=self.f_mono_s,
                                  fg=self.dim, bg=self.card, anchor="w")
        self._lbl_rssi.grid(row=1, column=1, sticky="w")

        self._lbl_snr = tk.Label(c, text="", font=self.f_mono_s,
                                 fg=self.dim, bg=self.card, anchor="w")
        self._lbl_snr.grid(row=1, column=2, sticky="w", padx=4)

        self._lbl_hop = tk.Label(c, text="", font=self.f_mono_s,
                                 fg=self.dim, bg=self.card, anchor="e")
        self._lbl_hop.grid(row=1, column=3, sticky="e", padx=10)

        # Metric chips row
        chips = tk.Frame(self, bg=self.bg)
        chips.grid(row=1, column=0, sticky="ew", padx=8)
        chips.columnconfigure(0, weight=1)
        chips.columnconfigure(1, weight=1)

        self._chip_tx = self._make_chip(chips)
        self._chip_tx.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=4)

        self._chip_rx = self._make_chip(chips)
        self._chip_rx.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=4)

    def _make_chip(self, parent) -> tk.Frame:
        f = self.card(parent)
        lbl = tk.Label(f, text="", font=self.f_small,
                       fg=self.fg, bg=self.card, anchor="w")
        lbl.pack(padx=8, pady=4)
        f._lbl = lbl
        return f

    # ------------------------------------------------------------------ #
    # Events log                                                           #
    # ------------------------------------------------------------------ #

    def _build_events(self):
        outer = tk.Frame(self, bg=self.bg)
        outer.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 4))
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        tk.Label(outer, text="EVENTI", font=self.f_small,
                 fg=self.dim, bg=self.bg, anchor="w").grid(
            row=0, column=0, sticky="w")

        self._evt_txt = tk.Text(
            outer,
            font=self.f_small, fg=self.fg, bg=self.bg,
            relief="flat", state="disabled", wrap="word",
            cursor="", selectbackground=self.card,
        )
        self._evt_txt.grid(row=1, column=0, sticky="nsew")
        self._evt_txt.tag_configure("ts",  foreground=self.dim)
        self._evt_txt.tag_configure("msg", foreground=self.accent)

    # ------------------------------------------------------------------ #
    # Callbacks                                                            #
    # ------------------------------------------------------------------ #

    def _on_status(self, text: str):
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M")
        self._evt_txt.after(0, self._append_event, f"↗ {text}", ts)

    def _on_message(self, msg):
        from datetime import datetime
        ts = msg.timestamp.strftime("%H:%M")
        preview = msg.text[:28] + ("…" if len(msg.text) > 28 else "")
        self._evt_txt.after(0, self._append_event,
                            f"✉ [{msg.sender}] {preview}", ts)

    def _append_event(self, text: str, ts: str = ""):
        self._evt_txt.configure(state="normal")
        if ts:
            self._evt_txt.insert("end", f"{ts}  ", "ts")
        self._evt_txt.insert("end", text + "\n", "msg")
        self._evt_txt.see("end")
        self._evt_txt.configure(state="disabled")

    # ------------------------------------------------------------------ #
    # Polling                                                              #
    # ------------------------------------------------------------------ #

    def _poll(self):
        self._refresh()
        self.after(self.cfg["refresh_interval_ms"], self._poll)

    def _refresh(self):
        s = self.client.stats
        n_nodes = len(self.client.nodes)
        connected = self.client.connected

        # Top bar
        dot_color = self.online if connected else self.err
        dot_text  = DOT_ON if connected else DOT_OFF
        self._lbl_conn_dot.config(text=dot_text, fg=dot_color)
        self._lbl_node_count.config(
            text=f"{n_nodes} nod{'o' if n_nodes == 1 else 'i'}")
        self._lbl_battery.config(text=battery_icon(80))   # placeholder; real hw needed

        # Status card
        if connected:
            self._lbl_status.config(text=f"{DOT_ON}  CONNESSO", fg=self.online)
        else:
            self._lbl_status.config(text=f"{DOT_OFF}  DISCONNESSO", fg=self.err)

        sig_color = self.rssi_color(s.rssi)
        self._lbl_sigbars.config(text=signal_bars(s.rssi), fg=sig_color)
        self._lbl_rssi.config(text=f"RSSI {s.rssi} dBm")
        self._lbl_snr.config(text=f"SNR {s.snr:.1f} dB")
        self._lbl_hop.config(text=f"{s.hops} hop")

        # Uptime
        elapsed = int(time.time() - self._start_time)
        h, rem = divmod(elapsed, 3600)
        m, sec = divmod(rem, 60)
        self._lbl_uptime.config(text=f"{h:02d}:{m:02d}:{sec:02d}")

        # Metric chips
        self._chip_tx._lbl.config(text=f"↑ TX  {s.tx_packets} pkt")
        self._chip_rx._lbl.config(text=f"↓ RX  {s.rx_packets} pkt")
