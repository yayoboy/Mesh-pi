# Mesh-Pi Miglioramenti Open Source — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migliorare Mesh-Pi in 4 wave per renderlo un progetto open source maturo e usabile dalla community Meshtastic.

**Architecture:** 4 wave sequenziali — Wave 1 refactoring e configurazione, Wave 2 UI e feature, Wave 3 affidabilità hardware, Wave 4 documentazione. Ogni task produce un commit autonomo testabile in demo mode senza hardware fisico.

**Tech Stack:** Python 3.9+, Tkinter (apt), meshtastic>=2.5.0, pytest per unit test dei moduli non-UI, threading + widget.after(0, fn) per cross-thread safety.

---

## Setup Iniziale

### Task 0: Setup pytest

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `requirements-dev.txt`

**Step 1: Crea la struttura test**

```bash
mkdir -p tests/hardware tests/radio tests/data tests/ui
touch tests/__init__.py tests/hardware/__init__.py tests/radio/__init__.py tests/data/__init__.py tests/ui/__init__.py
```

**Step 2: Crea `requirements-dev.txt`**

```
pytest>=7.0.0
pytest-mock>=3.10.0
```

**Step 3: Crea `tests/conftest.py`**

```python
import sys
import os
# Aggiungi root al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

**Step 4: Verifica pytest funziona**

```bash
pip install pytest pytest-mock
pytest tests/ -v
```
Atteso: `no tests ran` (zero test, zero errori)

**Step 5: Commit**

```bash
git add tests/ requirements-dev.txt
git commit -m "test: aggiungi struttura pytest e conftest"
```

---

## WAVE 1 — Fondamenta

---

### Task 1: Estrai `HardwareStatus` — pattern unificato errori

**Files:**
- Create: `hardware/status.py`
- Create: `tests/hardware/test_status.py`

**Step 1: Scrivi il test**

```python
# tests/hardware/test_status.py
from hardware.status import HardwareStatus, StatusLevel

def test_status_default_disabled():
    s = HardwareStatus("test")
    assert s.level == StatusLevel.DISABLED
    assert s.message == ""

def test_status_set_ok():
    s = HardwareStatus("gps")
    s.set_ok("Fix acquisito")
    assert s.level == StatusLevel.OK
    assert s.message == "Fix acquisito"

def test_status_set_error():
    s = HardwareStatus("serial")
    s.set_error("/dev/ttyUSB0 non trovato")
    assert s.level == StatusLevel.ERROR
    assert "ttyUSB0" in s.message

def test_status_set_warning():
    s = HardwareStatus("i2c")
    s.set_warning("Sensore non risponde")
    assert s.level == StatusLevel.WARNING

def test_status_repr():
    s = HardwareStatus("buzzer")
    s.set_ok()
    assert "ok" in repr(s).lower()
```

**Step 2: Esegui il test per verificare che fallisce**

```bash
pytest tests/hardware/test_status.py -v
```
Atteso: `ImportError: cannot import name 'HardwareStatus'`

**Step 3: Implementa `hardware/status.py`**

```python
"""
hardware/status.py — Stato unificato per ogni periferica hardware.

Ogni modulo hardware espone un HardwareStatus consultabile dalla UI.
"""
from enum import Enum


class StatusLevel(Enum):
    OK       = "ok"
    WARNING  = "warning"
    ERROR    = "error"
    DISABLED = "disabled"


class HardwareStatus:
    """Stato osservabile di una periferica hardware."""

    def __init__(self, name: str):
        self.name    = name
        self.level   = StatusLevel.DISABLED
        self.message = ""

    def set_ok(self, message: str = ""):
        self.level   = StatusLevel.OK
        self.message = message

    def set_warning(self, message: str = ""):
        self.level   = StatusLevel.WARNING
        self.message = message

    def set_error(self, message: str = ""):
        self.level   = StatusLevel.ERROR
        self.message = message

    def set_disabled(self, message: str = ""):
        self.level   = StatusLevel.DISABLED
        self.message = message

    def __repr__(self):
        return f"<HardwareStatus name={self.name!r} level={self.level.value} msg={self.message!r}>"
```

**Step 4: Esegui i test**

```bash
pytest tests/hardware/test_status.py -v
```
Atteso: 5 PASS

**Step 5: Commit**

```bash
git add hardware/status.py tests/hardware/test_status.py
git commit -m "feat: aggiungi HardwareStatus — pattern unificato stato hardware"
```

---

### Task 2: Applica `HardwareStatus` a `I2CManager`

**Files:**
- Modify: `hardware/i2c_manager.py`
- Create: `tests/hardware/test_i2c_manager.py`

**Step 1: Scrivi il test**

```python
# tests/hardware/test_i2c_manager.py
from unittest.mock import patch, MagicMock
from hardware.i2c_manager import I2CManager
from hardware.status import StatusLevel

BASE_CFG = {
    "i2c": {
        "bus": 1,
        "poll_interval_ms": 100,
        "sensors": []
    }
}

def test_i2c_manager_status_disabled_no_sensors():
    mgr = I2CManager(BASE_CFG)
    assert mgr.status.level == StatusLevel.DISABLED

def test_i2c_manager_exposes_status():
    mgr = I2CManager(BASE_CFG)
    assert hasattr(mgr, "status")

def test_i2c_manager_status_error_on_bad_bus():
    cfg = {"i2c": {"bus": 99, "poll_interval_ms": 100, "sensors": []}}
    mgr = I2CManager(cfg)
    # Bus 99 non esiste — non deve crashare, deve segnalare errore
    assert mgr.status.level in (StatusLevel.DISABLED, StatusLevel.ERROR)
```

**Step 2: Esegui il test per verificare che fallisce**

```bash
pytest tests/hardware/test_i2c_manager.py -v
```
Atteso: `AttributeError: 'I2CManager' object has no attribute 'status'`

**Step 3: Aggiungi `status` a `I2CManager`**

Apri `hardware/i2c_manager.py`. Nel metodo `__init__`, dopo `self._lock = threading.Lock()`, aggiungi:

```python
from .status import HardwareStatus, StatusLevel

# In __init__:
self.status = HardwareStatus("i2c")
if not self._sensors:
    self.status.set_disabled("Nessun sensore configurato")
else:
    self.status.set_ok(f"{len(self._sensors)} sensore/i configurati")
