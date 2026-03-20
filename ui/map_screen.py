"""
Map screen — offline node map visualisation.

Layout (480×320):
  ┌─────────────────────────────────────────────┐
  │  ⊕ MAPPA NODI               ● 3 nodi  OK   │  ← topbar (row 0)
  ├─────────────────────────────────────────────┤
  │                                             │
  │         [map area — tiles or canvas]    [+] │
  │                                         [-] │
  │              ◎ ALFA  ◎ BRAV             [⊞] │
  ├─────────────────────────────────────────────┤
  │  ◎ Base Alpha  RSSI -85  SNR 7.5  80%  0 h  │  ← info card (hidden unless node selected)
  ├─────────────────────────────────────────────┤
  │  ⌂ HOME  ✉ CHAT  ◉ NODI  ⊕ MAPPA  ≡ DEBUG  │  ← nav (row 2 or 3)
  └─────────────────────────────────────────────┘

Two render backends (selected at import time):

  1. TkinterMapView  (pip install tkintermapview)
     – Renders OSM tiles from an SQLite cache (offline) or live
     – Supports touch pan, zoom scroll
     – Node markers are set_marker() calls

  2. Canvas fallback  (pure Tkinter, always works)
     – Web Mercator projection drawn on tk.Canvas
     – No tiles — dark background with grid lines
     – Touch pan (click+drag), zoom buttons (+/-)
     – Node markers are Canvas ovals + text
"""

import math
import logging
import tkinter as tk
from datetime import datetime

from .base_screen import BaseScreen
from .icons import DOT_ON, DOT_OFF, ICON_MAP

logger = logging.getLogger(__name__)

# ── optional tkintermapview ────────────────────────────────────────────────
try:
    from tkintermapview import TkinterMapView as _TkMapView
    MAPVIEW_OK = True
    logger.info("tkintermapview available — tile map enabled")
except ImportError:
    MAPVIEW_OK = False
    logger.info("tkintermapview not found — using canvas fallback")


# ── Mercator helpers ───────────────────────────────────────────────────────

def _merc_x(lon: float, zoom: int, tile_px: int = 256) -> float:
    """Pixel X for longitude at given zoom."""
    return (lon + 180.0) / 360.0 * (2 ** zoom) * tile_px


def _merc_y(lat: float, zoom: int, tile_px: int = 256) -> float:
    """Pixel Y for latitude at given zoom (Web Mercator)."""
    lat_r = math.radians(max(-85.0, min(85.0, lat)))
    return (1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi) \
           / 2.0 * (2 ** zoom) * tile_px


def _fit_bounds(nodes, margin: float = 0.15):
    """
    Return (center_lat, center_lon, zoom) that fits all nodes.
    Uses a simple lat/lon span → zoom heuristic.
    """
    coords = [(n.latitude, n.longitude) for n in nodes
              if n.latitude != 0.0 or n.longitude != 0.0]
    if not coords:
        return 45.0, 10.0, 5

    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    clat = (min(lats) + max(lats)) / 2
    clon = (min(lons) + max(lons)) / 2

    span = max(max(lats) - min(lats), max(lons) - min(lons)) * (1 + margin)
    if span < 0.001:
        return clat, clon, 15
    # approximate zoom from span
    zoom = max(1, min(17, round(math.log2(360.0 / max(span, 0.001))) + 1))
    return clat, clon, zoom


# ── Map screen ─────────────────────────────────────────────────────────────

