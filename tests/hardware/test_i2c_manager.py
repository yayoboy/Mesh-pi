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

def test_i2c_manager_exposes_status():
    mgr = I2CManager(BASE_CFG)
    assert hasattr(mgr, "status")

def test_i2c_manager_status_disabled_no_sensors():
    mgr = I2CManager(BASE_CFG)
    assert mgr.status.level == StatusLevel.DISABLED

def test_i2c_manager_status_not_crash_bad_bus():
    cfg = {"i2c": {"bus": 99, "poll_interval_ms": 100, "sensors": []}}
    mgr = I2CManager(cfg)
    # non deve crashare — status deve essere DISABLED o ERROR
    assert mgr.status.level in (StatusLevel.DISABLED, StatusLevel.ERROR)