```

Nel blocco `except` del polling, aggiorna lo status:
```python
except Exception as e:
    self.status.set_error(str(e))
    logger.error("I2C poll error: %s", e)
```

**Step 4: Esegui i test**

```bash
pytest tests/hardware/test_i2c_manager.py -v
```
Atteso: 3 PASS

**Step 5: Commit**

```bash
git add hardware/i2c_manager.py tests/hardware/test_i2c_manager.py
git commit -m "feat: aggiungi HardwareStatus a I2CManager"
```

---

### Task 3: Sensori I2C personalizzabili — label, ruolo, multipli

**Files:**
- Modify: `hardware/i2c_manager.py`
- Modify: `config/settings.json`
- Create: `tests/hardware/test_sensor_config.py`

**Step 1: Scrivi i test**

```python
# tests/hardware/test_sensor_config.py
from hardware.i2c_manager import SensorConfig

def test_sensor_config_defaults():
    cfg = {"type": "sht30", "enabled": False, "address": "0x44"}
    sc = SensorConfig(cfg)
    assert sc.label == "sht30"
    assert sc.role == "custom"
    assert sc.address == 0x44

def test_sensor_config_custom_label():
    cfg = {"type": "sht30", "enabled": True, "address": "0x44",
           "label": "Temperatura Interna", "role": "interno"}
    sc = SensorConfig(cfg)
    assert sc.label == "Temperatura Interna"
    assert sc.role == "interno"

def test_sensor_config_multiple_same_type():
    cfgs = [
        {"type": "sht30", "enabled": True, "address": "0x44", "label": "Int", "role": "interno"},
        {"type": "sht30", "enabled": True, "address": "0x45", "label": "Ext", "role": "esterno"},
    ]
    sensors = [SensorConfig(c) for c in cfgs]
    assert sensors[0].address != sensors[1].address
    assert sensors[0].label != sensors[1].label

def test_sensor_config_address_string_and_int():
    sc1 = SensorConfig({"type": "bme280", "enabled": False, "address": "0x76"})
    sc2 = SensorConfig({"type": "bme280", "enabled": False, "address": 118})
    assert sc1.address == 0x76
    assert sc2.address == 0x76

def test_sensor_config_valid_roles():
    valid = ["interno", "esterno", "ambiente", "alimentazione", "custom"]
    for role in valid:
        sc = SensorConfig({"type": "ina219", "enabled": False,
                           "address": "0x40", "role": role})
        assert sc.role == role
```

**Step 2: Esegui per verificare che falliscono**

```bash
pytest tests/hardware/test_sensor_config.py -v
```
Atteso: `ImportError: cannot import name 'SensorConfig'`

**Step 3: Aggiungi `SensorConfig` a `hardware/i2c_manager.py`**

Prima di `class I2CManager`, aggiungi:

```python
VALID_ROLES = ("interno", "esterno", "ambiente", "alimentazione", "custom")


class SensorConfig:
    """Configurazione di un singolo sensore I2C."""

    def __init__(self, cfg: dict):
        self.type    = cfg["type"]
        self.enabled = cfg.get("enabled", False)
        raw_addr     = cfg.get("address", "0x00")
        self.address = int(raw_addr, 16) if isinstance(raw_addr, str) else int(raw_addr)
        self.label   = cfg.get("label") or self.type
        role         = cfg.get("role", "custom")
        self.role    = role if role in VALID_ROLES else "custom"
        # Parametri tipo-specifici
        self.shunt_ohms        = float(cfg.get("shunt_ohms", 0.1))
        self.max_expected_amps = float(cfg.get("max_expected_amps", 2.0))

    def to_dict(self) -> dict:
        return {
            "type":    self.type,
            "enabled": self.enabled,
            "address": hex(self.address),
            "label":   self.label,
            "role":    self.role,
            "shunt_ohms":        self.shunt_ohms,
            "max_expected_amps": self.max_expected_amps,
        }
```

In `I2CManager.__init__`, sostituisci la lettura sensori con:
```python
self._sensor_configs = [SensorConfig(s) for s in cfg.get("i2c", {}).get("sensors", [])]
self._sensors = [s for s in self._sensor_configs if s.enabled]
```

**Step 4: Aggiorna `config/settings.json`** — aggiungi `role` ai sensori esistenti:

```json
{ "type": "ina219", "enabled": false, "address": "0x40",
  "label": "Batteria", "role": "alimentazione",
  "shunt_ohms": 0.1, "max_expected_amps": 2.0 },
{ "type": "bme280", "enabled": false, "address": "0x76",
  "label": "Meteo", "role": "ambiente" },
{ "type": "sht30", "enabled": false, "address": "0x44",
  "label": "Temp/Umidità", "role": "interno" }
```

**Step 5: Esegui i test**

```bash
pytest tests/hardware/test_sensor_config.py -v
```
Atteso: 5 PASS

**Step 6: Commit**

```bash
git add hardware/i2c_manager.py config/settings.json tests/hardware/test_sensor_config.py
git commit -m "feat: sensori I2C personalizzabili — label, ruolo, multipli stesso tipo"
```

---

### Task 4: GPIO Configurator — modello dati

**Files:**
- Create: `hardware/gpio_config.py`
- Create: `tests/hardware/test_gpio_config.py`

**Step 1: Scrivi i test**

```python
# tests/hardware/test_gpio_config.py
from hardware.gpio_config import GPIOPinConfig, GPIOConfigurator, PIN_FUNCTIONS, RESERVED_PINS

def test_pin_functions_defined():
    assert "non usato" in PIN_FUNCTIONS
    assert "encoder CLK" in PIN_FUNCTIONS
    assert "button" in PIN_FUNCTIONS
    assert "buzzer" in PIN_FUNCTIONS

def test_reserved_pins_not_assignable():
    assert 1 in RESERVED_PINS   # 3.3V
    assert 2 in RESERVED_PINS   # 5V
    assert 6 in RESERVED_PINS   # GND

def test_pin_config_default():
    p = GPIOPinConfig(17)
    assert p.pin == 17
    assert p.function == "non usato"

def test_pin_config_assign():
    p = GPIOPinConfig(17)
    p.function = "encoder CLK"
    assert p.function == "encoder CLK"

def test_configurator_no_duplicate_pins():
    cfg = GPIOConfigurator()
    cfg.assign(17, "encoder CLK")
    cfg.assign(18, "encoder DT")
    errors = cfg.validate()
    assert errors == []

