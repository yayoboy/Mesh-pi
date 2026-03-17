# Architettura Mesh-Pi

## Panoramica

```
┌─────────────────────────────────────────────────────────┐
│                    main.py (App)                        │
│  ┌──────────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │  Radio   │  │  Hardware   │  │   TelemetryStore │   │
│  │ Client   │  │  Manager    │  │   (data/)        │   │
│  └────┬─────┘  └──────┬──────┘  └────────┬─────────┘   │
│       │               │                  │              │
│  ┌────▼───────────────▼──────────────────▼──────────┐  │
│  │              Tkinter UI (ui/)                    │  │
│  │  Home │ Chat │ Nodes │ Debug │ Settings │ Startup │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Threading Model

| Thread | Modulo | Scopo |
|--------|--------|-------|
| **Main** | Tkinter `.mainloop()` | Rendering UI, eventi touch |
| **Radio reader** | `radio/meshtastic_client.py` | I/O seriale, callbacks |
| **Demo loop** | `radio/meshtastic_client.py` | Traffico simulato (senza hardware) |
| **GPS reader** | `hardware/gps_reader.py` | Parser NMEA seriale |
| **Buzzer worker** | `hardware/buzzer.py` | Tone patterns async |
| **I2C poller** | `hardware/i2c_manager.py` | Polling sensori ogni 2s |
| **Watchdog** | `hardware/watchdog.py` | Monitora e riavvia thread morti |

**Regola fondamentale:** Tutti gli aggiornamenti GUI devono passare per:

```python
widget.after(0, callback)
```

Mai chiamare metodi Tkinter da thread non-main. Ogni violazione causa race conditions difficili da riprodurre.

---

## Moduli

### radio/meshtastic_client.py

- Wrapper thread-safe attorno alla libreria `meshtastic`
- Pattern Observer: callbacks `on_message`, `on_node_update`, `on_status_change`
- Reconnect automatico con backoff esponenziale (`ReconnectPolicy`)
- Demo mode: 3 nodi simulati, messaggi random, RSSI/SNR realistici

### hardware/

| File | Responsabilita' |
|------|----------------|
| `gpio_manager.py` | Dispatcher centrale: mappa eventi GPIO → azioni applicazione |
| `gpio_config.py` | Modello dati pin→funzione con validazione conflitti |
| `i2c_manager.py` | Orchestratore sensori I2C con `SensorConfig` personalizzabile |
| `gps_reader.py` | Parser NMEA 0183 su porta seriale, emette coordinate |
| `buzzer.py` | Toni asincroni (pattern: alert, conferma, errore) |
| `watchdog.py` | Supervisor thread con protezione max-restart |
| `status.py` | `HardwareStatus` enum: ok / warning / error / disabled |

### ui/

| File | Responsabilita' |
|------|----------------|
| `base_screen.py` | BaseScreen: colori, font, helpers `card()`, `nav_bar()`, `chip()` |
| `home_screen.py` | Dashboard: stato rete, log eventi, metriche TX/RX |
| `chat_screen.py` | Chat: bolle messaggi, tastiera on-screen, invio |
| `nodes_screen.py` | Lista nodi: card per nodo, segnale, batteria, hop |
| `debug_screen.py` | Telemetria: sparkline RSSI, log viewer in-app |
| `settings/` | 4 tab: Display, GPIO, GPS, Sensori I2C |
| `startup_check.py` | Diagnostica pre-avvio: serial / I2C / GPIO |
| `keyboard.py` | Tastiera on-screen QWERTY + numerica |
| `icons.py` | Icone Unicode, renderer barre segnale e batteria |

### data/

- `telemetry_store.py` — Buffer circolare thread-safe, persiste in JSON su disco. Usato da Debug Screen per la sparkline RSSI.

---

## Flusso dati radio → UI

```
Meshtastic radio (Heltec LoRa V3)
    |
    | USB seriale /dev/ttyUSB0
    v
meshtastic_client._reader_thread
    |
    | callback (thread non-main)
    v
App._on_message(msg)
    |
    | widget.after(0, ...)   <-- crossing thread boundary
    v
ChatScreen.add_message(msg)    <-- aggiornamento GUI thread-safe
HomeScreen.add_event(msg)
TelemetryStore.append(msg)
```

In demo mode, `_demo_loop_thread` sostituisce il reader seriale e produce lo stesso tipo di eventi.

---

## Config

`config/settings.json` e' l'unica fonte di verita' per:

| Categoria | Chiavi |
|-----------|--------|
| Connessione | `serial_port`, `serial_baud` |
| Display | `display_width`, `display_height` |
| Font | `font_family`, `font_family_mono`, `font_size_*` |
| Palette | `bg_color`, `card_color`, `accent_color`, ... |
| Nodo | `node_name` |
| GPIO | `encoder_clk`, `encoder_dt`, `button_*`, `buzzer_pin` |
| GPS | `gps_enabled`, `gps_port`, `gps_baud` |
| Sensori I2C | `i2c_sensors` (array di `SensorConfig`) |

Per override locali non tracciati da git: `config/settings.local.json` (stesso formato, valori che sovrascrivono).

---

## Pattern architetturali

### Observer (radio → UI)

Il client radio non conosce le schermate. Le schermate si registrano come observer tramite callback passati ad `App`. Questo permette di aggiungere nuovi observer senza modificare il client radio.

### HardwareStatus

Ogni sottosistema hardware espone un `HardwareStatus`. La schermata di startup legge tutti gli status e decide se continuare o mostrare warning. Nessun sottosistema crasha l'app: ogni errore hardware produce `status=error` e la funzionalita' viene disabilitata gracefully.

### Demo mode

Il flag `demo_mode` e' impostato dal client radio, non dall'app. L'UI non deve sapere se e' in demo mode: riceve gli stessi callback con gli stessi tipi di dati. Questo garantisce che la UI funzioni sempre correttamente con dati reali.

### Thread watchdog

Il watchdog controlla periodicamente che i thread hardware siano vivi. Se un thread muore (eccezione non gestita), il watchdog lo riavvia fino a `max_restarts`. Superato il limite, imposta lo status del modulo su `error` e smette di riavviare.
