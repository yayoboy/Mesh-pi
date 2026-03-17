# Troubleshooting Mesh-Pi

---

## Problemi comuni

---

### L'app non si avvia — `ModuleNotFoundError: No module named 'tkinter'`

**Sintomo:** Errore all'avvio su Linux/Raspberry Pi OS.

**Causa:** Tkinter deve essere installato tramite apt, NON pip.

**Soluzione:**

```bash
sudo apt install python3-tk
```

**Nota:** Non usare `pip install tkinter` — non funziona.

---

### Serial port non trovata — demo mode attivo

**Sintomo:** La schermata diagnostica mostra "Serial /dev/ttyUSB0 non trovata".

**Causa:** Il radio Heltec non e' collegato o non e' riconosciuto.

**Soluzioni:**

1. Verifica il cavo USB
2. Controlla la porta: `ls /dev/ttyUSB*`
3. Se la porta e' diversa, aggiorna `config/settings.json`:

   ```json
   "serial_port": "/dev/ttyUSB1"
   ```

4. Aggiungi il tuo utente al gruppo dialout:

   ```bash
   sudo usermod -a -G dialout $USER
   # Richiede logout e login per avere effetto
   ```

---

### I2C bus non disponibile

**Sintomo:** La schermata diagnostica mostra "I2C bus /dev/i2c-1 non disponibile".

**Causa:** I2C non e' abilitato sul Raspberry Pi.

**Soluzione:**

```bash
sudo raspi-config
# Interface Options -> I2C -> Enable
sudo reboot
```

In alternativa, aggiungi manualmente a `/boot/firmware/config.txt`:

```
dtparam=i2c_arm=on
```

Poi riavvia.

---

### GPIO permission denied

**Sintomo:** Errore `PermissionError` all'avvio con encoder o buzzer abilitati.

**Causa:** L'utente non ha i permessi per accedere ai GPIO.

**Soluzione:**

```bash
sudo usermod -a -G gpio $USER
# Poi logout e login
```

---

### Conflitto pin GPIO

**Sintomo:** La schermata diagnostica mostra "Pin X e Y entrambi assegnati a '...'".

**Causa:** Due periferiche hanno lo stesso pin in `config/settings.json`.

**Soluzione:** Vai su Settings → GPIO, assegna pin diversi a ciascuna funzione. I pin BCM disponibili dipendono dal modello di Raspberry Pi — consulta il pinout con `pinout` (richiede `python3-gpiozero`).

---

### I sensori I2C non leggono

**Sintomo:** Il tab Telemetria in Debug Screen e' vuoto.

**Cause possibili:**

1. **Sensori non abilitati** — vai su Settings → I2C e attiva i sensori
2. **Indirizzo sbagliato** — usa `i2cdetect` per scoprire gli indirizzi reali:

   ```bash
   # Installa i2c-tools se non presente
   sudo apt install i2c-tools

   # Scansione bus I2C 1 (default)
   i2cdetect -y 1
   ```

3. **Bus I2C sbagliato** — default e' bus 1, verifica su quale bus sono i sensori

**Indirizzo tipico per sensore:**

| Sensore | Indirizzo default |
|---------|-------------------|
| INA219 | 0x40 |
| BME280 | 0x76 o 0x77 |
| SHT30 | 0x44 o 0x45 |

---

### Tkinter non trova i font DejaVu

**Sintomo:** Testo sfocato o font diverso dal previsto.

**Causa:** Il font `DejaVu Sans` non e' installato.

**Soluzione:**

```bash
sudo apt install fonts-dejavu
```

---

### L'app crasha all'avvio dopo un aggiornamento

**Causa probabile:** `config/settings.json` manca di chiavi aggiunte nella nuova versione.

**Soluzione rapida:**

```bash
cd Mesh-pi
git stash
python3 main.py
```

Se funziona, il problema e' nelle modifiche locali. Confronta il tuo `settings.json` con `config/settings.json` nel repo per trovare le chiavi mancanti.

---

### Errore `BadPinsError` all'avvio con GPIO abilitati

**Sintomo:** Eccezione `gpiozero.exc.BadPinsError` all'avvio.

**Causa:** gpiozero non trova un pin factory backend sul sistema.

**Soluzione su Raspberry Pi OS Bookworm:**

```bash
sudo apt install python3-lgpio
```

Su sistemi non-Pi (sviluppo desktop), il GPIO entra automaticamente in stub mode — nessuna azione necessaria.

---

## Log di sistema

```bash
# Se avviato come servizio systemd
journalctl -u meshtastic-ui -f

# Log file rotante (quando avviato manualmente)
tail -f /tmp/meshtastic-ui.log

# Log completo dall'ultimo avvio del servizio
journalctl -u meshtastic-ui --since today
```

---

## Diagnostica veloce

Esegui questo script per una panoramica rapida dello stato del sistema:

```bash
# Verifica Python e tkinter
python3 -c "import tkinter; print('tkinter OK:', tkinter.TkVersion)"

# Verifica porta seriale
ls /dev/ttyUSB* 2>/dev/null || echo "Nessuna porta ttyUSB trovata"

# Verifica I2C
ls /dev/i2c* 2>/dev/null || echo "I2C non abilitato"

# Verifica GPIO (richiede gpiozero installato)
python3 -c "from gpiozero import Device; print('gpiozero OK')"

# Scansione sensori I2C
i2cdetect -y 1 2>/dev/null || echo "i2c-tools non installato (sudo apt install i2c-tools)"
```
