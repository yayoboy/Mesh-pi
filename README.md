# Mesh-Pi — Meshtastic Terminal UI

Un'interfaccia grafica touchscreen per reti [Meshtastic](https://meshtastic.org) su **Raspberry Pi 3 Model A+**.
La radio LoRa (Heltec WiFi LoRa 32 V3) gestisce la rete mesh; il Raspberry Pi è solo il cervello dell'interfaccia.

---

## Architettura

```
Heltec WiFi LoRa 32 V3
  (firmware Meshtastic)
          │
          │  USB seriale (/dev/ttyUSB0)
          ▼
 Raspberry Pi 3 A+
          │
  ┌───────┴────────┐
  │  Thread seriale │  ← legge pacchetti, emette callback
  │  Thread demo    │  ← traffico finto se assente HW
  │  Thread GUI     │  ← Tkinter + .after() scheduling
  └───────┬────────┘
          │
   Display 3.5" SPI
   (touch, 480×320)
```

Tre livelli nettamente separati:

| Livello | Componente | File |
|---------|-----------|------|
| **Radio** | Meshtastic Python client | `radio/meshtastic_client.py` |
| **Logica** | Callback, buffer messaggi, statistiche | `radio/meshtastic_client.py` |
| **Interfaccia** | Tkinter touchscreen UI | `ui/` |

---

## Hardware

| Componente | Modello |
|-----------|---------|
| SBC | Raspberry Pi 3 Model A+ |
| Radio LoRa | Heltec WiFi LoRa 32 V3 |
| Display | 3.5" SPI touchscreen, 480×320 px |
| Connessione radio | USB seriale (`/dev/ttyUSB0`) |
| Alimentazione | Batteria 10 000 mAh + step-up 5 V |

**Consumi indicativi**

| Componente | Consumo |
|-----------|---------|
| Raspberry Pi 3 A+ | 3–5 W |
| Heltec LoRa V3 | ~0.5 W |
| Display 3.5" | ~1 W |
| **Totale** | **~5–6 W** |

---

## Struttura del progetto

```
Mesh-pi/
├── main.py                     # Entry point — App Tkinter, gestione schermate
├── requirements.txt            # Dipendenze Python con version bounds
├── install.sh                  # Setup automatico su Raspberry Pi OS
├── meshtastic-ui.service       # Systemd service per avvio automatico
├── .gitignore
│
├── config/
│   └── settings.json           # Porta seriale, palette colori, font, ecc.
│
├── radio/
│   └── meshtastic_client.py    # Client Meshtastic thread-safe + demo mode
│
└── ui/
    ├── base_screen.py          # Classe base: colori, font, helper widget
    ├── icons.py                # Icone Unicode, barre segnale, batteria
    ├── keyboard.py             # Tastiera on-screen per touchscreen
    ├── home_screen.py          # Schermata Home — stato rete
    ├── chat_screen.py          # Schermata Chat — messaggi
    ├── nodes_screen.py         # Schermata Nodi — lista nodi mesh
    └── debug_screen.py         # Schermata Debug — telemetria radio
```

---

## Installazione

### Requisiti di sistema

- Raspberry Pi OS **Bookworm** (o superiore) — Lite consigliato
- Python **3.9+** (3.11 su Bookworm)
- Display 3.5" SPI configurato e funzionante (`/dev/fb1` o simile)
- Heltec LoRa V3 con firmware Meshtastic collegato via USB

### Procedura

```bash
# 1. Clona il repository
git clone https://github.com/yayoboy/Mesh-pi.git
cd Mesh-pi

# 2. Esegui lo script di installazione (richiede sudo)
bash install.sh
```

`install.sh` esegue automaticamente:
1. Verifica Python ≥ 3.9
2. Installa pacchetti di sistema: `python3-venv`, `python3-tk`, `python3-dbus`, `libglib2.0-dev`
3. Crea un ambiente virtuale in `.venv/` con `--system-site-packages` (espone tkinter di sistema)
4. Installa le dipendenze Python nel venv
5. Aggiunge l'utente al gruppo `dialout` (accesso seriale)
6. Installa e abilita il servizio systemd

```bash
# 3. Avvio manuale (per test)
.venv/bin/python3 main.py

# 4. Avvio come servizio (dopo riavvio o esplicitamente)
sudo systemctl start meshtastic-ui

# Verifica log
journalctl -u meshtastic-ui -f
```

### Demo mode (senza hardware)

Se la libreria `meshtastic` non è installata o la radio non è collegata, il sistema entra automaticamente in **demo mode**: genera traffico finto con tre nodi simulati e messaggi casuali. Ideale per sviluppo e test della UI.

---

## Configurazione

Modifica `config/settings.json` per personalizzare il sistema:

