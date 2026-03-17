from hardware.gpio_config import GPIOPinConfig, GPIOConfigurator, PIN_FUNCTIONS, RESERVED_PINS

def test_pin_functions_defined():
    assert "non usato" in PIN_FUNCTIONS
    assert "encoder CLK" in PIN_FUNCTIONS
    assert "button" in PIN_FUNCTIONS
    assert "buzzer" in PIN_FUNCTIONS

def test_reserved_pins_not_assignable():
    assert 1 in RESERVED_PINS   # 3.3V
    assert 2 in RESERVED_PINS   # 5V
    assert 6 in RESERVED_PINS   # GND

def test_pin_config_default():
    p = GPIOPinConfig(17)
    assert p.pin == 17
    assert p.function == "non usato"

def test_pin_config_assign():
    p = GPIOPinConfig(17)
    p.function = "encoder CLK"
    assert p.function == "encoder CLK"

def test_configurator_no_duplicate_pins():
    cfg = GPIOConfigurator()
    cfg.assign(17, "encoder CLK")
    cfg.assign(18, "encoder DT")
    errors = cfg.validate()
    assert errors == []

def test_configurator_detects_duplicate():
    cfg = GPIOConfigurator()
    cfg.assign(17, "encoder CLK")
    cfg.assign(17, "encoder DT")
    errors = cfg.validate()
    assert len(errors) == 1
    assert "17" in errors[0]

def test_configurator_to_settings():
    cfg = GPIOConfigurator()
    cfg.assign(17, "encoder CLK")
    cfg.assign(18, "encoder DT")
    d = cfg.to_settings_dict()
    assert d["encoder"]["pin_clk"] == 17
    assert d["encoder"]["pin_dt"] == 18

def test_configurator_from_settings():
    hw = {"encoder": {"pin_clk": 17, "pin_dt": 18, "pin_sw": 27}}
    cfg = GPIOConfigurator.from_settings(hw)
    assert cfg.get(17) == "encoder CLK"
    assert cfg.get(18) == "encoder DT"
    assert cfg.get(27) == "encoder SW"
