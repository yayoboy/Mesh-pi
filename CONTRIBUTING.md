# Contribuire a Mesh-Pi

Benvenuto! Questa guida ti aiuta a configurare l'ambiente di sviluppo e a contribuire al progetto.

---

## Setup ambiente (macOS/Linux, senza hardware)

### Prerequisiti

- Python 3.9+
- `python3-tk` (su Linux: `sudo apt install python3-tk`)
- Git

### Installazione

```bash
git clone https://github.com/<tuo-fork>/Mesh-pi.git
cd Mesh-pi
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

> **Nota `--system-site-packages`:** necessario su Linux per esporre `tkinter` di sistema all'interno del venv. Su macOS puoi ometterlo se hai installato tkinter tramite Homebrew (`brew install python-tk`).

### Demo mode

L'app si avvia in demo mode automaticamente se il radio non e' collegato:

```bash
python3 main.py
```

Demo mode include 3 nodi simulati, messaggi casuali e tutte le schermate navigabili. Non richiede hardware.

### Eseguire i test

```bash
pytest tests/ -v
```

Tutti i test devono passare prima di aprire una Pull Request.

---

## Struttura del codice

| Directory/File | Contenuto |
|----------------|-----------|
| `main.py` | Entry point, App class, screen manager |
| `radio/` | Client Meshtastic (thread-safe, demo mode) |
| `hardware/` | GPIO, I2C, GPS, buzzer, encoder, watchdog |
| `ui/` | 5 schermate Tkinter + componenti (base, keyboard, icons) |
| `data/` | TelemetryStore (buffer circolare, persistenza JSON) |
| `config/` | settings.json — unica fonte di verita' della configurazione |
| `tests/` | Suite pytest |
| `docs/` | Documentazione tecnica (architettura, troubleshooting) |

Per la descrizione completa dei thread e del flusso dati, vedi [docs/architecture.md](docs/architecture.md).

---

## Convenzioni commit

Questo progetto usa la convenzione [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: aggiunge nuova funzionalita'
fix: corregge un bug
refactor: riorganizza codice senza cambiare funzionalita'
test: aggiunge o modifica test
docs: aggiorna documentazione
chore: aggiornamento dipendenze, config, tooling
style: formattazione, linting
perf: miglioramento prestazioni
```

Esempi reali:

```
feat: aggiungi sensore SHT31 in i2c_manager
fix: correggi race condition in TelemetryStore.append()
test: aggiungi test per ReconnectPolicy backoff
docs: aggiorna troubleshooting con errore I2C bus
```

---

## Come aggiungere un sensore I2C

1. Crea `hardware/sensor_NOME.py` con una classe `NOMESensor`
2. La classe deve avere `read() -> NomeReading | None`
3. Aggiungi il tipo in `hardware/i2c_manager.py` nella factory `_create_sensor()`
4. Aggiungi il tipo a `VALID_SENSOR_TYPES` se necessario
5. Testa con un `SensorConfig` fittizio in `tests/`

Esempio struttura minima:

```python
# hardware/sensor_sht31.py
from dataclasses import dataclass

@dataclass
class SHT31Reading:
    temperature: float   # gradi Celsius
    humidity: float      # percentuale relativa

class SHT31Sensor:
    def __init__(self, bus_number: int, address: int = 0x44):
        ...

    def read(self) -> SHT31Reading | None:
        ...
```

---

## Come aggiungere una schermata

1. Crea `ui/nome_screen.py` con `class NomeScreen(BaseScreen)`
2. Implementa `build()` usando le helper di `BaseScreen`:
   - `self.card(parent, **kw)` — superficie card con raggio bordi
   - `self.nav_bar(parent)` — barra di navigazione inferiore
   - `self.chip(parent, text, **kw)` — etichetta metrica compatta
3. Aggiungi in `main.py` nel dict `SCREENS`
4. Aggiungi il bottone di navigazione nella nav bar di `BaseScreen`

---

## TDD — Test Driven Development

Questo progetto preferisce TDD per le nuove funzionalita':

1. Scrivi il test prima del codice (RED)
2. Implementa il codice minimo per farlo passare (GREEN)
3. Refactora se necessario (REFACTOR)

```bash
# Esegui solo un test specifico durante lo sviluppo
pytest tests/test_telemetry_store.py -v

# Esegui tutti i test
pytest tests/ -v
```

---

## Pull Request

1. Fork del repo
2. Crea branch: `git checkout -b feat/nome-feature`
3. Scrivi test prima del codice (TDD)
4. Esegui `pytest tests/ -v` — tutti devono passare
5. Apri PR con descrizione chiara che include:
   - Cosa fa la modifica
   - Come testarla
   - Screenshot/video se modifica la UI

---

## Linee guida generali

- **Thread safety:** tutti gli aggiornamenti GUI devono usare `widget.after(0, callback)`. Mai chiamare metodi Tkinter da thread non-main.
- **Demo mode:** le nuove funzionalita' devono funzionare anche in demo mode (senza hardware).
- **Nessun hardcode:** porte, pin, indirizzi I2C, colori — tutto in `config/settings.json`.
- **Errori hardware:** usa `HardwareStatus` (ok/warning/error/disabled) invece di eccezioni non gestite.
