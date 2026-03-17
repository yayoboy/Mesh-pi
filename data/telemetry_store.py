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

DEFAULT_PATH  = "/tmp/telemetry.json"
DEFAULT_HOURS = 24
SAMPLES_PER_H = 120  # campione ogni 30s → 120/h


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
        cap        = max_samples or (max_hours * SAMPLES_PER_H)
        self._buf  = deque(maxlen=cap)
        self._lock = threading.Lock()
        self._path = persist_path

    def add(self, sample: TelemetrySample):
        with self._lock:
            self._buf.append(sample)

    def get_samples(self) -> list:
        with self._lock:
            return list(self._buf)

    def sensor_names(self) -> list:
        names: set = set()
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
