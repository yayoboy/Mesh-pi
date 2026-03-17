import os
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
        assert samples[0].sensors["Batteria"] == 12.1
    finally:
        os.unlink(path)

def test_store_sensor_names():
    store = TelemetryStore()
    store.add(TelemetrySample(rssi=-80, snr=0, sensors={"Int": 20.0, "Ext": 25.0}))
    names = store.sensor_names()
    assert "Int" in names
    assert "Ext" in names

def test_store_empty_load_no_crash():
    store = TelemetryStore(persist_path="/tmp/nonexistente_xyz.json")
    store.load()  # non deve crashare
    assert store.get_samples() == []
