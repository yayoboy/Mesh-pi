"""
Nodes screen — Meshtastic-style node cards.

Layout (480×320):
  ┌─────────────────────────────────────────────┐
  │  ◉ NODI IN RETE                  3 online   │
  ├─────────────────────────────────────────────┤
  │  ┌───────────────────────────────────────┐  │
  │  │ ┌────┐  Base Alpha          12s fa    │  │
  │  │ │ALFA│  ▂▄▆█ -85 dBm  ⊕ direct       │  │
  │  │ └────┘  ⚡████░  80%                  │  │
  │  └───────────────────────────────────────┘  │
  │  ┌───────────────────────────────────────┐  │
  │  │ ┌────┐  Patrol Bravo        45s fa    │  │
  │  │ │BRAV│  ▂▄·· -102dBm  → 1hop         │  │
  │  │ └────┘                                │  │
  │  └───────────────────────────────────────┘  │
  ├─────────────────────────────────────────────┤
  │  ⌂ HOME   ✉ CHAT   ◉ NODI   ⚙ DEBUG        │
  └─────────────────────────────────────────────┘
"""

import tkinter as tk
from .base_screen import BaseScreen
from .icons import signal_bars, signal_bars_snr, battery_icon, hop_arrows, DOT_ON


# Palette for node avatar badges — cycles through nodes
_AVATAR_COLORS = [
    "#3D7A72", "#5B4A8A", "#8A4A3D", "#3D6A8A",
    "#8A7A3D", "#4A8A3D", "#8A3D6A", "#3D4A8A",
]


