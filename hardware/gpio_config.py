"""
hardware/gpio_config.py — Modello dati per la configurazione GPIO.

Gestisce l'assegnazione pin → funzione con validazione conflitti.
"""

# Pin fisici Raspberry Pi da NON toccare
RESERVED_PINS = frozenset([
    1, 2,               # 3.3V, 5V
    4, 6,               # 5V, GND
    9, 14, 20, 25, 30, 34, 39,  # GND
    27, 28,             # ID_SD, ID_SC (EEPROM HAT)
])

PIN_FUNCTIONS = [
    "non usato",
    "encoder CLK",
    "encoder DT",
    "encoder SW",
    "button",
    "buzzer",
    "GPS TX",
    "GPS RX",
]

_FUNCTION_TO_SETTING = {
    "encoder CLK": ("encoder", "pin_clk"),
    "encoder DT":  ("encoder", "pin_dt"),
    "encoder SW":  ("encoder", "pin_sw"),
    "button":      ("buttons", "pin"),
    "buzzer":      ("buzzer",  "pin"),
    "GPS TX":      ("gps",     "pin_tx"),
    "GPS RX":      ("gps",     "pin_rx"),
}


class GPIOPinConfig:
    def __init__(self, pin: int, function: str = "non usato"):
        self.pin = pin
        self.function = function


class GPIOConfigurator:
    """Gestisce l'assegnazione completa pin → funzione per tutti i GPIO."""

    def __init__(self):
        # Lista di (pin, function) per preservare tutti i tentativi di assegnazione
        self._assignments: list = []

    def assign(self, pin: int, function: str):
        self._assignments.append((pin, function))

    def get(self, pin: int) -> str:
        # Restituisce l'ultima assegnazione per il pin (o "non usato")
        for p, fn in reversed(self._assignments):
            if p == pin:
                return fn
        return "non usato"

    def validate(self) -> list:
        """Restituisce lista messaggi di errore (vuota = ok)."""
        errors = []
        # Controlla pin assegnati più di una volta
        seen_pins: dict = {}
        for pin, fn in self._assignments:
            if fn == "non usato":
                continue
            if pin in seen_pins:
                errors.append(f"Pin {pin} assegnato più volte ('{seen_pins[pin]}' e '{fn}')")
            else:
                seen_pins[pin] = fn
        # Controlla funzioni duplicate su pin diversi
        seen_fns: dict = {}
        for pin, fn in self._assignments:
            if fn == "non usato":
                continue
            if fn in seen_fns and seen_fns[fn] != pin:
                msg = f"Pin {seen_fns[fn]} e {pin} entrambi assegnati a '{fn}'"
                if msg not in errors:
                    errors.append(msg)
            else:
                seen_fns[fn] = pin
        return errors

    def to_settings_dict(self) -> dict:
        result: dict = {
            "encoder": {},
            "buttons": {},
            "buzzer":  {},
            "gps":     {},
        }
        # Usa solo l'ultima assegnazione per ciascun pin
        effective: dict = {}
        for pin, fn in self._assignments:
            effective[pin] = fn
        for pin, fn in effective.items():
            if fn in _FUNCTION_TO_SETTING:
                section, key = _FUNCTION_TO_SETTING[fn]
                result[section][key] = pin
        return result

    @classmethod
    def from_settings(cls, hw_cfg: dict) -> "GPIOConfigurator":
        cfg = cls()
        enc = hw_cfg.get("encoder", {})
        if enc.get("pin_clk"): cfg.assign(enc["pin_clk"], "encoder CLK")
        if enc.get("pin_dt"):  cfg.assign(enc["pin_dt"],  "encoder DT")
        if enc.get("pin_sw"):  cfg.assign(enc["pin_sw"],  "encoder SW")
        for btn in hw_cfg.get("buttons", []):
            if btn.get("pin"): cfg.assign(btn["pin"], "button")
        buz = hw_cfg.get("buzzer", {})
        if buz.get("pin"): cfg.assign(buz["pin"], "buzzer")
        gps = hw_cfg.get("gps", {})
        if gps.get("pin_tx"): cfg.assign(gps["pin_tx"], "GPS TX")
        if gps.get("pin_rx"): cfg.assign(gps["pin_rx"], "GPS RX")
        return cfg
