"""
BaseScreen — shared Tkinter frame used by all screens.

Every screen inherits from this class and gets:
  - self.cfg           : settings dict
  - self.client        : MeshtasticClient
  - self.navigate      : callable(screen_name)
  - self.keyboard      : OnScreenKeyboard (injected by App after build)
  - colour shortcuts   : bg, card, topbar, fg, dim, accent, online, warn, err
  - font shortcuts     : f_large, f_normal, f_small, f_bold, f_icon, f_mono

Touch input:
  Call self.bind_touch_entry(entry) on any Entry for automatic OSK.

Layout helpers:
  self.card(parent)        → Frame styled as a surface card
  self.chip(parent, text)  → compact status chip Label
  self.nav_bar(parent, current) → bottom navigation with icons
"""

import tkinter as tk
import tkinter.font as tkfont

from .icons import ICON_HOME, ICON_CHAT, ICON_NODES, ICON_DEBUG, ICON_SETTINGS


def _pick_font(*names: str) -> str:
    """Return the first font name that is installed on this system."""
    available = set(tkfont.families())
    for name in names:
        if name in available:
            return name
    return "TkDefaultFont"


class BaseScreen(tk.Frame):

    def __init__(self, parent, cfg: dict, client, navigate):
        super().__init__(parent, bg=cfg["bg_color"])
        self.cfg = cfg
        self.client = client
        self.navigate = navigate
        self.keyboard = None   # injected by App after all screens are built

        # ── Colours ────────────────────────────────────────────────────
        self.bg      = cfg["bg_color"]
        self.card    = cfg["card_color"]
        self.topbar  = cfg["topbar_color"]
        self.nav_bg  = cfg["nav_color"]
        self.fg      = cfg["fg_color"]
        self.dim     = cfg["fg_dim_color"]
        self.accent  = cfg["accent_color"]
        self.online  = cfg["online_color"]
        self.warn    = cfg["warning_color"]
        self.err     = cfg["error_color"]
        self.sent_bg = cfg["sent_bubble_color"]
        self.recv_bg = cfg["recv_bubble_color"]

        # ── Fonts ──────────────────────────────────────────────────────
        sans  = _pick_font(cfg.get("font_family", "DejaVu Sans"),
                           "Helvetica", "TkDefaultFont")
        mono  = _pick_font(cfg.get("font_family_mono", "DejaVu Sans Mono"),
                           "Courier", "TkFixedFont")

        # font_scale lets you compensate for display DPI vs X11-reported DPI.
        # E.g. a 3.5" 480×320 screen has ~165 DPI but X11 usually reports 96.
        # Set font_scale = 165/96 ≈ 1.72 to get the correct physical text size,
        # or leave at 1.0 to keep sizes as pixel-friendly values for the layout.
        _scale = cfg.get("font_scale", 1.0)

        def _sz(base: int) -> int:
            return max(6, round(base * _scale))

        fl = _sz(cfg["font_size_large"])
        fn = _sz(cfg["font_size_normal"])
        fs = _sz(cfg["font_size_small"])
        fi = _sz(cfg["font_size_icon"])

        self.f_large  = (sans, fl, "bold")
        self.f_normal = (sans, fn)
        self.f_small  = (sans, fs)
        self.f_bold   = (sans, fn, "bold")
        self.f_icon   = (sans, fi)
        self.f_mono   = (mono, fn)
        self.f_mono_s = (mono, fs)

        # keep legacy names so keyboard.py still works
        self.font_large  = self.f_large
        self.font_normal = self.f_normal
        self.font_small  = self.f_small
        self.font_bold   = self.f_bold

        self.build()

    def build(self):
        pass

    def on_enter(self):
        pass

    def on_leave(self):
        pass

    def on_scroll(self, direction: int):
        """
        Called by encoder rotation. direction: +1 = down, -1 = up.
        Override in screens that contain a scrollable Canvas or Text.
        """
        pass

    # ------------------------------------------------------------------ #
    # Layout helpers                                                       #
    # ------------------------------------------------------------------ #

    def card(self, parent, **kw) -> tk.Frame:
        """A slightly elevated surface card."""
        return tk.Frame(parent, bg=self.card,
                        highlightthickness=1,
                        highlightbackground=self.cfg["accent_dark_color"],
                        **kw)

    def chip(self, parent, text: str, color: str = None) -> tk.Label:
        """Small inline status badge."""
        return tk.Label(parent, text=text,
                        font=self.f_small,
                        fg=color or self.accent,
                        bg=self.card,
                        padx=5, pady=1)

    def avatar(self, parent, short_name: str, color: str = None) -> tk.Frame:
        """Coloured square badge with short node name (e.g. 'ALFA')."""
        bg = color or self.cfg["accent_dark_color"]
        box = tk.Frame(parent, bg=bg, width=36, height=36)
        box.pack_propagate(False)
        tk.Label(box, text=short_name[:4], font=self.f_bold,
                 fg=self.fg, bg=bg).place(relx=0.5, rely=0.5, anchor="center")
        return box

    def separator(self, parent, **kw) -> tk.Frame:
        return tk.Frame(parent, bg=self.cfg["accent_dark_color"], height=1, **kw)

    def button(self, parent, text, command, width=8, active=False) -> tk.Button:
        fg = self.bg  if active else self.fg
        bg = self.accent if active else self.cfg["accent_dark_color"]
        return tk.Button(
            parent, text=text, command=command,
            font=self.f_bold,
            fg=fg, bg=bg,
            activeforeground=self.bg, activebackground=self.fg,
            relief="flat", bd=0,
            width=width, pady=4,
        )

    def nav_bar(self, parent, current: str) -> tk.Frame:
        """Bottom navigation bar with Unicode icons (5 screens)."""
        bar = tk.Frame(parent, bg=self.nav_bg)
        items = [
            (f"{ICON_HOME} HOME",      "home"),
            (f"{ICON_CHAT} CHAT",      "chat"),
            (f"{ICON_NODES} NODI",     "nodes"),
            (f"{ICON_DEBUG} DEBUG",    "debug"),
            (f"{ICON_SETTINGS} CONFIG","settings"),
        ]
        for label, name in items:
            is_active = name == current
            fg = self.accent if is_active else self.dim
            btn = tk.Button(
                bar, text=label,
                font=self.f_small,
                fg=fg, bg=self.nav_bg,
                activeforeground=self.accent, activebackground=self.nav_bg,
                relief="flat", bd=0,
                pady=5,
                command=lambda n=name: self.navigate(n),
            )
            if is_active:
                # Underline indicator
                btn.configure(underline=0)
            btn.pack(side="left", expand=True, fill="x")
            # Keep a reference to the chat button for badge updates
            if name == "chat":
                self._nav_chat_btn = btn
                self._nav_chat_default = label
        # top border line
        tk.Frame(bar, bg=self.cfg["accent_dark_color"], height=1).place(
            relx=0, rely=0, relwidth=1)
        return bar

    def update_nav_badges(self, badges: dict):
        """Update badge counts on nav bar buttons (e.g. unread chat count)."""
        btn = getattr(self, "_nav_chat_btn", None)
        if btn is None:
            return
        count = badges.get("chat", 0)
        if count > 0:
            btn.config(text=f"{ICON_CHAT} {count}")
        else:
            btn.config(text=getattr(self, "_nav_chat_default",
                                    f"{ICON_CHAT} CHAT"))

    # ------------------------------------------------------------------ #
    # Touch keyboard binding                                               #
    # ------------------------------------------------------------------ #

    def bind_touch_entry(self, entry: tk.Entry) -> None:
        """Attach on-screen keyboard to an Entry widget."""
        def _show(_event):
            if self.keyboard:
                self.keyboard.show(entry)

        def _hide(_event):
            entry.after(150, _maybe_hide)

        def _maybe_hide():
            if self.keyboard and self.keyboard.is_visible():
                focused = entry.focus_get()
                if focused is entry:
                    return
                if focused and str(focused).startswith(str(self.keyboard._win)):
                    return
                self.keyboard.hide()

        def _enter_key(_event):
            if self.keyboard:
                self.keyboard.hide()

        entry.bind("<FocusIn>",  _show,      add="+")
        entry.bind("<FocusOut>", _hide,      add="+")
        entry.bind("<Return>",   _enter_key, add="+")

    # ------------------------------------------------------------------ #
    # Colour helpers                                                       #
    # ------------------------------------------------------------------ #

    def rssi_color(self, rssi: int) -> str:
        if rssi >= -85:  return self.online
        if rssi >= -100: return self.warn
        return self.err