class NodesScreen(BaseScreen):

    def build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._color_map: dict[str, str] = {}
        self._color_idx = 0

        self._build_topbar()
        self._build_list()
        nav = self.nav_bar(self, "nodes")
        nav.grid(row=2, column=0, sticky="ew")

        self.client.on_node_update(self._on_node_update)

    # ------------------------------------------------------------------ #
    # Top bar                                                              #
    # ------------------------------------------------------------------ #

    def _build_topbar(self):
        bar = tk.Frame(self, bg=self.topbar)
        bar.grid(row=0, column=0, sticky="ew")

        tk.Label(bar, text=f"{DOT_ON} NODI IN RETE",
                 font=self.f_bold, fg=self.fg, bg=self.topbar
                 ).pack(side="left", padx=8, pady=4)

        self._lbl_count = tk.Label(bar, text="", font=self.f_small,
                                   fg=self.accent, bg=self.topbar)
        self._lbl_count.pack(side="right", padx=10)

        tk.Button(bar, text="↺", font=self.f_icon,
                  fg=self.dim, bg=self.topbar,
                  activeforeground=self.accent, activebackground=self.topbar,
                  relief="flat", bd=0, pady=2,
                  command=self._refresh_nodes
                  ).pack(side="right", padx=4)

    # ------------------------------------------------------------------ #
    # Scrollable node list                                                 #
    # ------------------------------------------------------------------ #

    def _build_list(self):
        container = tk.Frame(self, bg=self.bg)
        container.grid(row=1, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(container, bg=self.bg, highlightthickness=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")

        sb = tk.Scrollbar(container, orient="vertical",
                          command=self._canvas.yview,
                          bg=self.card, troughcolor=self.bg, width=6)
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

        self._node_cards: dict[str, tk.Frame] = {}

    # ------------------------------------------------------------------ #
    # Callbacks                                                            #
    # ------------------------------------------------------------------ #

    def on_enter(self):
        self._refresh_nodes()

    def on_scroll(self, direction: int):
        self._canvas.yview_scroll(direction, "units")

    def _on_node_update(self, _node):
        self._inner.after(0, self._refresh_nodes)

    def _refresh_nodes(self):
        nodes = self.client.get_nodes()
        seen = {n.node_id for n in nodes}

        # Destroy cards for gone nodes
        for nid in list(self._node_cards.keys()):
            if nid not in seen:
                self._node_cards.pop(nid).destroy()

        # Sort by SNR (always available from node db); fall back to rssi
        for node in sorted(nodes, key=lambda n: n.snr, reverse=True):
            if node.node_id in self._node_cards:
                self._update_card(self._node_cards[node.node_id], node)
            else:
                card = self._create_card(node)
                card.pack(fill="x", padx=8, pady=4)
                self._node_cards[node.node_id] = card

        n = len(nodes)
        self._lbl_count.config(
            text=f"{n} nod{'o' if n == 1 else 'i'} online")

    def _node_color(self, node_id: str) -> str:
        if node_id not in self._color_map:
            self._color_map[node_id] = \
                _AVATAR_COLORS[self._color_idx % len(_AVATAR_COLORS)]
            self._color_idx += 1
        return self._color_map[node_id]

    # ------------------------------------------------------------------ #
    # Card construction                                                    #
    # ------------------------------------------------------------------ #

    def _create_card(self, node) -> tk.Frame:
        color = self._node_color(node.node_id)

        frame = self.card(self._inner)
        frame.columnconfigure(1, weight=1)

        # ── Avatar badge ──────────────────────────────────────────────
        av = self.avatar(frame, node.short_name, color)
        av.grid(row=0, column=0, rowspan=2, padx=(8, 10), pady=8, sticky="ns")
        frame._avatar = av

        # ── Top row: name + last heard ───────────────────────────────
        name_lbl = tk.Label(frame, text=node.display_name,
                            font=self.f_bold, fg=self.fg, bg=self.card,
                            anchor="w")
        name_lbl.grid(row=0, column=1, sticky="w", pady=(6, 0))
        frame._name = name_lbl

        age_lbl = tk.Label(frame, text="", font=self.f_small,
                           fg=self.dim, bg=self.card, anchor="e")
        age_lbl.grid(row=0, column=2, sticky="e", padx=8, pady=(6, 0))
        frame._age = age_lbl

        # ── Bottom row: signal bars + RSSI + hop ─────────────────────
        sig_frame = tk.Frame(frame, bg=self.card)
        sig_frame.grid(row=1, column=1, columnspan=2, sticky="ew",
                       padx=(0, 8), pady=(0, 6))

        sig_lbl = tk.Label(sig_frame, text="", font=self.f_mono_s,
                           fg=self.accent, bg=self.card)
        sig_lbl.pack(side="left")
        frame._sig = sig_lbl

        rssi_lbl = tk.Label(sig_frame, text="", font=self.f_small,
                            fg=self.dim, bg=self.card)
        rssi_lbl.pack(side="left", padx=(6, 0))
        frame._rssi = rssi_lbl

        hop_lbl = tk.Label(sig_frame, text="", font=self.f_small,
                           fg=self.dim, bg=self.card)
        hop_lbl.pack(side="left", padx=(8, 0))
        frame._hop = hop_lbl

        bat_lbl = tk.Label(sig_frame, text="", font=self.f_small,
                           fg=self.online, bg=self.card)
        bat_lbl.pack(side="right", padx=4)
        frame._bat = bat_lbl

        frame._node = node
        self._update_card(frame, node)
        self._schedule_age(frame)
        return frame

    def _update_card(self, frame, node):
        # Prefer RSSI (from received packets) for display; fall back to SNR
        # RSSI is only known after we've received a packet from this node.
        if node.rssi != 0:
            bars  = signal_bars(node.rssi)
            color = self.rssi_color(node.rssi)
            sig_text = f"{node.rssi} dBm"
        else:
            bars  = signal_bars_snr(node.snr)
            color = self._snr_color(node.snr)
            sig_text = f"SNR {node.snr:+.1f} dB"

        frame._name.config(text=node.display_name)
        frame._sig.config(text=bars, fg=color)
        frame._rssi.config(text=sig_text)
        frame._hop.config(text=hop_arrows(node.hops))
        if hasattr(node, "battery_level") and node.battery_level >= 0:
            frame._bat.config(text=battery_icon(node.battery_level))
        else:
            frame._bat.config(text="")
        frame._node = node

    def _snr_color(self, snr: float) -> str:
        if snr > 5:    return self.online
        if snr >= 0:   return self.warn
        return self.err

    def _schedule_age(self, frame):
        def _tick():
            if not frame.winfo_exists():
                return
            sec = int(frame._node.seconds_since_heard)
            if sec < 60:
                s = f"{sec}s fa"
            elif sec < 3600:
                s = f"{sec // 60}m fa"
            else:
                s = f"{sec // 3600}h fa"
            frame._age.config(text=s)
            frame.after(5000, _tick)
        _tick()
