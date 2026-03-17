import threading
import time
from hardware.watchdog import ThreadWatchdog


def test_watchdog_detects_dead_thread():
    events = []
    dead_thread = threading.Thread(target=lambda: None, name="test-dead")
    dead_thread.start()
    time.sleep(0.05)

    def on_dead(name):
        events.append(name)

    wd = ThreadWatchdog(check_interval=0.1)
    wd.watch(dead_thread, on_dead)
    wd.start()
    time.sleep(0.4)
    wd.stop()
    assert "test-dead" in events


def test_watchdog_ignores_alive_thread():
    events = []
    stop = threading.Event()
    alive = threading.Thread(target=lambda: stop.wait(), name="test-alive", daemon=True)
    alive.start()

    wd = ThreadWatchdog(check_interval=0.1)
    wd.watch(alive, lambda n: events.append(n))
    wd.start()
    time.sleep(0.3)
    wd.stop()
    stop.set()
    assert events == []


def test_watchdog_max_restarts():
    wd = ThreadWatchdog(max_restarts=2)
    wd._restart_counts["x"] = 2
    assert not wd._can_restart("x")


def test_watchdog_can_restart_below_max():
    wd = ThreadWatchdog(max_restarts=3)
    wd._restart_counts["y"] = 1
    assert wd._can_restart("y")


def test_watchdog_stops_cleanly():
    wd = ThreadWatchdog(check_interval=0.1)
    wd.start()
    wd.stop()
    # non deve bloccarsi
    assert True
