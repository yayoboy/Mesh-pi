"""
ui/keyboard.py — On-screen keyboard for touchscreen input.

Appears as a frameless Toplevel anchored to the bottom of the root window.
Designed for 480×320 displays: 5 key rows, each key ~44×36 px.

Usage (automatic via BaseScreen.bind_touch_entry):

    self.bind_touch_entry(self._entry)

The keyboard attaches itself to the focused Entry, inserts/deletes
characters on tap, and hides on OK or when focus moves away.

Layouts:
  alpha  → QWERTY lowercase + ⌫ + OK
  ALPHA  → QWERTY uppercase
  num    → numbers, symbols, punctuation
"""

import tkinter as tk
from typing import Optional


# ── Key layout definitions ─────────────────────────────────────────────────

_ALPHA_ROWS = [
    ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
    ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
    ["⇧", "z", "x", "c", "v", "b", "n", "m", "⌫"],
    ["123", " ", " ", " ", " ", " ", " ", "OK"],
]

_UPPER_ROWS = [
    ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
    ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
    ["⇩", "Z", "X", "C", "V", "B", "N", "M", "⌫"],
    ["123", " ", " ", " ", " ", " ", " ", "OK"],
]

_NUM_ROWS = [
    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
    ["-", "/", ":", ";", "(", ")", "$", "&", "@"],
    [".", ",", "?", "!", "'", "\"", "_", "#", "⌫"],
    ["abc", " ", " ", " ", " ", " ", " ", "OK"],
]

# Key width weights: special keys span multiple units
_SPACE_WEIGHT = 5   # space bar spans this many normal-key widths
_KEY_H = 36         # key height in pixels
_PAD = 3            # gap between keys


class OnScreenKeyboard:
    """
    Singleton-style on-screen keyboard attached to the Tkinter root.

    Create once in App, then call show(entry_widget) / hide().
    """

    def __init__(self, root: tk.Tk, cfg: dict):
        self._root = root
        self._cfg = cfg
        self._target: Optional[tk.Entry] = None
        self._layout = "alpha"

        self._win = tk.Toplevel(root)
        self._win.overrideredirect(True)       # no title bar
        self._win.configure(bg=cfg["bg_color"])
        self._win.withdraw()                   # hidden initially

        self._frame = tk.Frame(self._win, bg=cfg["bg_color"])
        self._frame.pack(fill="both", expand=True)

        self._build()
        root.bind("<Configure>", self._on_root_move, add="+")

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def show(self, entry: tk.Entry) -> None:
        self._target = entry
        self._reposition()
        self._win.deiconify()
        self._win.lift()

    def hide(self) -> None:
        self._win.withdraw()
        self._target = None

    def is_visible(self) -> bool:
        return self._win.state() != "withdrawn"

    # ------------------------------------------------------------------ #
    # Build keyboard frame                                                 #
    # ------------------------------------------------------------------ #

    def _build(self) -> None:
        for w in self._frame.winfo_children():
            w.destroy()

        rows = {
            "alpha": _ALPHA_ROWS,
            "ALPHA": _UPPER_ROWS,
            "num":   _NUM_ROWS,
        }[self._layout]

        cfg = self._cfg
        bg  = cfg["bg_color"]
        fg  = cfg["fg_color"]
        acc = cfg["accent_color"]
        dim = cfg["dim_color"]
        font_key   = ("Courier", 13, "bold")
        font_small = ("Courier", 10)

        display_w = cfg["display_width"]
        n_units_per_row = 10   # normal row has 10 keys → each unit = display_w / 10

        unit = (display_w - _PAD) // n_units_per_row

        for row_idx, keys in enumerate(rows):
            row_frame = tk.Frame(self._frame, bg=bg)
            row_frame.pack(fill="x", pady=(_PAD, 0))

            is_last_row = row_idx == len(rows) - 1

            # Build key list expanding the space bar
            expanded: list[tuple[str, int]] = []   # (label, weight)
            for k in keys:
                if k == " ":
                    # accumulate space bar
                    if expanded and expanded[-1][0] == " ":
                        expanded[-1] = (" ", expanded[-1][1] + 1)
                    else:
                        expanded.append((" ", 1))
                else:
                    expanded.append((k, 1))

            for label, weight in expanded:
                w = unit * weight - _PAD

                is_special = label in ("⌫", "⇧", "⇩", "OK", "123", "abc")
                is_space   = label == " "

                if label == "OK":
                    key_bg, key_fg = acc, bg
                    key_font = font_key
                elif is_special:
                    key_bg, key_fg = dim, fg
                    key_font = font_small
                else:
                    key_bg, key_fg = "#1a1a1a", fg
                    key_font = font_key

                btn = tk.Button(
                    row_frame,
                    text=label if not is_space else "",
                    font=key_font,
                    fg=key_fg, bg=key_bg,
                    activeforeground=bg, activebackground=fg,
                    relief="flat", bd=0,
                    width=w // 10,          # approximate char width
                    height=1,
                    command=lambda lbl=label: self._on_key(lbl),
                )
                # Override with explicit pixel width via place-in-frame trick
                btn.pack(side="left", padx=(_PAD, 0))
                btn.config(width=0)
                btn.pack_forget()

                # Use a fixed-width Frame wrapper for precise pixel sizing
                cell = tk.Frame(row_frame, width=w, height=_KEY_H, bg=bg)
                cell.pack_propagate(False)
                cell.pack(side="left", padx=(_PAD, 0))

                btn2 = tk.Button(
                    cell,
                    text=label if not is_space else "space" if weight >= 3 else "",
                    font=key_font,
                    fg=key_fg, bg=key_bg,
                    activeforeground=bg, activebackground=fg,
                    relief="flat", bd=0,
                    command=lambda lbl=label: self._on_key(lbl),
                )
                btn2.place(relwidth=1.0, relheight=1.0)

    # ------------------------------------------------------------------ #
    # Key handler                                                          #
    # ------------------------------------------------------------------ #

    def _on_key(self, label: str) -> None:
        if label == "OK":
            self.hide()
            if self._target:
                self._target.event_generate("<Return>")
            return

        if label == "⌫":
            if self._target:
                cur = self._target.index(tk.INSERT)
                if cur > 0:
                    self._target.delete(cur - 1, cur)
            return

        if label in ("⇧", "⇩"):
            self._layout = "ALPHA" if self._layout == "alpha" else "alpha"
            self._build()
            return

        if label == "123":
            self._layout = "num"
            self._build()
            return

        if label == "abc":
            self._layout = "alpha"
            self._build()
            return

        if label == " ":
            if self._target:
                self._insert(" ")
            return

        if self._target:
            self._insert(label)
            # Auto return to lowercase after uppercase letter
            if self._layout == "ALPHA":
                self._layout = "alpha"
                self._build()

    def _insert(self, char: str) -> None:
        if self._target:
            try:
                self._target.insert(tk.INSERT, char)
            except tk.TclError:
                pass

    # ------------------------------------------------------------------ #
    # Positioning                                                          #
    # ------------------------------------------------------------------ #

    def _reposition(self) -> None:
        self._win.update_idletasks()
        rw = self._root.winfo_rootx()
        ry = self._root.winfo_rooty()
        rh = self._root.winfo_height()
        rwidth = self._root.winfo_width()
        kh = self._win.winfo_reqheight() or (_KEY_H + _PAD) * 5

        x = rw
        y = ry + rh - kh
        self._win.geometry(f"{rwidth}x{kh}+{x}+{y}")

    def _on_root_move(self, _event) -> None:
        if self.is_visible():
            self._reposition()
