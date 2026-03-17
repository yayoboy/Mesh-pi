"""
hardware/watchdog.py — Supervisor thread che monitora i thread background.
"""
import logging
import threading

logger = logging.getLogger(__name__)


class ThreadWatchdog:
    def __init__(self, check_interval: float = 5.0, max_restarts: int = 3):
        self._interval       = check_interval
        self._max_restarts   = max_restarts
        self._watched: list  = []  # (thread, on_dead_cb)
        self._restart_counts: dict = {}
        self._stop           = threading.Event()
        self._thread         = threading.Thread(
            target=self._run, name="watchdog", daemon=True)

    def watch(self, thread: threading.Thread, on_dead=None):
        self._watched.append((thread, on_dead))

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _can_restart(self, name: str) -> bool:
        return self._restart_counts.get(name, 0) < self._max_restarts

    def _run(self):
        while not self._stop.wait(self._interval):
            for thread, on_dead in list(self._watched):
                if not thread.is_alive():
                    name = thread.name
                    logger.warning("Watchdog: thread '%s' morto", name)
                    if on_dead and self._can_restart(name):
                        self._restart_counts[name] = \
                            self._restart_counts.get(name, 0) + 1
                        try:
                            on_dead(name)
                        except Exception as e:
                            logger.error("Watchdog restart callback error: %s", e)
                    elif not self._can_restart(name):
                        logger.error(
                            "Watchdog: '%s' superato max_restarts=%d",
                            name, self._max_restarts)
