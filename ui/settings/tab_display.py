"""
Tab Display — placeholder per impostazioni font e colori.
"""

import tkinter as tk


class TabDisplay(tk.Frame):
    """Placeholder: font e colori — in arrivo."""

    def __init__(self, parent, colors: dict, fonts: dict, cfg: dict, **kw):
        super().__init__(parent, bg=colors["bg"], **kw)
        self.colors = colors
        self.fonts = fonts

        tk.Label(
            self, text="Font e colori -- in arrivo",
            font=fonts["bold"], fg=colors["fg"], bg=colors["bg"],
        ).pack(expand=True)
