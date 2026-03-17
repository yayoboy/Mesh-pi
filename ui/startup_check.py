"""
ui/startup_check.py — Schermata diagnostica pre-avvio.

Verifica sequenzialmente: serial port → I2C bus → GPIO pin conflict.
Mostra i risultati e permette di continuare anche se qualcosa manca.
"""
import os
import tkinter as tk
from .base_screen import BaseScreen


def run_startup_checks(cfg: dict) -> list:
    """
    Esegui tutti i check hardware.
    Restituisce lista di dict: {name, ok, message}
    """
    results = []

    # Check 1: serial port
    port = cfg.get("serial_port", "/dev/ttyUSB0")
    port_ok = os.path.exists(port)
    results.append({
        "name":    f"Serial {port}",
        "ok":      port_ok,
        "message": "disponibile" if port_ok else "non trovata — verrà usata la demo mode",
    })

    # Check 2: I2C bus
    i2c_bus  = cfg.get("i2c", {}).get("bus", 1)
    i2c_path = f"/dev/i2c-{i2c_bus}"
    i2c_ok   = os.path.exists(i2c_path)
    results.append({
        "name":    f"I2C bus {i2c_path}",
        "ok":      i2c_ok,
        "message": "disponibile" if i2c_ok else "non disponibile — sensori disabilitati",
    })

    # Check 3: GPIO pin conflict
    try:
        from hardware.gpio_config import GPIOConfigurator
        gpio_cfg = GPIOConfigurator.from_settings(cfg.get("hardware", {}))
        errors   = gpio_cfg.validate()
        results.append({
            "name":    "GPIO pin conflict",
            "ok":      len(errors) == 0,
            "message": "nessun conflitto" if not errors else "; ".join(errors),
        })
    except Exception as e:
        results.append({
            "name":    "GPIO",
            "ok":      False,
            "message": str(e),
        })

    return results


class StartupCheckScreen(BaseScreen):
    """Schermata diagnostica mostrata prima dell'UI principale."""

    def build(self):
        self._on_continue = None
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Titolo
        tk.Label(
            self, text="Diagnostica Avvio",
            bg=self.bg, fg=self.fg,
            font=self.f_large,
        ).grid(row=0, column=0, pady=12)

        # Area risultati
        self._results_frame = tk.Frame(self, bg=self.bg)
        self._results_frame.grid(row=1, column=0, sticky="nsew", padx=16)

        # Bottone Continua
        btn_frame = tk.Frame(self, bg=self.bg)
        btn_frame.grid(row=2, column=0, pady=10)
        tk.Button(
            btn_frame, text="Continua",
            command=self._do_continue,
            bg=self.accent, fg=self.bg,
            font=self.f_normal, padx=20, pady=6,
            relief="flat",
        ).pack()

    def show_results(self, results: list):
        """Popola la schermata con i risultati dei check."""
        for widget in self._results_frame.winfo_children():
            widget.destroy()

        for r in results:
            row = tk.Frame(self._results_frame, bg=self.card, pady=6, padx=10)
            row.pack(fill="x", pady=3)

            icon  = "OK" if r["ok"] else "!!"
            color = self.online if r["ok"] else self.err
            tk.Label(row, text=icon, bg=self.card, fg=color,
                     font=self.f_bold, width=3).pack(side="left")
            tk.Label(row, text=r["name"], bg=self.card, fg=self.fg,
                     font=self.f_small, width=22, anchor="w").pack(side="left")
            tk.Label(row, text=r["message"], bg=self.card, fg=self.dim,
                     font=self.f_small, anchor="w").pack(side="left", fill="x", expand=True)

    def set_on_continue(self, callback):
        self._on_continue = callback

    def _do_continue(self):
        if self._on_continue:
            self._on_continue()
