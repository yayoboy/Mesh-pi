"""
ui/icons.py — Unicode icon helpers for the Meshtastic UI.

All functions return plain strings built from Unicode characters that are
present in DejaVu Sans / DejaVu Sans Mono (standard on Raspberry Pi OS).

Signal staircase uses Block Elements U+2581–U+2588 (▁▂▃▄▅▆▇█).
"""

# ── Nav bar icons ──────────────────────────────────────────────────────────
ICON_HOME     = "⌂"    # U+2302  HOUSE
ICON_CHAT     = "✉"    # U+2709  ENVELOPE
ICON_NODES    = "◉"    # U+25C9  FISHEYE / node
ICON_DEBUG    = "≡"    # U+2261  IDENTICAL TO  (data/signal lines)
ICON_SETTINGS = "⚙"    # U+2699  GEAR

# ── Status indicators ──────────────────────────────────────────────────────
DOT_ON  = "●"        # U+25CF
DOT_OFF = "○"        # U+25CB
ARROW_UP   = "↑"
ARROW_DOWN = "↓"
ARROW_HOP  = "→"

# ── Signal bars (4 levels, staircase) ─────────────────────────────────────
_SIG_CHARS  = ("▁", "▂", "▄", "█")   # increasing height
_SIG_EMPTY  = "·"


def signal_bars(rssi: int) -> str:
    """4-char staircase signal indicator from RSSI (dBm)."""
    if rssi >= -70:    level = 4
    elif rssi >= -85:  level = 3
    elif rssi >= -100: level = 2
    elif rssi >= -115: level = 1
    else:              level = 0
    return "".join(_SIG_CHARS[i] if i < level else _SIG_EMPTY
                   for i in range(4))


def signal_level(rssi: int) -> int:
    """0–4 signal quality from RSSI (dBm)."""
    if rssi >= -70:    return 4
    if rssi >= -85:    return 3
    if rssi >= -100:   return 2
    if rssi >= -115:   return 1
    return 0


def signal_bars_snr(snr: float) -> str:
    """4-char staircase from SNR (dB) — used for LoRa node-db entries.

    Meshtastic stores SNR (not RSSI) in the nodes dict; RSSI is only
    available on received packets (rxRssi).  SNR thresholds for LoRa:
      > 5 dB  → excellent  (4 bars)
      0–5 dB  → good       (3 bars)
    -10–0 dB  → fair       (2 bars)
    -20–-10   → poor       (1 bar)
      < -20   → none       (0 bars)
    """
    if snr > 5:    level = 4
    elif snr >= 0: level = 3
    elif snr >= -10: level = 2
    elif snr >= -20: level = 1
    else:            level = 0
    return "".join(_SIG_CHARS[i] if i < level else _SIG_EMPTY
                   for i in range(4))


def signal_level_snr(snr: float) -> int:
    """0–4 signal quality from SNR (dB)."""
    if snr > 5:      return 4
    if snr >= 0:     return 3
    if snr >= -10:   return 2
    if snr >= -20:   return 1
    return 0


# ── Battery ───────────────────────────────────────────────────────────────
_BAT_CHARS = ("░", "░", "▒", "▓", "█")   # fill levels


def battery_bar(pct: int) -> str:
    """5-char battery indicator. pct=-1 means unknown."""
    if pct < 0:
        return "⚡ ?"
    blocks = round(pct / 25)           # 0–4
    bar = "".join("█" if i < blocks else "░" for i in range(4))
    return f"⚡{bar} {pct:3d}%"


def battery_icon(pct: int) -> str:
    """Single compact battery icon (no bar)."""
    if pct < 0:
        return "⚡?"
    if pct >= 80: return "⚡▓▓▓▓"
    if pct >= 50: return "⚡▓▓▒░"
    if pct >= 20: return "⚡▓░░░"
    return "⚡▒░░░"


# ── Hop indicator ─────────────────────────────────────────────────────────

def hop_arrows(hops: int) -> str:
    """Arrow sequence for hop count."""
    if hops == 0:
        return "⊕ direct"
    return ARROW_HOP * min(hops, 4) + f" {hops}hop"


# ── Signal quality colour (call with cfg values) ───────────────────────────

def rssi_color(rssi: int, online: str, warning: str, error: str) -> str:
    if rssi >= -85:  return online
    if rssi >= -100: return warning
    return error
