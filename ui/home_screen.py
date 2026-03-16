"""
Home screen — radio status, connected node count, signal overview.

Layout (480×320):
  ┌─────────────────────────────────────┐
  │  ◉ MESH-PI          [node name]     │  ← header
  ├─────────────────────────────────────┤
  │  STATO   ● CONNESSO                 │
  │  NODI    █████ 3                    │
  │  RSSI    -85 dBm                    │
  │  SNR     7.5 dB                     │
  │  HOP     1                          │
  │  UPTIME  00:12:34                   │
  ├─────────────────────────────────────┤
  │  Ultimi eventi …                    │
  ├─────────────────────────────────────┤
  │ [HOME] [CHAT] [NODI] [DEBUG]        │  ← nav bar
  └─────────────────────────────────────┘
"""

import time
import tkinter as tk
from .base_screen import BaseScreen


class HomeScreen(BaseScreen):

    def build(self):
        self._start_time = time.time()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_header()
        self._build_stats()
        self._build_events()
        nav = self.nav_bar(self, "home")
        nav.grid(row=3, column=0, sticky="ew")

        self._poll()

    # ------------------------------------------------------------------ #
    # Header                                                               #
    # ------------------------------------------------------------------ #

    def _build_header(self):
        hdr = tk.Frame(self, bg=self.dim)
        hdr.grid(row=0, column=0, sticky="ew", padx=0, pady=0)

        self._lbl_icon = tk.Label(hdr, text="◉", font=self.font_large,
                                  fg=self.accent, bg=self.dim)
        self._lbl_icon.pack(side="left", padx=(8, 4))

        self._lbl_title = tk.Label(hdr, text="MESH-PI",
                                   font=self.font_large, fg=self.fg, bg=self.dim)
        self._lbl_title.pack(side="left")

        self._lbl_nodename = tk.Label(hdr, text="",
                                      font=self.font_small, fg=self.fg, bg=self.dim)
        self._lbl_nodename.pack(side="right", padx=8)

    # ------------------------------------------------------------------ #
    # Stats grid                                                           #
    # ------------------------------------------------------------------ #

    def _build_stats(self):
        frame = tk.Frame(self, bg=self.bg)
        frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        frame.columnconfigure(1, weight=1)

        rows = [
            ("STATO",   "_val_stato"),
            ("NODI",    "_val_nodi"),
            ("RSSI",    "_val_rssi"),
            ("SNR",     "_val_snr"),
            ("HOP",     "_val_hop"),
            ("UPTIME",  "_val_uptime"),
        ]

        for i, (key, attr) in enumerate(rows):
            lbl_key = tk.Label(frame, text=key, font=self.font_bold,
                               fg=self.dim, bg=self.bg, width=8, anchor="w")
            lbl_key.grid(row=i, column=0, sticky="w", pady=1)

            lbl_val = tk.Label(frame, text="—", font=self.font_normal,
                               fg=self.fg, bg=self.bg, anchor="w")
            lbl_val.grid(row=i, column=1, sticky="w", padx=4)
            setattr(self, attr, lbl_val)

        self.separator(frame).grid(row=len(rows), column=0,
                                   columnspan=2, sticky="ew", pady=4)

    # ------------------------------------------------------------------ #
    # Events log                                                           #
    # ------------------------------------------------------------------ #

    def _build_events(self):
        frame = tk.Frame(self, bg=self.bg)
        frame.grid(row=2, column=0, sticky="nsew", padx=8)

        lbl = tk.Label(frame, text="EVENTI", font=self.font_small,
                       fg=self.dim, bg=self.bg, anchor="w")
        lbl.pack(fill="x")

        self._events_text = tk.Text(
            frame, height=3,
            font=self.font_small, fg=self.accent, bg=self.bg,
            relief="flat", state="disabled", wrap="word",
            insertbackground=self.fg,
        )
        self._events_text.pack(fill="both", expand=True)

        self.client.on_status_change(self._on_status)
        self.client.on_message(self._on_message)

    # ------------------------------------------------------------------ #
    # Callbacks                                                            #
    # ------------------------------------------------------------------ #

    def _on_status(self, msg: str):
        self._append_event(msg)

    def _on_message(self, msg):
        self._append_event(f"MSG [{msg.sender}]: {msg.text[:30]}")

    def _append_event(self, text: str):
        self._events_text.configure(state="normal")
        self._events_text.insert("end", text + "\n")
        self._events_text.see("end")
        self._events_text.configure(state="disabled")

    # ------------------------------------------------------------------ #
    # Polling refresh                                                      #
    # ------------------------------------------------------------------ #

    def _poll(self):
        self._refresh()
        self.after(self.cfg["refresh_interval_ms"], self._poll)

    def _refresh(self):
        s = self.client.stats
        connected = self.client.connected
        n_nodes = len(self.client.nodes)

        # Node name in header
        name = self.client.my_node_name or self.cfg.get("node_name", "")
        self._lbl_nodename.config(text=name)

        # Status
        if connected:
            self._val_stato.config(text="● CONNESSO", fg=self.accent)
        else:
            self._val_stato.config(text="○ DISCONNESSO", fg=self.err)

        # Node count with bar
        bar = "█" * min(n_nodes, 10)
        self._val_nodi.config(text=f"{bar}  {n_nodes}")

        # Radio metrics
        rssi_color = self._rssi_color(s.rssi)
        self._val_rssi.config(text=f"{s.rssi} dBm", fg=rssi_color)
        self._val_snr.config(text=f"{s.snr:.1f} dB")
        self._val_hop.config(text=str(s.hops))

        # Uptime
        elapsed = int(time.time() - self._start_time)
        h, rem = divmod(elapsed, 3600)
        m, sec = divmod(rem, 60)
        self._val_uptime.config(text=f"{h:02d}:{m:02d}:{sec:02d}")

    def _rssi_color(self, rssi: int) -> str:
        if rssi >= -80:
            return self.accent
        if rssi >= -100:
            return "#ffcc00"
        return self.err