def test_configurator_detects_duplicate():
    cfg = GPIOConfigurator()
    cfg.assign(17, "encoder CLK")
    cfg.assign(17, "encoder DT")  # stesso pin!
    errors = cfg.validate()
    assert len(errors) == 1
    assert "17" in errors[0]

def test_configurator_to_settings():
    cfg = GPIOConfigurator()
    cfg.assign(17, "encoder CLK")
    cfg.assign(18, "encoder DT")
    d = cfg.to_settings_dict()
    assert d["encoder"]["pin_clk"] == 17
    assert d["encoder"]["pin_dt"] == 18
```

**Step 2: Esegui per verificare che falliscono**

```bash
pytest tests/hardware/test_gpio_config.py -v
```
Atteso: `ImportError`

**Step 3: Implementa `hardware/gpio_config.py`**

```python
"""
hardware/gpio_config.py — Modello dati per la configurazione GPIO.

Gestisce l'assegnazione pin → funzione con validazione conflitti.
"""

# Pin fisici Raspberry Pi da NON toccare
RESERVED_PINS = frozenset([
    1, 2,        # 3.3V, 5V
    4, 6,        # 5V, GND
    9, 14, 20, 25, 30, 34, 39,  # GND
    27, 28,      # ID_SD, ID_SC (EEPROM HAT)
])

# Funzioni assegnabili a un pin GPIO
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

# Mappa funzione → chiave settings.json
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
        self._assignments: dict[int, str] = {}  # pin → function

    def assign(self, pin: int, function: str):
        self._assignments[pin] = function

    def get(self, pin: int) -> str:
        return self._assignments.get(pin, "non usato")

    def validate(self) -> list[str]:
        """Restituisce lista di messaggi di errore (vuota = ok)."""
        errors = []
        seen: dict[str, int] = {}
        for pin, fn in self._assignments.items():
            if fn == "non usato":
                continue
            if fn in seen:
                errors.append(f"Pin {seen[fn]} e {pin} entrambi assegnati a '{fn}'")
            else:
                seen[fn] = pin
        return errors

    def to_settings_dict(self) -> dict:
        """Converte in struttura compatibile con settings.json hardware."""
        result: dict = {
            "encoder": {},
            "buttons": {},
            "buzzer":  {},
            "gps":     {},
        }
        for pin, fn in self._assignments.items():
            if fn in _FUNCTION_TO_SETTING:
                section, key = _FUNCTION_TO_SETTING[fn]
                result[section][key] = pin
        return result

    @classmethod
    def from_settings(cls, hw_cfg: dict) -> "GPIOConfigurator":
        """Costruisce da settings.json["hardware"]."""
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
```

**Step 4: Esegui i test**

```bash
pytest tests/hardware/test_gpio_config.py -v
```
Atteso: 8 PASS

**Step 5: Commit**

```bash
git add hardware/gpio_config.py tests/hardware/test_gpio_config.py
git commit -m "feat: aggiungi GPIOConfigurator — modello dati pin → funzione con validazione"
```

---

### Task 5: Refactor `settings_screen.py` → `ui/settings/`

**Files:**
- Create: `ui/settings/__init__.py`
- Create: `ui/settings/tab_display.py`
- Create: `ui/settings/tab_gpio.py`
- Create: `ui/settings/tab_gps.py`
- Create: `ui/settings/tab_sensors.py`
- Delete: `ui/settings_screen.py` (rimpiazzato da `ui/settings/__init__.py`)

**Step 1: Leggi l'intero `ui/settings_screen.py`**

```bash
cat -n ui/settings_screen.py
```

**Step 2: Crea `ui/settings/__init__.py`**

Sposta in questo file solo la classe `SettingsScreen` principale con il metodo `build()`, il top bar, la tab bar e il routing dei tab. Ogni tab delega a una classe nel file corrispondente.

```python
"""
ui/settings/__init__.py — SettingsScreen: compone i tab di configurazione hardware.
"""
import tkinter as tk
from ..base_screen import BaseScreen
from ..icons import ICON_SETTINGS
from .tab_display  import TabDisplay
from .tab_gpio     import TabGPIO
from .tab_gps      import TabGPS
from .tab_sensors  import TabSensors

# ... (class SettingsScreen con build(), _build_topbar(), _build_tab_bar(),
#      _show_tab(), _save(), inject_managers())
```

**Step 3: Crea `ui/settings/tab_gpio.py`**

Estrai tutto il codice relativo a ENCODER e PULSANTI. Aggiungi la lista GPIO con `GPIOConfigurator`:

```python
"""
ui/settings/tab_gpio.py — Tab configurazione GPIO.

Mostra lista scrollabile: pin → menu funzione.
Usa GPIOConfigurator per validazione e salvataggio.
"""
import tkinter as tk
from hardware.gpio_config import GPIOConfigurator, PIN_FUNCTIONS, RESERVED_PINS

ASSIGNABLE_PINS = [p for p in range(2, 28) if p not in RESERVED_PINS]

class TabGPIO(tk.Frame):
    def __init__(self, parent, settings: dict, **kwargs):
        super().__init__(parent, **kwargs)
        self._settings = settings
        self._vars: dict[int, tk.StringVar] = {}
        self._cfg = GPIOConfigurator.from_settings(settings.get("hardware", {}))
        self._build()

    def _build(self):
        # Intestazione colonne
        # Per ogni pin assegnabile: label pin + OptionMenu funzione
        canvas = tk.Canvas(self, bg=self["bg"], highlightthickness=0)
        scroll = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        frame  = tk.Frame(canvas, bg=self["bg"])
        frame.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)

        tk.Label(frame, text="GPIO", width=6, bg=self["bg"], fg="white").grid(row=0, column=0)
        tk.Label(frame, text="Funzione", bg=self["bg"], fg="white").grid(row=0, column=1, sticky="w")

        for i, pin in enumerate(ASSIGNABLE_PINS, start=1):
            var = tk.StringVar(value=self._cfg.get(pin))
            self._vars[pin] = var
            tk.Label(frame, text=f"GPIO {pin:2d}", bg=self["bg"],
                     fg="#aaaaaa", width=8).grid(row=i, column=0, padx=4, pady=1)
            om = tk.OptionMenu(frame, var, *PIN_FUNCTIONS)
            om.config(bg="#25252D", fg="white", highlightthickness=0, width=14)
            om["menu"].config(bg="#25252D", fg="white")
            om.grid(row=i, column=1, sticky="w", pady=1)

        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def get_config(self) -> GPIOConfigurator:
        cfg = GPIOConfigurator()
        for pin, var in self._vars.items():
            cfg.assign(pin, var.get())
        return cfg

    def validate(self) -> list[str]:
        return self.get_config().validate()