```jsonc
{
    "serial_port": "/dev/ttyUSB0",   // Porta USB della radio
    "serial_baud": 115200,

    "display_width":  480,           // Risoluzione display
    "display_height": 320,

    "font_family":      "DejaVu Sans",
    "font_family_mono": "DejaVu Sans Mono",
    "font_size_large":  15,
    "font_size_normal": 12,
    "font_size_small":  10,

    // Palette colori (stile Meshtastic)
    "bg_color":          "#1B1B1F",  // Sfondo principale
    "card_color":        "#25252D",  // Card/superfici
    "accent_color":      "#67AB9F",  // Verde-teal Meshtastic
    "online_color":      "#4CAF50",  // Verde online
    "warning_color":     "#FF9800",  // Arancio warning
    "error_color":       "#EF5350",  // Rosso errore
    "sent_bubble_color": "#2A4A46",  // Bolla messaggi inviati
    "recv_bubble_color": "#2C2C35",  // Bolla messaggi ricevuti

    "node_name": "MESH-PI"           // Nome locale del nodo
}
```

Per override locali (non tracciati da git) crea `config/settings.local.json`.

---

## Schermate

### Home
Dashboard principale con:
- **Top bar**: dot connessione, contatore nodi, livello batteria
- **Status card**: barre segnale, RSSI/SNR/hop, uptime
- **Chip metrici**: pacchetti TX / RX
- **Log eventi**: stato connessione e messaggi in arrivo con timestamp

### Chat
- Messaggi ricevuti a **sinistra** (bolla teal scuro)
- Messaggi inviati a **destra** (bolla teal più caldo)
- Metadata per messaggio: RSSI, SNR, hop count
- Input con **tastiera on-screen** (appare al tocco del campo)

### Nodi
- Una **card per nodo** con badge colorato (short name)
- Barre segnale `▁▂▄█` (RSSI se ricevuto, SNR dal node db)
- Indicatore batteria `⚡████░`, hop count, età dell'ultimo ascolto
- Aggiornamento live ogni 5 secondi

### Debug
- Barre orizzontali RSSI e SNR con colore dinamico (verde/arancio/rosso)
- Chip: HOP / RX / TX / CH-UTIL
- Sparkline RSSI degli ultimi 60 campioni con linea di riferimento a -100 dBm

---

## Tastiera on-screen

Si attiva automaticamente toccando qualsiasi campo di testo.

| Tasto | Funzione |
|-------|---------|
| `⇧` | Maiuscolo (ritorna minuscolo dopo ogni lettera) |
| `⇩` | Minuscolo |
| `123` | Layout numeri e simboli |
| `abc` | Layout QWERTY |
| `⌫` | Cancella carattere |
| `OK` | Conferma e nasconde la tastiera |

---

## Dipendenze Python

| Pacchetto | Versione | Motivo |
|-----------|----------|--------|
| `meshtastic` | `>=2.5.0,<3.0.0` | Client radio principale |
| `PyPubSub` | `>=4.0.3,<5.0.0` | Event bus usato da meshtastic |
| `pyserial` | `>=3.5,<4.0` | Accesso porta USB seriale |
| `protobuf` | `>=4.21.12,<6.0.0` | Serializzazione proto3 |
| `requests` | `>=2.31.0,<3.0.0` | Usato da meshtastic internamente |
| `PyYAML` | `>=6.0.1,<7.0.0` | Configurazione meshtastic |

> **Nota**: `tkinter` deve essere installato come pacchetto di sistema (`python3-tk`), non tramite pip.
> **Nota**: `bleak` (BLE) è una dipendenza obbligatoria di meshtastic anche per connessioni USB. Richiede D-Bus su Linux (`python3-dbus`).

### Nota sul namespace protobuf (meshtastic ≥ 2.3.13)

A partire da meshtastic 2.3.13 i moduli protobuf sono stati spostati:

```python
# Vecchio (< 2.3.13) — non più valido
from meshtastic import mesh_pb2

# Nuovo (>= 2.3.13)
from meshtastic.protobuf import mesh_pb2
```

Questo progetto non importa protobuf direttamente, quindi non è impattato.

---

## Avvio automatico

Il servizio systemd viene installato da `install.sh`:

```bash
# Stato
sudo systemctl status meshtastic-ui

# Avvia / ferma / riavvia
sudo systemctl start   meshtastic-ui
sudo systemctl stop    meshtastic-ui
sudo systemctl restart meshtastic-ui

# Log in tempo reale
journalctl -u meshtastic-ui -f
```

Variabili d'ambiente nel service file:

| Variabile | Valore | Effetto |
|-----------|--------|---------|
| `MESHTASTIC_FULLSCREEN` | `1` | Finestra a tutto schermo |
| `MESHTASTIC_HIDE_CURSOR` | `1` | Nasconde il cursore mouse |

---

## Estensioni future

- **Mappa nodi**: visualizzazione GPS con `tkintermapview`
- **Notifiche sonore**: `pygame.mixer` per alert messaggi
- **Modalità repeater**: forward automatico dei pacchetti
- **Topologia mesh**: grafo dei nodi e dei link
- **Export log**: salvataggio messaggi su file JSON/CSV
