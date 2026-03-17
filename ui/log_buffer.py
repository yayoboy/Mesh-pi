"""
ui/log_buffer.py — In-memory circular log buffer for the debug screen.

Acts as a standard logging.Handler and stores the last MAX_RECORDS log
records in a thread-safe deque.  Any number of callbacks can subscribe to
receive new records as they arrive (called from the emitting thread, so
GUI callbacks must re-route via widget.after(0, ...)).

Usage:

    # In main.py (once, before any other imports that log):
    from ui.log_buffer import ui_log_handler
    logging.getLogger().addHandler(ui_log_handler)

    # In a screen:
    from ui.log_buffer import ui_log_handler
    ui_log_handler.on_new_record(lambda r: self.after(0, self._append_record, r))
    for r in ui_log_handler.get_records():
        self._append_record(r)
"""

import logging
import threading
from collections import deque
from typing import Callable

MAX_RECORDS = 400   # max log lines kept in memory


class UILogHandler(logging.Handler):
    """
    Thread-safe in-memory log handler.

    Records are stored as raw LogRecord objects so that consumers can
    format them however they like (level, colour, timestamp, etc.).
    """

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self._records: deque[logging.LogRecord] = deque(maxlen=MAX_RECORDS)
        self._lock    = threading.Lock()
        self._cbs: list[Callable[[logging.LogRecord], None]] = []

        # Compact formatter — used to produce the one-line string stored
        # alongside each record for quick rendering.
        self._fmt = logging.Formatter(
            fmt="%(asctime)s %(levelname).1s  %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )

    # ------------------------------------------------------------------ #
    # logging.Handler interface                                            #
    # ------------------------------------------------------------------ #

    def emit(self, record: logging.LogRecord) -> None:
        # Cache the formatted string on the record itself so screens
        # don't have to re-format on every render.
        record._ui_line = self._fmt.format(record)   # type: ignore[attr-defined]
        with self._lock:
            self._records.append(record)
        for cb in list(self._cbs):
            try:
                cb(record)
            except Exception:
                pass    # never let a callback crash the logger

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def get_records(self) -> list[logging.LogRecord]:
        """Return a snapshot of all buffered records (oldest → newest)."""
        with self._lock:
            return list(self._records)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    def on_new_record(
        self, cb: Callable[[logging.LogRecord], None]
    ) -> None:
        """
        Register a callback fired for every new record.
        Called from the thread that emitted the log message — GUI callbacks
        MUST use widget.after(0, ...) to stay on the Tkinter thread.
        """
        self._cbs.append(cb)

    def warn_count(self) -> int:
        """Number of buffered WARNING or higher records."""
        with self._lock:
            return sum(1 for r in self._records
                       if r.levelno >= logging.WARNING)


# Module-level singleton — import and register once in main.py
ui_log_handler = UILogHandler()