```

**Step 4: Crea `ui/settings/tab_sensors.py`**

Estrai il tab I2C con supporto label/ruolo personalizzati:

```python
"""
ui/settings/tab_sensors.py — Tab configurazione sensori I2C.

Ogni sensore: tipo, indirizzo, label libera, ruolo, abilitato.
Supporta multipli sensori dello stesso tipo.
"""
import tkinter as tk
from hardware.i2c_manager import SensorConfig, VALID_ROLES

class TabSensors(tk.Frame):
    def __init__(self, parent, settings: dict, **kwargs):
        super().__init__(parent, **kwargs)
        self._settings   = settings
        self._rows: list[dict] = []  # una entry per sensore
        self._build()

    def _build(self):
        # Scroll area
        canvas = tk.Canvas(self, bg=self["bg"], highlightthickness=0)
        scroll = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self._frame = tk.Frame(canvas, bg=self["bg"])
        self._frame.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)

        sensors = self._settings.get("i2c", {}).get("sensors", [])
        for s in sensors:
            self._add_sensor_row(SensorConfig(s))

        btn = tk.Button(self._frame, text="+ Aggiungi Sensore",
                        command=self._add_empty_row,
                        bg="#2A4A46", fg="white")
        btn.grid(row=999, column=0, columnspan=5, pady=6)

        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _add_sensor_row(self, sc: SensorConfig):
        row = len(self._rows)
        vars_ = {
            "enabled": tk.BooleanVar(value=sc.enabled),
            "type":    tk.StringVar(value=sc.type),
            "address": tk.StringVar(value=hex(sc.address)),
            "label":   tk.StringVar(value=sc.label),
            "role":    tk.StringVar(value=sc.role),
        }
        self._rows.append(vars_)
        f = self._frame
        tk.Checkbutton(f, variable=vars_["enabled"], bg=self["bg"],
                       fg="white", selectcolor="#333").grid(row=row, column=0)
        tk.Entry(f, textvariable=vars_["label"], width=16,
                 bg="#2C2C35", fg="white").grid(row=row, column=1, padx=2)
        tk.Label(f, textvariable=vars_["type"], bg=self["bg"],
                 fg="#aaaaaa", width=7).grid(row=row, column=2)
        tk.Entry(f, textvariable=vars_["address"], width=6,
                 bg="#2C2C35", fg="white").grid(row=row, column=3, padx=2)
        om = tk.OptionMenu(f, vars_["role"], *VALID_ROLES)
        om.config(bg="#25252D", fg="white", highlightthickness=0, width=10)
        om["menu"].config(bg="#25252D", fg="white")
        om.grid(row=row, column=4, padx=2)

    def _add_empty_row(self):
        dummy = SensorConfig({"type": "sht30", "enabled": False,
                              "address": "0x44", "label": "Nuovo", "role": "custom"})
        self._add_sensor_row(dummy)

    def get_sensor_configs(self) -> list[dict]:
        result = []
        for v in self._rows:
            result.append({
                "type":    v["type"].get(),
                "enabled": v["enabled"].get(),
                "address": v["address"].get(),
                "label":   v["label"].get(),
                "role":    v["role"].get(),
            })
        return result
```

**Step 5: Aggiorna import in `main.py`**

Sostituisci:
```python
from ui.settings_screen import SettingsScreen
```
con:
```python
from ui.settings import SettingsScreen
```

**Step 6: Avvia in demo mode per smoke test**

```bash
python3 main.py
```
Atteso: app si apre, schermata Settings funziona con i tab.

**Step 7: Commit**

```bash
git add ui/settings/ main.py
git rm ui/settings_screen.py
git commit -m "refactor: split settings_screen.py in ui/settings/ con tab modulari"
```

---

## WAVE 2 — UI Polish + Feature

---

### Task 6: `data/telemetry_store.py` — campionamento e persistenza

**Files:**
- Create: `data/__init__.py`
- Create: `data/telemetry_store.py`
- Create: `tests/data/test_telemetry_store.py`

**Step 1: Scrivi i test**

```python
# tests/data/test_telemetry_store.py
import time
import os
import json
import tempfile
from data.telemetry_store import TelemetryStore, TelemetrySample

def test_sample_creation():
    s = TelemetrySample(rssi=-80, snr=5.0)
    assert s.rssi == -80
    assert s.snr == 5.0
    assert s.sensors == {}

def test_sample_with_sensors():
    s = TelemetrySample(rssi=-70, snr=3.0,
                        sensors={"Temperatura Interna": 22.5})
    assert s.sensors["Temperatura Interna"] == 22.5

def test_store_add_and_get():
    store = TelemetryStore(max_hours=1)
    store.add(TelemetrySample(rssi=-80, snr=5.0))
    samples = store.get_samples()
    assert len(samples) == 1
    assert samples[0].rssi == -80

def test_store_max_size():
    store = TelemetryStore(max_hours=1, max_samples=5)
    for i in range(10):
        store.add(TelemetrySample(rssi=-i, snr=0.0))
    assert len(store.get_samples()) == 5

def test_store_persist_and_load():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        store = TelemetryStore(persist_path=path)
        store.add(TelemetrySample(rssi=-75, snr=4.0,
                                  sensors={"Batteria": 12.1}))
        store.save()
        store2 = TelemetryStore(persist_path=path)
        store2.load()
        samples = store2.get_samples()
        assert len(samples) == 1
        assert samples[0].rssi == -75
    finally:
        os.unlink(path)

def test_store_sensor_names():
    store = TelemetryStore()
    store.add(TelemetrySample(rssi=-80, snr=0, sensors={"Int": 20.0, "Ext": 25.0}))
    names = store.sensor_names()
    assert "Int" in names
    assert "Ext" in names
