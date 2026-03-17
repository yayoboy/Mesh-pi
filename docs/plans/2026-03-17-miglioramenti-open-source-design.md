# Design: Miglioramenti Open Source Mesh-Pi

**Data:** 2026-03-17
**Branch:** claude/meshtastic-terminal-ui-5G5WG
**Obiettivo:** Rendere Mesh-Pi un progetto open source maturo e utilizzabile dalla community Meshtastic

---

## Contesto

Mesh-Pi è una Terminal UI Meshtastic per Raspberry Pi 3 A+ con display SPI 3.5" (480×320).
~4600 LOC Python/Tkinter. L'hardware non è ancora montato — sviluppo in demo mode.
Target: open source per la community Meshtastic.

---

## Approccio: Wave Parallele

4 wave sequenziali, ognuna producente commit indipendenti e testabili in demo mode.

---

## Wave 1 — Fondamenta (Refactor + Error Handling + Config)

### 1.1 Refactor `settings_screen.py` (642 LOC → moduli)

```
ui/settings/
├── __init__.py       # SettingsScreen principale, compone i tab
├── tab_display.py    # Font, colori, display
├── tab_gpio.py       # GPIO configurator (lista pin → funzione)
├── tab_gps.py        # GPS config
└── tab_sensors.py    # I2C sensori personalizzabili
```

`SettingsScreen` usa un widget tab-style per navigare tra le sezioni.

### 1.2 GPIO Configurator (lista)

- Lista semplice: ogni riga = pin GPIO + menu a tendina funzione
- Funzioni disponibili: `non usato | encoder CLK | encoder DT | encoder SW | button | buzzer | GPS TX | GPS RX`
- Stato pin: `libero | in uso | riservato sistema`
- Validazione real-time: impedisce assegnare lo stesso pin a due funzioni
- Salva in `config/settings.json`
- **Roadmap futura:** rappresentazione visiva pinout 40-pin (non in scope ora)

### 1.3 Sensori I2C Personalizzabili

Ogni sensore configurabile con:
- **Label libera** — es. "Temperatura Interna", "Temperatura Esterna", "Batteria Principale"
- **Ruolo** — `interno | esterno | ambiente | alimentazione | custom`
- **Indirizzo I2C** — selezionabile da scan automatico del bus
- **Multipli dello stesso tipo** — es. 2× SHT30 a `0x44` e `0x45` con label distinte
- Home Screen e Debug Screen usano le label personalizzate

### 1.4 Error Handling Robusto

Pattern unificato: ogni modulo hardware espone `status: ok | warning | error | disabled`

Aree coperte:
- **Serial port** — `/dev/ttyUSB0` non esiste → errore UI chiaro, non crash silenzioso
- **I2C** — indirizzo non trovato → messaggio specifico per tipo sensore
- **GPIO** — pin già in uso → warning + fallback automatico

---

## Wave 2 — UI Polish + Feature

### 2.1 Transizioni Schermate

Fade cross-dissolve 100ms tra schermate via Tkinter `after()`.
Leggero su Pi, non blocca il main thread.

### 2.2 Notifiche Messaggi

Quando arriva un messaggio su schermata diversa da Chat:
- Badge numerico sull'icona Chat nella nav bar (es. `✉ 3`)
- Flash accent color sulla top bar per 1 secondo
- Buzzer opzionale (già supportato, da collegare all'evento)

### 2.3 Storico Telemetria + Grafico Debug

Nuovo modulo `data/telemetry_store.py`:
- Campiona RSSI/SNR + tutti i sensori I2C attivi ogni 30s
- Persiste in `/tmp/telemetry.json` (max 24h, rotazione automatica)
- Persiste tra riavvii app, non tra reboot Pi

**Debug Screen diventa multi-tab:**
- **Tab "Radio"** — grafici RSSI/SNR/CH-UTIL + sparkline esistenti
- **Tab "Telemetria"** — nuovo:
  - Un grafico per sensore attivo, con **label personalizzata**
  - Asse X = tempo (ultimi 30min scrollabile), asse Y = valore + unità (°C, %, V, mA)
  - Colori distinti per sensore, legenda con label
  - Messaggio "Nessun sensore configurato" se vuoto

### 2.4 Schermata Nodi Migliorata

- Tap su nodo → pannello espanso con: coordinate GPS, telemetria sensori, storico RSSI
- Ordinamento: per segnale | per ultimo contatto | per nome

---

## Wave 3 — Reliability

### 3.1 Reconnessione Automatica Radio

- Retry loop con backoff esponenziale: 1s → 2s → 4s → 8s → max 30s
- Indicatore "Riconnessione..." in top bar durante tentativi
- Callback `on_reconnected()` che resetta statistiche

### 3.2 Watchdog Thread

- Thread supervisor monitora tutti i thread background (radio, GPS, I2C, buzzer)
- Thread morto inaspettatamente → riavvio automatico + log in debug viewer
- Max 3 riavvii consecutivi → segnala errore permanente nella UI

### 3.3 Stato Hardware Unificato

- Ogni modulo espone `status: ok | warning | error | disabled`
- Home Screen: indicatore compatto per ogni periferica attiva (verde/arancio/rosso)
- Tap sull'indicatore → dettaglio errore

### 3.4 Diagnostica Avvio

- `main.py` esegue check sequenziale prima dell'UI: serial port → I2C bus → GPIO pin conflict
- Errori mostrati in schermata di diagnostica dedicata
- Possibilità di continuare in demo mode se hardware non disponibile

---

## Wave 4 — Docs + Onboarding Open Source

### 4.1 README Migliorato

- Screenshot/GIF demo in modalità demo
- Tabella hardware supportato (Pi models, display, radio)
- Sezione "Quick Start" 5 passi
- Badge: Python version, license, platform

### 4.2 CONTRIBUTING.md

- Setup ambiente dev su macOS/Linux (demo mode, senza hardware)
- Mappa moduli con struttura codice
- Convenzioni commit e branch
- Tutorial: aggiungere un sensore I2C
- Tutorial: aggiungere una nuova schermata UI

### 4.3 Troubleshooting Guide (`docs/troubleshooting.md`)

Problemi comuni:
- Serial port non trovata
- Tkinter mancante (deve essere apt, non pip)
- I2C bus error
- GPIO permission denied

Formato: sintomo → causa → soluzione

### 4.4 Architettura Documentata (`docs/architecture.md`)

- Diagramma moduli e relazioni
- Threading model con flusso dati
- Flusso radio → UI

---

## Riepilogo

| Wave | Focus | File principali |
|------|-------|-----------------|
| 1 | Refactor + Error Handling + Config | `ui/settings/` (split), `hardware/*.py` |
| 2 | UI Polish + Telemetria + Notifiche | `data/telemetry_store.py`, `ui/debug_screen.py`, `ui/nodes_screen.py` |
| 3 | Reliability | `radio/meshtastic_client.py`, `main.py`, `hardware/watchdog.py` |
| 4 | Docs | `README.md`, `CONTRIBUTING.md`, `docs/` |

---

## Vincoli

- Tkinter puro — no dipendenze UI esterne
- Compatibile Python 3.9+
- Testabile in demo mode senza hardware
- Tutti gli update GUI via `widget.after(0, callback)`
- GPIO list ora, pinout visivo come roadmap futura
