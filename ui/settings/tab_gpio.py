"""
Tab GPIO — lista scrollabile pin -> funzione.

Usa GPIOConfigurator e PIN_FUNCTIONS da hardware.gpio_config.
"""

import tkinter as tk

from hardware.gpio_config import GPIOConfigurator, PIN_FUNCTIONS, RESERVED_PINS


# GPIO assegnabili: da 2 a 27 esclusi i riservati
_ASSIGNABLE_PINS = sorted(p for p in range(2, 28) if p not in RESERVED_PINS)


class TabGPIO(tk.Frame):
    """Lista scrollabile pin -> funzione GPIO."""

    def __init__(self, parent, colors: dict, fonts: dict, cfg: dict, **kw):
        super().__init__(parent, bg=colors["bg"], **kw)
        self.colors = colors
        self.fonts = fonts
        self.cfg = cfg

        self._pin_vars: dict[int, tk.StringVar] = {}

        self._build(cfg)

    def _build(self, cfg: dict):
        bg = self.colors["bg"]
        card = self.colors["card"]
        fg = self.colors["fg"]
        accent = self.colors["accent"]

        # Load existing assignments from settings
        hw_cfg = cfg.get("hardware", {})
        existing = GPIOConfigurator.from_settings(hw_cfg)

        # Title
        tk.Label(
            self, text="Assegnazione Pin GPIO",
            font=self.fonts["bold"], fg=fg, bg=bg, anchor="w",
        ).pack(fill="x", padx=12, pady=(8, 4))

        # One row per assignable pin
        for pin in _ASSIGNABLE_PINS:
            row = tk.Frame(self, bg=card)
            row.pack(fill="x", padx=8, pady=1)
            row.columnconfigure(0, weight=1)

            tk.Label(
                row, text=f"GPIO {pin:2d}",
                font=self.fonts["mono"], fg=fg, bg=card, anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=(12, 4), pady=3)

            current_fn = existing.get(pin)
            var = tk.StringVar(value=current_fn)
            self._pin_vars[pin] = var

            om = tk.OptionMenu(row, var, *PIN_FUNCTIONS)
            om.configure(
                font=self.fonts["small"],
                fg=accent, bg=card,
                activeforeground=bg, activebackground=accent,
                highlightthickness=0, relief="flat", bd=0,
            )
            om["menu"].configure(
                font=self.fonts["small"],
                fg=fg, bg=card,
                activeforeground=bg, activebackground=accent,
            )
            om.grid(row=0, column=1, padx=(4, 8), pady=3)

    def get_config(self) -> GPIOConfigurator:
        """Restituisce un GPIOConfigurator con le assegnazioni correnti."""
        gc = GPIOConfigurator()
        for pin, var in self._pin_vars.items():
            fn = var.get()
            if fn != "non usato":
                gc.assign(pin, fn)
        return gc

    def validate(self) -> list[str]:
        """Restituisce lista di errori (vuota = ok)."""
        return self.get_config().validate()
