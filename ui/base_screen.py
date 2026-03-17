"""
BaseScreen — shared Tkinter frame used by all screens.

Every screen inherits from this class and gets:
  - self.cfg       : settings dict
  - self.client    : MeshtasticClient
  - self.navigate  : callable(screen_name) for screen switching
  - self.keyboard  : OnScreenKeyboard (shared, set by App after build)
  - colour helpers : bg, fg, accent, dim, err
  - font helpers   : font_large, font_normal, font_small (monospace)

Touch input:
  Call self.bind_touch_entry(entry_widget) on any Entry to make the
  on-screen keyboard pop up automatically when the field is tapped.
"""

import tkinter as tk


class BaseScreen(tk.Frame):

    def __init__(self, parent, cfg: dict, client, navigate):
        super().__init__(parent, bg=cfg["bg_color"])
        self.cfg = cfg
        self.client = client
        self.navigate = navigate
        self.keyboard = None   # injected by App after all screens are built

        # Colours
        self.bg = cfg["bg_color"]
        self.fg = cfg["fg_color"]
        self.accent = cfg["accent_color"]
        self.dim = cfg["dim_color"]
        self.err = cfg["error_color"]

        # Fonts (monospace — terminal look)
        self.font_large = ("Courier", cfg["font_size_large"], "bold")
        self.font_normal = ("Courier", cfg["font_size_normal"])
        self.font_small = ("Courier", cfg["font_size_small"])
        self.font_bold = ("Courier", cfg["font_size_normal"], "bold")

        self.build()

    def build(self):
        """Override in subclasses to construct the screen layout."""
        pass

    def on_enter(self):
        """Called every time this screen becomes active."""
        pass

    def on_leave(self):
        """Called when this screen is hidden."""
        pass

    # ------------------------------------------------------------------ #
    # Widget helpers                                                       #
    # ------------------------------------------------------------------ #

    def label(self, parent, text="", font=None, fg=None, **kw) -> tk.Label:
        return tk.Label(
            parent, text=text,
            font=font or self.font_normal,
            fg=fg or self.fg,
            bg=self.bg,
            **kw
        )

    def button(self, parent, text, command, width=8, active=False) -> tk.Button:
        fg = self.bg if active else self.fg
        bg = self.accent if active else self.dim
        return tk.Button(
            parent, text=text, command=command,
            font=self.font_bold,
            fg=fg, bg=bg,
            activeforeground=self.bg, activebackground=self.fg,
            relief="flat", bd=0,
            width=width, pady=4,
        )

    def bind_touch_entry(self, entry: tk.Entry) -> None:
        """
        Attach on-screen keyboard behaviour to an Entry widget.

        - FocusIn  → show keyboard
        - FocusOut → hide keyboard (unless focus moved to the keyboard itself)
        - <Return> → hide keyboard
        """
        def _show(_event):
            if self.keyboard:
                self.keyboard.show(entry)

        def _hide(_event):
            # Small delay so the keyboard's own buttons can receive the click
            # before we decide to hide.
            entry.after(150, _maybe_hide)

        def _maybe_hide():
            if self.keyboard and self.keyboard.is_visible():
                focused = entry.focus_get()
                # Keep visible if focus is still on the entry or inside keyboard
                if focused is entry:
                    return
                if focused and str(focused).startswith(
                        str(self.keyboard._win)):
                    return
                self.keyboard.hide()

        def _enter_key(_event):
            if self.keyboard:
                self.keyboard.hide()

        entry.bind("<FocusIn>",  _show,     add="+")
        entry.bind("<FocusOut>", _hide,     add="+")
        entry.bind("<Return>",   _enter_key, add="+")

    def separator(self, parent, **kw) -> tk.Frame:
        return tk.Frame(parent, bg=self.dim, height=1, **kw)

    def nav_bar(self, parent, current: str) -> tk.Frame:
        """Bottom navigation bar shared across screens."""
        bar = tk.Frame(parent, bg=self.dim)
        screens = [
            ("HOME", "home"),
            ("CHAT", "chat"),
            ("NODI", "nodes"),
            ("DEBUG", "debug"),
        ]
        for label, name in screens:
            active = name == current
            btn = self.button(bar, label, lambda n=name: self.navigate(n),
                              width=6, active=active)
            btn.pack(side="left", expand=True, fill="x", padx=1, pady=1)
        return bar
