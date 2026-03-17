from hardware.i2c_manager import SensorConfig, VALID_ROLES

def test_sensor_config_defaults():
    cfg = {"type": "sht30", "enabled": False, "address": "0x44"}
    sc = SensorConfig(cfg)
    assert sc.label == "sht30"
    assert sc.role == "custom"
    assert sc.address == 0x44

def test_sensor_config_custom_label():
    cfg = {"type": "sht30", "enabled": True, "address": "0x44",
           "label": "Temperatura Interna", "role": "interno"}
    sc = SensorConfig(cfg)
    assert sc.label == "Temperatura Interna"
    assert sc.role == "interno"

def test_sensor_config_multiple_same_type():
    cfgs = [
        {"type": "sht30", "enabled": True, "address": "0x44", "label": "Int", "role": "interno"},
        {"type": "sht30", "enabled": True, "address": "0x45", "label": "Ext", "role": "esterno"},
    ]
    sensors = [SensorConfig(c) for c in cfgs]
    assert sensors[0].address != sensors[1].address
    assert sensors[0].label != sensors[1].label

def test_sensor_config_address_string_and_int():
    sc1 = SensorConfig({"type": "bme280", "enabled": False, "address": "0x76"})
    sc2 = SensorConfig({"type": "bme280", "enabled": False, "address": 118})
    assert sc1.address == 0x76
    assert sc2.address == 0x76

def test_sensor_config_valid_roles():
    valid = ["interno", "esterno", "ambiente", "alimentazione", "custom"]
    for role in valid:
        sc = SensorConfig({"type": "ina219", "enabled": False,
                           "address": "0x40", "role": role})
        assert sc.role == role

def test_sensor_config_invalid_role_defaults_to_custom():
    sc = SensorConfig({"type": "sht30", "enabled": False,
                       "address": "0x44", "role": "nonvalido"})
    assert sc.role == "custom"

def test_sensor_config_to_dict():
    cfg = {"type": "sht30", "enabled": True, "address": "0x44",
           "label": "Interno", "role": "interno"}
    sc = SensorConfig(cfg)
    d = sc.to_dict()
    assert d["label"] == "Interno"
    assert d["role"] == "interno"
    assert d["address"] == "0x44"
