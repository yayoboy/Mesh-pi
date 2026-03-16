"""
Nodes screen — list of visible nodes with signal info.

Layout (480×320):
  ┌─────────────────────────────────────┐
  │  NODI IN RETE              [aggiorna]│
  ├─────────────────────────────────────┤
  │  ◉ Base Alpha    ALFA  -85dBm  0hop │
  │  ◉ Patrol Bravo  BRAV  -102dBm 1hop │
  │  ○ Relay Charlie CHAR  -78dBm  0hop │
  │  …                                  │
  ├─────────────────────────────────────┤
  │ [HOME] [CHAT] [NODI] [DEBUG]        │
  └─────────────────────────────────────┘
"""

import tkinter as tk
from datetime import datetime
from .base_screen import BaseScreen


class NodesScreen(BaseScreen):

    def build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_header()
        self._build_list()
        nav = self.nav_bar(self, "nodes")
        nav.grid(row=2, column=0, sticky="ew")

        self.client.on_node_update(self._on_node_update)

    # ------------------------------------------------------------------ #
    # Header                                                               #
    # ------------------------------------------------------------------ #

    def _build_header(self):
        hdr = tk.Frame(self, bg=self.dim)
        hdr.grid(row=0, column=0, sticky="ew")

        tk.Label(hdr, text="NODI IN RETE", font=self.font_large,
                 fg=self.fg, bg=self.dim).pack(side="left", padx=8, pady=2)

        self._lbl_count = tk.Label(hdr, text="", font=self.font_small,
                                   fg=self.accent, bg=self.dim)
        self._lbl_count.pack(side="right", padx=(0, 8))

        self.button(hdr, "↺", self._refresh_nodes, width=3
                    ).pack(side="right", padx=4)

    # ------------------------------------------------------------------ #
    # Node list                                                            #
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
                          bg=self.dim, troughcolor=self.bg, width=8)
        sb.grid(row=0, column=1, sticky="ns")
        self._canvas.config(yscrollcommand=sb.set)

        self._inner = tk.Frame(self._canvas, bg=self.bg)
        self._window = self._canvas.create_window((0, 0), window=self._inner,
                                                  anchor="nw")
        self._inner.bind("<Configure>", self._on_inner_resize)
        self._canvas.bind("<Configure>", self._on_canvas_resize)

        self._node_rows: dict[str, tk.Frame] = {}

    def _on_inner_resize(self, _event):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, event):
        self._canvas.itemconfig(self._window, width=event.width)

    # ------------------------------------------------------------------ #
    # Callbacks                                                            #
    # ------------------------------------------------------------------ #

    def on_enter(self):
        self._refresh_nodes()

    def _on_node_update(self, node):
        self._inner.after(0, self._refresh_nodes)

    def _refresh_nodes(self):
        nodes = self.client.get_nodes()

        # Remove stale rows
        seen = {n.node_id for n in nodes}
        for nid in list(self._node_rows.keys()):
            if nid not in seen:
                self._node_rows.pop(nid).destroy()

        # Add / update rows
        for i, node in enumerate(sorted(nodes, key=lambda n: n.rssi, reverse=True)):
            if node.node_id in self._node_rows:
                self._update_row(self._node_rows[node.node_id], node)
            else:
                row = self._create_row(node)
                row.pack(fill="x", padx=4, pady=1)
                self._node_rows[node.node_id] = row

        self._lbl_count.config(text=f"{len(nodes)} nodi")

    def _create_row(self, node) -> tk.Frame:
        row = tk.Frame(self._inner, bg="#111111", padx=4, pady=3)
        row.columnconfigure(1, weight=1)

        # Status dot
        dot = tk.Label(row, text="◉", font=self.font_bold,
                       fg=self._signal_color(node.rssi), bg="#111111")
        dot.grid(row=0, column=0, padx=(0, 6))
        row._dot = dot

        # Name
        name_lbl = tk.Label(row, text=node.display_name, font=self.font_bold,
                            fg=self.fg, bg="#111111", anchor="w")
        name_lbl.grid(row=0, column=1, sticky="w")
        row._name = name_lbl

        # Short name
        short_lbl = tk.Label(row, text=node.short_name, font=self.font_small,
                             fg=self.dim, bg="#111111", width=6, anchor="w")
        short_lbl.grid(row=0, column=2)
        row._short = short_lbl

        # RSSI
        rssi_lbl = tk.Label(row, text=f"{node.rssi} dBm",
                            font=self.font_small,
                            fg=self._signal_color(node.rssi), bg="#111111",
                            width=9, anchor="e")
        rssi_lbl.grid(row=0, column=3)
        row._rssi = rssi_lbl

        # Hops
        hop_lbl = tk.Label(row, text=f"{node.hops}hop",
                           font=self.font_small, fg=self.dim, bg="#111111",
                           width=5, anchor="e")
        hop_lbl.grid(row=0, column=4, padx=(0, 4))
        row._hop = hop_lbl

        # Age (seconds since heard)
        age_lbl = tk.Label(row, text="", font=self.font_small,
                           fg=self.dim, bg="#111111", width=6, anchor="e")
        age_lbl.grid(row=0, column=5)
        row._age = age_lbl

        row._node = node
        self._schedule_age_update(row)
        return row

    def _update_row(self, row, node):
        color = self._signal_color(node.rssi)
        row._dot.config(fg=color)
        row._name.config(text=node.display_name)
        row._short.config(text=node.short_name)
        row._rssi.config(text=f"{node.rssi} dBm", fg=color)
        row._hop.config(text=f"{node.hops}hop")
        row._node = node

    def _schedule_age_update(self, row):
        def _tick():
            if not row.winfo_exists():
                return
            sec = int(row._node.seconds_since_heard)
            if sec < 60:
                age_str = f"{sec}s"
            elif sec < 3600:
                age_str = f"{sec // 60}m"
            else:
                age_str = f"{sec // 3600}h"
            row._age.config(text=age_str)
            row.after(5000, _tick)
        _tick()

    def _signal_color(self, rssi: int) -> str:
        if rssi >= -80:
            return self.accent
        if rssi >= -100:
            return "#ffcc00"
        return self.err