```

**Step 2: Esegui per verificare che falliscono**

```bash
pytest tests/data/test_telemetry_store.py -v
```

**Step 3: Implementa `data/telemetry_store.py`**

```python
"""
data/telemetry_store.py — Storico telemetria campionato ogni 30s.

Persiste in JSON (default /tmp/telemetry.json), max 24h di dati.
Thread-safe: tutte le operazioni protette da lock.
"""
import json
import logging
import threading
from collections import deque
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_PATH    = "/tmp/telemetry.json"
DEFAULT_HOURS   = 24
SAMPLES_PER_H   = 120  # campione ogni 30s → 120/h


class TelemetrySample:
    __slots__ = ("timestamp", "rssi", "snr", "sensors")

    def __init__(self, rssi: int, snr: float,
                 sensors: Optional[dict] = None,
                 timestamp: Optional[datetime] = None):
        self.timestamp = timestamp or datetime.now()
        self.rssi      = rssi
        self.snr       = snr
        self.sensors   = sensors or {}

    def to_dict(self) -> dict:
        return {
            "ts":      self.timestamp.isoformat(),
            "rssi":    self.rssi,
            "snr":     self.snr,
            "sensors": self.sensors,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TelemetrySample":
        return cls(
            rssi      = d["rssi"],
            snr       = d["snr"],
            sensors   = d.get("sensors", {}),
            timestamp = datetime.fromisoformat(d["ts"]),
        )


class TelemetryStore:
    def __init__(self, max_hours: int = DEFAULT_HOURS,
                 max_samples: Optional[int] = None,
                 persist_path: str = DEFAULT_PATH):
        cap = max_samples or (max_hours * SAMPLES_PER_H)
        self._buf  = deque(maxlen=cap)
        self._lock = threading.Lock()
        self._path = persist_path

    def add(self, sample: TelemetrySample):
        with self._lock:
            self._buf.append(sample)

    def get_samples(self) -> list[TelemetrySample]:
        with self._lock:
            return list(self._buf)

    def sensor_names(self) -> list[str]:
        names: set[str] = set()
        with self._lock:
            for s in self._buf:
                names.update(s.sensors.keys())
        return sorted(names)

    def save(self):
        try:
            with self._lock:
                data = [s.to_dict() for s in self._buf]
            with open(self._path, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning("Telemetry save failed: %s", e)

    def load(self):
        try:
            with open(self._path) as f:
                data = json.load(f)
            with self._lock:
                for d in data:
                    self._buf.append(TelemetrySample.from_dict(d))
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning("Telemetry load failed: %s", e)
```

**Step 4: Crea `data/__init__.py`** (vuoto)

**Step 5: Esegui i test**

```bash
pytest tests/data/test_telemetry_store.py -v
```
Atteso: 6 PASS

**Step 6: Commit**

```bash
git add data/ tests/data/
git commit -m "feat: aggiungi TelemetryStore — campionamento RSSI/sensori con persistenza JSON"
```

---

### Task 7: Debug Screen multi-tab (Radio + Telemetria)

**Files:**
- Modify: `ui/debug_screen.py`

**Step 1: Leggi il file corrente**

```bash
cat -n ui/debug_screen.py
```

**Step 2: Aggiungi struttura tab**

Nella classe `DebugScreen.build()`, avvolgi il contenuto esistente in un frame "radio_tab" e aggiungi un frame "telemetry_tab". Aggiungi una tab bar sopra (simile a SettingsScreen).

```python
def _build_tab_bar(self):
    bar = tk.Frame(self, bg=self.card, height=32)
    bar.grid(row=1, column=0, sticky="ew")
    for name, key in [("📡 Radio", "radio"), ("📊 Telemetria", "telemetry")]:
        btn = tk.Button(bar, text=name,
                        command=lambda k=key: self._show_tab(k),
                        bg=self.card, fg=self.fg,
                        relief="flat", padx=10)
        btn.pack(side="left")

def _show_tab(self, key: str):
    self._radio_tab.grid_remove()
    self._telemetry_tab.grid_remove()
    if key == "radio":
        self._radio_tab.grid(row=2, column=0, sticky="nsew")
    else:
        self._telemetry_tab.grid(row=2, column=0, sticky="nsew")
        self._refresh_telemetry()
```

**Step 3: Costruisci `_build_telemetry_tab()`**

```python
def _build_telemetry_tab(self):
    frame = tk.Frame(self, bg=self.bg)
    frame.grid(row=2, column=0, sticky="nsew")
    frame.grid_remove()
    self._telemetry_tab   = frame
    self._telemetry_frame = frame  # aggiornato in _refresh_telemetry

    # Placeholder
    self._tel_placeholder = tk.Label(
        frame, text="Nessun sensore configurato",
        bg=self.bg, fg="#666666")
    self._tel_placeholder.pack(expand=True)

def _refresh_telemetry(self):
    if not hasattr(self, "_telemetry_store") or not self._telemetry_store:
        return
    names = self._telemetry_store.sensor_names()
    if not names:
        self._tel_placeholder.pack(expand=True)
        return
    self._tel_placeholder.pack_forget()
    # Disegna un mini-grafico per ogni sensore
    # (canvas 200×60 con linea, label, ultimo valore)
    for widget in self._telemetry_tab.winfo_children():
        if widget != self._tel_placeholder:
            widget.destroy()
    samples = self._telemetry_store.get_samples()
    for sensor_name in names:
        values = [s.sensors.get(sensor_name) for s in samples
                  if sensor_name in s.sensors]
        if not values:
            continue
        self._draw_sensor_graph(self._telemetry_tab, sensor_name, values)

def _draw_sensor_graph(self, parent, name: str, values: list):
    frame = tk.Frame(parent, bg=self.card, pady=4)
    frame.pack(fill="x", padx=8, pady=3)
    label_text = f"{name}   {values[-1]:.1f}"
    tk.Label(frame, text=label_text, bg=self.card,
             fg=self.accent, font=self.f_small).pack(anchor="w", padx=6)
    c = tk.Canvas(frame, bg=self.card, height=40,
                  width=200, highlightthickness=0)
    c.pack(fill="x", padx=6)
    if len(values) < 2:
        return
    mn, mx = min(values), max(values)
    span = (mx - mn) or 1
    w, h = 200, 38
    pts = []
    for i, v in enumerate(values[-60:]):
        x = int(i / max(len(values[-60:]) - 1, 1) * w)
        y = h - int((v - mn) / span * (h - 4)) - 2
        pts += [x, y]
    if len(pts) >= 4:
        c.create_line(pts, fill=self.accent, width=1, smooth=True)
```

**Step 4: Inietta `TelemetryStore` tramite `App`**

In `main.py`, dopo la creazione di `TelemetryStore`, iniettalo nella DebugScreen:
```python
self.screens["debug"]._telemetry_store = self.telemetry_store
```

**Step 5: Smoke test in demo mode**

```bash
python3 main.py
```
Apri Debug Screen → verifica due tab "Radio" e "Telemetria" visibili.

**Step 6: Commit**

```bash
git add ui/debug_screen.py main.py
git commit -m "feat: Debug Screen multi-tab Radio + Telemetria con grafici per sensore"
```

---

### Task 8: Badge messaggi non letti nella nav bar

**Files:**
- Modify: `ui/base_screen.py`
- Modify: `ui/chat_screen.py`
- Modify: `main.py`

**Step 1: Aggiungi `unread_count` a `BaseScreen.nav_bar()`**

In `base_screen.py`, il metodo `nav_bar()` accetta ora un parametro opzionale `badge_counts: dict`:

```python
def nav_bar(self, parent, current: str, badge_counts: dict = None) -> tk.Frame:
    ...
    # Sull'icona chat:
    count = (badge_counts or {}).get("chat", 0)
    label = f"✉ {count}" if count > 0 else "✉ CHAT"
    # usa label invece del testo fisso
```

**Step 2: Aggiungi `MessageBadge` a `App` in `main.py`**

```python
self._unread_messages = 0

def _on_message(self, msg):
    if self._current_screen != "chat":
        self._unread_messages += 1
        self._update_badges()

def _update_badges(self):
    badge = {"chat": self._unread_messages}
    for screen in self.screens.values():
        if hasattr(screen, "update_badges"):
            screen.update_badges(badge)

def _on_screen_change(self, name):
    if name == "chat":
        self._unread_messages = 0
        self._update_badges()
```

**Step 3: Aggiungi `update_badges()` a `BaseScreen`**

```python
def update_badges(self, badges: dict):
    """Aggiorna badge nella nav bar. Override se necessario."""
    # Trova e aggiorna il label della chat nella nav bar
    pass  # implementazione via tag Tkinter su nav bar labels
```

**Step 4: Smoke test**

```bash
python3 main.py
```
Demo mode invia messaggi automatici — verifica badge numerico appare su ✉ quando si è su Home.

**Step 5: Commit**

```bash
git add ui/base_screen.py ui/chat_screen.py main.py
git commit -m "feat: badge messaggi non letti nella nav bar"
```

---

### Task 9: Pannello espanso nodi (tap → dettagli)

**Files:**
- Modify: `ui/nodes_screen.py`

**Step 1: Aggiungi `_show_node_detail()` a `NodesScreen`**

```python
def _on_node_tap(self, node_id: str):
    node = self._get_node(node_id)
    if not node:
        return
    # Crea overlay semitrasparente
    overlay = tk.Frame(self, bg="#000000")
    overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
    overlay.configure(bg="#000000")

    panel = tk.Frame(overlay, bg=self.card, padx=12, pady=12)
    panel.place(relx=0.05, rely=0.1, relwidth=0.9, relheight=0.8)

    tk.Label(panel, text=node.long_name or node.node_id,
             bg=self.card, fg=self.fg, font=self.f_large).pack(anchor="w")
    tk.Label(panel, text=f"RSSI: {node.rssi} dBm   SNR: {node.snr:.1f}",
             bg=self.card, fg=self.accent, font=self.f_small).pack(anchor="w")
    tk.Label(panel, text=f"Hop: {node.hops}   Ultimo: {self._fmt_time(node.last_heard)}",
             bg=self.card, fg="#aaaaaa", font=self.f_small).pack(anchor="w")
    if node.latitude and node.longitude:
        tk.Label(panel, text=f"GPS: {node.latitude:.5f}, {node.longitude:.5f}",
                 bg=self.card, fg="#aaaaaa", font=self.f_small).pack(anchor="w")

    tk.Button(panel, text="✕ Chiudi",
              command=overlay.destroy,
              bg=self.bg, fg=self.fg, relief="flat").pack(side="bottom")
```

**Step 2: Aggiungi bind tap alle card nodi**

Nella funzione che costruisce ogni card nodo, aggiungi:
```python
card_frame.bind("<Button-1>", lambda e, nid=node.node_id: self._on_node_tap(nid))
```

**Step 3: Aggiungi ordinamento**

Sopra la lista nodi, aggiungi tre bottoni compatti:
```python
sort_frame = tk.Frame(self, bg=self.bg)
sort_frame.grid(row=1, column=0, sticky="ew", padx=8)
for label, key in [("Segnale", "rssi"), ("Recente", "last_heard"), ("Nome", "name")]:
    tk.Button(sort_frame, text=label,
              command=lambda k=key: self._set_sort(k),
              bg=self.card, fg=self.fg,
              font=self.f_small, relief="flat", padx=6).pack(side="left")
```

**Step 4: Smoke test**

```bash
python3 main.py
```
Vai su Nodi → tap su un nodo demo → verifica pannello espanso con dettagli.

**Step 5: Commit**

```bash
git add ui/nodes_screen.py
git commit -m "feat: pannello espanso nodi con dettagli GPS/RSSI/SNR + ordinamento"
```

---

## WAVE 3 — Reliability

---

### Task 10: Reconnessione automatica radio con backoff

**Files:**
- Modify: `radio/meshtastic_client.py`
- Create: `tests/radio/test_reconnect.py`

**Step 1: Scrivi i test**

```python
# tests/radio/test_reconnect.py
from unittest.mock import MagicMock, patch
import time
from radio.meshtastic_client import ReconnectPolicy

def test_backoff_sequence():
    policy = ReconnectPolicy(base=1, max_delay=8)
    delays = [policy.next_delay() for _ in range(5)]
    assert delays == [1, 2, 4, 8, 8]

def test_backoff_resets_on_success():
    policy = ReconnectPolicy(base=1, max_delay=8)
    policy.next_delay()
    policy.next_delay()
    policy.reset()
    assert policy.next_delay() == 1

def test_policy_attempt_count():
    policy = ReconnectPolicy(base=1, max_delay=30)
    for _ in range(3):
        policy.next_delay()
    assert policy.attempts == 3
```

**Step 2: Esegui per verificare che falliscono**

```bash
pytest tests/radio/test_reconnect.py -v
```

**Step 3: Aggiungi `ReconnectPolicy` a `radio/meshtastic_client.py`**

```python
class ReconnectPolicy:
    """Backoff esponenziale per tentativi di riconnessione."""

    def __init__(self, base: int = 1, max_delay: int = 30):
        self._base      = base
        self._max       = max_delay
        self.attempts   = 0

    def next_delay(self) -> int:
        delay = min(self._base * (2 ** self.attempts), self._max)
        self.attempts += 1
        return delay

    def reset(self):
        self.attempts = 0
```

**Step 4: Integra in `MeshtasticClient`**

Nel thread reader, dopo una disconnessione:
```python
self._reconnect_policy = ReconnectPolicy()

def _reconnect_loop(self):
    while not self._stop_event.is_set():
        delay = self._reconnect_policy.next_delay()
        logger.info("Riconnessione in %ds (tentativo %d)",
                    delay, self._reconnect_policy.attempts)
        if self._on_status_change:
            self._on_status_change(f"reconnecting:{delay}")
        self._stop_event.wait(delay)
        if self._try_connect():
            self._reconnect_policy.reset()
            break
```

**Step 5: Esegui i test**

```bash
pytest tests/radio/test_reconnect.py -v
```
Atteso: 3 PASS

**Step 6: Commit**

```bash
git add radio/meshtastic_client.py tests/radio/test_reconnect.py
git commit -m "feat: reconnessione automatica radio con backoff esponenziale (1s→30s)"
```

---

### Task 11: Watchdog Thread

**Files:**
- Create: `hardware/watchdog.py`
- Create: `tests/hardware/test_watchdog.py`

**Step 1: Scrivi i test**

```python
# tests/hardware/test_watchdog.py
import threading
import time
from hardware.watchdog import ThreadWatchdog

def test_watchdog_detects_dead_thread():
    events = []
    dead_thread = threading.Thread(target=lambda: None, name="test-dead")
    dead_thread.start()
    time.sleep(0.05)  # lascia morire

    def on_dead(name):
        events.append(name)

    wd = ThreadWatchdog(check_interval=0.1)
    wd.watch(dead_thread, on_dead)
    wd.start()
    time.sleep(0.3)
    wd.stop()
    assert "test-dead" in events

def test_watchdog_ignores_alive_thread():
    events = []
    stop = threading.Event()
    alive = threading.Thread(target=lambda: stop.wait(), name="test-alive", daemon=True)
    alive.start()

    wd = ThreadWatchdog(check_interval=0.1)
    wd.watch(alive, lambda n: events.append(n))
    wd.start()
    time.sleep(0.3)
    wd.stop()
    stop.set()
    assert events == []

def test_watchdog_max_restarts():
    counts = [0]
    def restart_fn():
        counts[0] += 1
    wd = ThreadWatchdog(max_restarts=2)
    # simula 3 restart → il terzo non deve avvenire
    wd._restart_counts["x"] = 2
    assert not wd._can_restart("x")
```

**Step 2: Implementa `hardware/watchdog.py`**

```python
"""
hardware/watchdog.py — Supervisor thread che monitora i thread background.

Se un thread monitored muore inaspettatamente, chiama il callback on_dead.
Limita i riavvii automatici a max_restarts per thread.
"""
import logging
import threading
import time

logger = logging.getLogger(__name__)


class ThreadWatchdog:
    def __init__(self, check_interval: float = 5.0, max_restarts: int = 3):
        self._interval       = check_interval
        self._max_restarts   = max_restarts
        self._watched: list[tuple] = []  # (thread, on_dead_cb)
        self._restart_counts: dict[str, int] = {}
        self._stop           = threading.Event()
        self._thread         = threading.Thread(
            target=self._run, name="watchdog", daemon=True)

    def watch(self, thread: threading.Thread, on_dead=None):
        self._watched.append((thread, on_dead))

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _can_restart(self, name: str) -> bool:
        return self._restart_counts.get(name, 0) < self._max_restarts

    def _run(self):
        while not self._stop.wait(self._interval):
            for thread, on_dead in list(self._watched):
                if not thread.is_alive():
                    name = thread.name
                    logger.warning("Watchdog: thread '%s' morto", name)
                    if on_dead and self._can_restart(name):
                        self._restart_counts[name] = \
                            self._restart_counts.get(name, 0) + 1
                        on_dead(name)
                    elif not self._can_restart(name):
                        logger.error(
                            "Watchdog: '%s' ha superato max_restarts=%d",
                            name, self._max_restarts)
```

**Step 3: Esegui i test**

```bash
pytest tests/hardware/test_watchdog.py -v
```
Atteso: 3 PASS

**Step 4: Integra in `main.py`**

```python
from hardware.watchdog import ThreadWatchdog

# In App.__init__, dopo start() di tutti i thread:
self.watchdog = ThreadWatchdog(check_interval=10.0)
self.watchdog.watch(self.radio._reader_thread,
                    on_dead=lambda _: self.radio._reconnect_loop())
self.watchdog.start()
```

**Step 5: Commit**

```bash
git add hardware/watchdog.py tests/hardware/test_watchdog.py main.py
git commit -m "feat: watchdog thread — monitora e riavvia thread background morti"
```

---

### Task 12: Schermata diagnostica avvio

**Files:**
- Create: `ui/startup_check.py`
- Modify: `main.py`

**Step 1: Implementa `ui/startup_check.py`**

```python
"""
ui/startup_check.py — Schermata diagnostica pre-avvio.

Verifica sequenzialmente: serial port → I2C bus → GPIO pin conflict.
Mostra risultati e permette di continuare in demo mode se qualcosa manca.
"""
import os
import tkinter as tk
from .base_screen import BaseScreen


def run_startup_checks(cfg: dict) -> list[dict]:
    """Esegui tutti i check. Restituisce lista di {name, ok, message}."""
    results = []

    # Check 1: serial port
    port = cfg.get("serial_port", "/dev/ttyUSB0")
    port_ok = os.path.exists(port)
    results.append({
        "name":    f"Serial {port}",
        "ok":      port_ok,
        "message": "trovata" if port_ok else "non trovata — demo mode attivo",
    })

    # Check 2: I2C bus
    i2c_bus = cfg.get("i2c", {}).get("bus", 1)
    i2c_path = f"/dev/i2c-{i2c_bus}"
    i2c_ok = os.path.exists(i2c_path)
    results.append({
        "name":    f"I2C bus {i2c_path}",
        "ok":      i2c_ok,
        "message": "disponibile" if i2c_ok else "non disponibile",
    })

    # Check 3: GPIO conflict (usa GPIOConfigurator)
    try:
        from hardware.gpio_config import GPIOConfigurator
        gpio_cfg = GPIOConfigurator.from_settings(cfg.get("hardware", {}))
        errors = gpio_cfg.validate()
        results.append({
            "name":    "GPIO pin conflict",
            "ok":      len(errors) == 0,
            "message": "nessun conflitto" if not errors else "; ".join(errors),
        })
    except Exception as e:
        results.append({"name": "GPIO", "ok": False, "message": str(e)})

    return results


class StartupCheckScreen(BaseScreen):
    def build(self):
        self._on_continue = None
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        tk.Label(self, text="🔍 Diagnostica Avvio",
                 bg=self.bg, fg=self.fg,
                 font=self.f_large).grid(row=0, column=0, pady=12)

        self._results_frame = tk.Frame(self, bg=self.bg)
        self._results_frame.grid(row=1, column=0, sticky="nsew", padx=16)

        btn_frame = tk.Frame(self, bg=self.bg)
        btn_frame.grid(row=2, column=0, pady=10)
        tk.Button(btn_frame, text="▶ Continua",
                  command=self._continue,
                  bg=self.accent, fg="white",
                  font=self.f_normal, padx=20).pack()

    def show_results(self, results: list[dict]):
        for r in results:
            row = tk.Frame(self._results_frame, bg=self.card, pady=4, padx=8)
            row.pack(fill="x", pady=2)
            icon  = "✓" if r["ok"] else "✗"
            color = self.online if r["ok"] else self.error
            tk.Label(row, text=icon, bg=self.card, fg=color,
                     font=self.f_normal, width=2).pack(side="left")
            tk.Label(row, text=r["name"], bg=self.card, fg=self.fg,
                     font=self.f_small, width=20, anchor="w").pack(side="left")
            tk.Label(row, text=r["message"], bg=self.card, fg="#aaaaaa",
                     font=self.f_small, anchor="w").pack(side="left", fill="x")

    def _continue(self):
        if self._on_continue:
            self._on_continue()
```

**Step 2: Integra in `main.py`**

Prima di mostrare la schermata principale, esegui i check e mostra `StartupCheckScreen`. Dopo tap "Continua", carica la Home Screen normalmente.

**Step 3: Smoke test**

```bash
python3 main.py
```
Atteso: schermata diagnostica con check serial=✗ (non siamo su Pi), I2C=✗, GPIO=✓. Tap "Continua" porta alla Home.

**Step 4: Commit**

```bash
git add ui/startup_check.py main.py
git commit -m "feat: schermata diagnostica avvio — verifica serial/I2C/GPIO prima dell'UI"
```

---

## WAVE 4 — Docs

---

### Task 13: README migliorato

**Files:**
- Modify: `README.md`

**Step 1: Aggiungi le sezioni mancanti**

Struttura target:

```markdown
# Mesh-Pi

[badge Python] [badge License] [badge Platform]

Terminal UI Meshtastic per Raspberry Pi — schermo touch 3.5", display 480×320.

## Screenshot / Demo
(GIF demo mode)

## Hardware Supportato
| Componente | Modelli testati |
|...

## Quick Start (5 passi)
1. ...

## Architettura
(breve + link a docs/architecture.md)

## Contributing
(link a CONTRIBUTING.md)

## Troubleshooting
(link a docs/troubleshooting.md)
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: migliora README con quick start, hardware supportato, badge"
```

---

### Task 14: CONTRIBUTING.md

**Files:**
- Create: `CONTRIBUTING.md`

**Step 1: Crea `CONTRIBUTING.md`** con sezioni:

```markdown
# Contributing a Mesh-Pi

## Setup ambiente dev (macOS/Linux, no hardware)
## Struttura del codice
## Convenzioni commit
## Come aggiungere un sensore I2C
## Come aggiungere una schermata UI
## Aprire una PR
```

**Step 2: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: aggiungi CONTRIBUTING.md per contributor open source"
```

---

### Task 15: Troubleshooting + Architecture docs

**Files:**
- Create: `docs/troubleshooting.md`
- Create: `docs/architecture.md`

**Step 1: Crea `docs/troubleshooting.md`**

Formato per ogni problema: **Sintomo** → **Causa** → **Soluzione**.
Coprire: serial port, Tkinter mancante, I2C bus error, GPIO permission denied, demo mode non si avvia.

**Step 2: Crea `docs/architecture.md`**

- Diagramma ASCII moduli e relazioni
- Threading model con flusso dati
- Pattern cross-thread (`widget.after()`)
- Come aggiungere hardware

**Step 3: Commit**

```bash
git add docs/troubleshooting.md docs/architecture.md
git commit -m "docs: aggiungi troubleshooting guide e architettura del progetto"
```

---

## Riepilogo Task

| # | Task | Wave | File principali |
|---|------|------|-----------------|
| 0 | Setup pytest | Setup | `tests/`, `requirements-dev.txt` |
| 1 | HardwareStatus | W1 | `hardware/status.py` |
| 2 | Status su I2CManager | W1 | `hardware/i2c_manager.py` |
| 3 | Sensori I2C personalizzabili | W1 | `hardware/i2c_manager.py` |
| 4 | GPIOConfigurator | W1 | `hardware/gpio_config.py` |
| 5 | Refactor settings → ui/settings/ | W1 | `ui/settings/` |
| 6 | TelemetryStore | W2 | `data/telemetry_store.py` |
| 7 | Debug Screen multi-tab | W2 | `ui/debug_screen.py` |
| 8 | Badge messaggi nav bar | W2 | `ui/base_screen.py` |
| 9 | Pannello espanso nodi | W2 | `ui/nodes_screen.py` |
| 10 | Reconnect backoff | W3 | `radio/meshtastic_client.py` |
| 11 | Watchdog thread | W3 | `hardware/watchdog.py` |
| 12 | Diagnostica avvio | W3 | `ui/startup_check.py` |
| 13 | README | W4 | `README.md` |
| 14 | CONTRIBUTING.md | W4 | `CONTRIBUTING.md` |
| 15 | Troubleshooting + Arch docs | W4 | `docs/` |
