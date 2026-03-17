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