class MapScreen(BaseScreen):

    def build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)   # map area expands

        self._selected_node = None
        self._info_visible  = False

        # ── read map config ────────────────────────────────────────────
        mcfg = self.cfg.get("map", {})
        self._tile_cache  = mcfg.get("tile_cache_path", "/tmp/map_tiles.db")
        self._tile_server = mcfg.get("tile_server",
                                     "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
        self._zoom        = int(mcfg.get("default_zoom", 12))
        self._center_lat  = float(mcfg.get("default_lat", 45.619))
        self._center_lon  = float(mcfg.get("default_lon", 10.670))

        self._build_topbar()
        self._build_map_area()
        self._build_info_card()
        nav = self.nav_bar(self, "map")
        nav.grid(row=3, column=0, sticky="ew")

        # Subscribe to node updates (re-draw markers live)
        self.client.on_node_update(
            lambda node: self.after(0, self._refresh_markers))

        self._poll()

    # ------------------------------------------------------------------ #
    # Top bar                                                              #
    # ------------------------------------------------------------------ #

    def _build_topbar(self):
        bar = tk.Frame(self, bg=self.topbar)
        bar.grid(row=0, column=0, sticky="ew")

        tk.Label(bar, text=f"{ICON_MAP} MAPPA NODI", font=self.f_bold,
                 fg=self.fg, bg=self.topbar).pack(side="left", padx=8, pady=4)

        self._lbl_status = tk.Label(bar, text="", font=self.f_small,
                                    fg=self.online, bg=self.topbar)
        self._lbl_status.pack(side="right", padx=(4, 8))

        self._lbl_count = tk.Label(bar, text="", font=self.f_small,
                                   fg=self.fg, bg=self.topbar)
        self._lbl_count.pack(side="right", padx=2)

    # ------------------------------------------------------------------ #
    # Map area                                                             #
    # ------------------------------------------------------------------ #

    def _build_map_area(self):
        outer = tk.Frame(self, bg=self.bg)
        outer.grid(row=1, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        if MAPVIEW_OK:
            self._build_tile_map(outer)
        else:
            self._build_canvas_map(outer)

        self._build_zoom_buttons(outer)

    # ── Tile map (tkintermapview) ──────────────────────────────────────

    def _build_tile_map(self, parent):
        self._map_widget = _TkMapView(
            parent,
            width=self.cfg["display_width"],
            height=200,
            corner_radius=0,
            use_database_only=True,
            database_path=self._tile_cache,
        )
        self._map_widget.grid(row=0, column=0, sticky="nsew")
        self._map_widget.set_position(self._center_lat, self._center_lon)
        self._map_widget.set_zoom(self._zoom)

        # Tap on map clears selection
        self._map_widget.add_left_click_map_command(
            lambda coords: self._select_node(None))

        self._tile_markers: dict[str, object] = {}

    def _refresh_tile_markers(self):
        nodes = self.client.get_nodes()
        existing = set(self._tile_markers.keys())
        visible  = set()

        for node in nodes:
            if node.latitude == 0.0 and node.longitude == 0.0:
                continue
            nid = node.node_id
            visible.add(nid)
            color = self._node_color(node)

            if nid in self._tile_markers:
                try:
                    self._tile_markers[nid].delete()
                except Exception:
                    pass

            marker = self._map_widget.set_marker(
                node.latitude, node.longitude,
                text=node.short_name,
                marker_color_circle=color,
                marker_color_outside=self.topbar,
                text_color=self.fg,
                command=lambda m, n=node: self._select_node(n),
            )
            self._tile_markers[nid] = marker

        # Remove stale markers
        for nid in existing - visible:
            try:
                self._tile_markers.pop(nid).delete()
            except Exception:
                pass

    # ── Canvas fallback map ────────────────────────────────────────────

    def _build_canvas_map(self, parent):
        self._canvas = tk.Canvas(
            parent,
            bg="#12151A",
            highlightthickness=0,
            cursor="crosshair",
        )
        self._canvas.grid(row=0, column=0, sticky="nsew")

        # Pan state
        self._pan_start_x = 0
        self._pan_start_y = 0
        self._canvas.bind("<ButtonPress-1>",   self._pan_start)
        self._canvas.bind("<B1-Motion>",        self._pan_move)
        self._canvas.bind("<ButtonRelease-1>",  self._pan_end)
        self._canvas.bind("<Configure>",        lambda _e: self._draw_canvas())

        self._canvas_nodes: dict[str, tuple] = {}   # nid → (item_ids)
        self._pan_dragged = False

    def _canvas_to_screen(self, lat: float, lon: float) -> tuple[float, float]:
        """Convert lat/lon to canvas pixel coords given current center/zoom."""
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        if w < 4 or h < 4:
            return 0.0, 0.0
        cx = _merc_x(self._center_lon, self._zoom)
        cy = _merc_y(self._center_lat, self._zoom)
        px = _merc_x(lon, self._zoom) - cx + w / 2
        py = _merc_y(lat, self._zoom) - cy + h / 2
        return px, py

    def _screen_to_latlon(self, px: float, py: float) -> tuple[float, float]:
        """Convert canvas pixel coords back to lat/lon."""
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        cx = _merc_x(self._center_lon, self._zoom)
        cy = _merc_y(self._center_lat, self._zoom)
        mx = cx + (px - w / 2)
        my = cy + (py - h / 2)
        n = 2 ** self._zoom * 256
        lon = mx / n * 360.0 - 180.0
        lat_r = math.atan(math.sinh(math.pi * (1 - 2 * my / n)))
        return math.degrees(lat_r), lon

    def _draw_canvas(self):
        c = self._canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 4 or h < 4:
            return

        # Grid lines (graticule) — one line every ~40px at current zoom
        grid_deg = 360.0 / (2 ** self._zoom) * (40 / 256)
        if grid_deg > 0:
            # Vertical lon lines
            import math
            lon_start = math.floor(self._center_lon / grid_deg) * grid_deg - grid_deg * 3
            for i in range(20):
                lon = lon_start + i * grid_deg
                px, _ = self._canvas_to_screen(self._center_lat, lon)
                if 0 <= px <= w:
                    c.create_line(px, 0, px, h, fill="#1E2530", width=1)

            # Horizontal lat lines
            lat_start = math.floor(self._center_lat / grid_deg) * grid_deg - grid_deg * 3
            for i in range(20):
                lat = lat_start + i * grid_deg
                if not (-85 < lat < 85):
                    continue
                _, py = self._canvas_to_screen(lat, self._center_lon)
                if 0 <= py <= h:
                    c.create_line(0, py, w, py, fill="#1E2530", width=1)

        # Cross-hair at center
        cx, cy = w / 2, h / 2
        c.create_line(cx - 8, cy, cx + 8, cy, fill=self.dim, width=1)
        c.create_line(cx, cy - 8, cx, cy + 8, fill=self.dim, width=1)

        # Zoom level label
        c.create_text(4, 4, text=f"z{self._zoom}", anchor="nw",
                      fill=self.dim, font=self.f_mono_s)

        # Node markers
        nodes = self.client.get_nodes()
        self._canvas_nodes = {}
        for node in nodes:
            if node.latitude == 0.0 and node.longitude == 0.0:
                continue
            px, py = self._canvas_to_screen(node.latitude, node.longitude)
            # Only draw if within canvas bounds (with a margin)
            if not (-30 <= px <= w + 30 and -30 <= py <= h + 30):
                continue
            color = self._node_color(node)
            is_sel = (self._selected_node and
                      self._selected_node.node_id == node.node_id)
            r = 9 if is_sel else 6
            outline = self.fg if is_sel else color
            circle = c.create_oval(px - r, py - r, px + r, py + r,
                                   fill=color, outline=outline, width=2)
            label = c.create_text(px, py - r - 6,
                                  text=node.short_name,
                                  fill=self.fg, font=self.f_small,
                                  anchor="s")
            self._canvas_nodes[node.node_id] = (circle, label, node)

        # Bind click to node selection
        c.tag_bind("all", "<ButtonRelease-1>", self._canvas_click)

    def _canvas_click(self, event):
        if self._pan_dragged:
            return
        # Find closest node within 16px
        closest = None
        best_dist = 16.0
        for nid, (circle, label, node) in self._canvas_nodes.items():
            px, py = self._canvas_to_screen(node.latitude, node.longitude)
            d = math.hypot(event.x - px, event.y - py)
            if d < best_dist:
                best_dist = d
                closest = node
        self._select_node(closest)

    def _pan_start(self, event):
        self._pan_start_x = event.x
        self._pan_start_y = event.y
        self._pan_dragged  = False

    def _pan_move(self, event):
        dx = event.x - self._pan_start_x
        dy = event.y - self._pan_start_y
        if abs(dx) > 3 or abs(dy) > 3:
            self._pan_dragged = True
        # Update center from drag
        clat, clon = self._screen_to_latlon(
            self._canvas.winfo_width()  / 2 - dx,
            self._canvas.winfo_height() / 2 - dy,
        )
        self._center_lat = max(-85.0, min(85.0, clat))
        self._center_lon = ((clon + 180) % 360) - 180
        self._pan_start_x = event.x
        self._pan_start_y = event.y
        self._draw_canvas()

    def _pan_end(self, event):
        pass

    def _refresh_canvas_markers(self):
        self._draw_canvas()

    # ── Common marker refresh dispatcher ──────────────────────────────

    def _refresh_markers(self):
        if MAPVIEW_OK:
            self._refresh_tile_markers()
        else:
            self._refresh_canvas_markers()

    # ------------------------------------------------------------------ #
    # Zoom / Fit buttons                                                   #
    # ------------------------------------------------------------------ #

    def _build_zoom_buttons(self, parent):
        btn_frame = tk.Frame(parent, bg=self.bg)
        btn_frame.grid(row=0, column=0, sticky="ne", padx=4, pady=4)

        def _zoom_in():
            self._zoom = min(18, self._zoom + 1)
            self._apply_zoom()

        def _zoom_out():
            self._zoom = max(1, self._zoom - 1)
            self._apply_zoom()

        def _fit():
            nodes = [n for n in self.client.get_nodes()
                     if n.latitude != 0.0 or n.longitude != 0.0]
            if not nodes:
                return
            lat, lon, zoom = _fit_bounds(nodes)
            self._center_lat = lat
            self._center_lon = lon
            self._zoom = zoom
            self._apply_zoom()

        _btn_cfg = dict(font=self.f_bold, fg=self.fg, bg=self.card,
                        activeforeground=self.bg, activebackground=self.fg,
                        relief="flat", bd=0, width=2, pady=2)

        tk.Button(btn_frame, text="+", command=_zoom_in,  **_btn_cfg).pack(pady=(0, 1))
        tk.Button(btn_frame, text="−", command=_zoom_out, **_btn_cfg).pack(pady=(0, 1))
        tk.Button(btn_frame, text="⊞", command=_fit,      **_btn_cfg).pack()

    def _apply_zoom(self):
        if MAPVIEW_OK:
            self._map_widget.set_position(self._center_lat, self._center_lon)
            self._map_widget.set_zoom(self._zoom)
            self._refresh_tile_markers()
        else:
            self._draw_canvas()

    # ------------------------------------------------------------------ #
    # Node info card                                                       #
    # ------------------------------------------------------------------ #

    def _build_info_card(self):
        self._info_card = tk.Frame(self, bg=self.card,
                                   highlightthickness=1,
                                   highlightbackground=self.cfg["accent_dark_color"])
        # Not gridded initially — shown on node selection

        inner = tk.Frame(self._info_card, bg=self.card)
        inner.pack(fill="x", padx=8, pady=4)
        inner.columnconfigure(1, weight=1)

        # Close button
        tk.Button(inner, text="✕", font=self.f_small,
                  fg=self.dim, bg=self.card,
                  activeforeground=self.bg, activebackground=self.dim,
                  relief="flat", bd=0,
                  command=lambda: self._select_node(None)
                  ).grid(row=0, column=2, rowspan=2, sticky="ne", padx=(4, 0))

        self._info_name  = tk.Label(inner, text="", font=self.f_bold,
                                    fg=self.fg, bg=self.card, anchor="w")
        self._info_name.grid(row=0, column=0, columnspan=2, sticky="w")

        self._info_stats = tk.Label(inner, text="", font=self.f_mono_s,
                                    fg=self.dim, bg=self.card, anchor="w")
        self._info_stats.grid(row=1, column=0, columnspan=2, sticky="w")

    def _select_node(self, node):
        self._selected_node = node
        if node is None:
            if self._info_visible:
                self._info_card.grid_forget()
                self._info_visible = False
        else:
            self._update_info_card(node)
            if not self._info_visible:
                self._info_card.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 2))
                self._info_visible = True
        if not MAPVIEW_OK:
            self._draw_canvas()

    def _update_info_card(self, node):
        age = int(node.seconds_since_heard)
        if age < 60:
            age_str = f"{age}s fa"
        elif age < 3600:
            age_str = f"{age // 60}m fa"
        else:
            age_str = f"{age // 3600}h fa"

        bat = f"  🔋{node.battery_level}%" if node.battery_level >= 0 else ""
        pos_str = f"{node.latitude:.4f},{node.longitude:.4f}"

        self._info_name.config(text=f"◎ {node.display_name}  [{node.short_name}]")
        self._info_stats.config(
            text=f"RSSI {node.rssi}  SNR {node.snr:.1f}  {node.hops}hop"
                 f"{bat}  {age_str}  {pos_str}"
        )

    # ------------------------------------------------------------------ #
    # Polling                                                              #
    # ------------------------------------------------------------------ #

    def _poll(self):
        self._refresh()
        self.after(2000, self._poll)

    def _refresh(self):
        n_nodes = len([n for n in self.client.get_nodes()
                       if n.latitude != 0.0 or n.longitude != 0.0])
        connected = self.client.connected

        if connected:
            self._lbl_status.config(text=f"{DOT_ON} OK",  fg=self.online)
        else:
            self._lbl_status.config(text=f"{DOT_OFF} OFF", fg=self.err)

        self._lbl_count.config(
            text=f"{n_nodes} nod{'o' if n_nodes == 1 else 'i'} GPS")

        self._refresh_markers()

        # Keep info card updated if a node is selected
        if self._selected_node:
            # re-fetch the latest copy of the node
            updated = self.client.nodes.get(self._selected_node.node_id)
            if updated:
                self._selected_node = updated
                self._update_info_card(updated)

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def on_enter(self):
        """Center map on nodes when screen becomes active."""
        nodes = [n for n in self.client.get_nodes()
                 if n.latitude != 0.0 or n.longitude != 0.0]
        if nodes:
            lat, lon, zoom = _fit_bounds(nodes)
            self._center_lat = lat
            self._center_lon = lon
            self._zoom = zoom
            self._apply_zoom()

    def on_scroll(self, direction: int):
        """Encoder rotation zooms in/out."""
        if direction < 0:
            self._zoom = min(18, self._zoom + 1)
        else:
            self._zoom = max(1, self._zoom - 1)
        self._apply_zoom()

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _node_color(self, node) -> str:
        """Color based on signal quality."""
        if node.rssi >= -85:  return self.online
        if node.rssi >= -100: return self.warn
        return self.err
