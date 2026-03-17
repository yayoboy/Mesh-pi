"""
Meshtastic radio client — runs in a background thread.

Thread model:
  MeshtasticClient.start() → spawns _reader_thread
  _reader_thread           → reads serial, fires callbacks
  Public API               → thread-safe via queue + lock
"""

import threading
import time
import logging
from datetime import datetime
from collections import deque
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Try real meshtastic; fall back to a stub so the UI works without hardware.
try:
    import meshtastic
    import meshtastic.serial_interface
    from pubsub import pub
    MESHTASTIC_AVAILABLE = True
except ImportError:
    MESHTASTIC_AVAILABLE = False
    logger.warning("meshtastic library not found — running in demo mode")

    # Provide a stub so default parameter values don't raise NameError
    class _PubStub:
        AUTO_TOPIC = None
        def subscribe(self, *a, **kw): pass
    pub = _PubStub()


class Message:
    """Immutable value object for a received or sent message."""

    def __init__(self, sender: str, text: str, rssi: int = 0,
                 snr: float = 0.0, hops: int = 0, timestamp: Optional[datetime] = None):
        self.sender = sender
        self.text = text
        self.rssi = rssi
        self.snr = snr
        self.hops = hops
        self.timestamp = timestamp or datetime.now()

    def __repr__(self):
        return f"<Message from={self.sender!r} text={self.text!r}>"


class NodeInfo:
    """Snapshot of a remote node."""

    def __init__(self, node_id: str, long_name: str = "", short_name: str = "",
                 rssi: int = 0, snr: float = 0.0, hops: int = 0,
                 last_heard: Optional[datetime] = None,
                 latitude: float = 0.0, longitude: float = 0.0,
                 battery_level: int = -1):
        self.node_id = node_id
        self.long_name = long_name
        self.short_name = short_name or node_id[-4:]
        self.rssi = rssi
        self.snr = snr
        self.hops = hops
        self.last_heard = last_heard or datetime.now()
        self.latitude = latitude
        self.longitude = longitude
        self.battery_level = battery_level   # 0-100, -1 = unknown

    @property
    def display_name(self) -> str:
        return self.long_name or self.short_name or self.node_id

    @property
    def seconds_since_heard(self) -> float:
        return (datetime.now() - self.last_heard).total_seconds()


class RadioStats:
    """Latest radio-layer statistics."""

    def __init__(self):
        self.rssi: int = 0
        self.snr: float = 0.0
        self.hops: int = 0
        self.channel_util: float = 0.0
        self.air_util: float = 0.0
        self.rx_packets: int = 0
        self.tx_packets: int = 0


class ReconnectPolicy:
    """Backoff esponenziale per tentativi di riconnessione."""
    def __init__(self, base: int = 1, max_delay: int = 30):
        self._base    = base
        self._max     = max_delay
        self.attempts = 0

    def next_delay(self) -> int:
        delay = min(self._base * (2 ** self.attempts), self._max)
        self.attempts += 1
        return delay

    def reset(self):
        self.attempts = 0


class MeshtasticClient:
    """
    Thread-safe wrapper around the Meshtastic Python library.

    Usage:
        client = MeshtasticClient(port="/dev/ttyUSB0")
        client.on_message(my_callback)   # (Message) -> None
        client.on_node_update(my_cb)     # (NodeInfo) -> None
        client.start()
        ...
        client.send("Hello mesh!")
        ...
        client.stop()
    """

    RECONNECT_DELAY = 5  # seconds between reconnection attempts

    def __init__(self, port: str = "/dev/ttyUSB0", baud: int = 115200):
        self.port = port
        self.baud = baud

        self._lock = threading.Lock()
        self._interface = None
        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._reconnect_policy = ReconnectPolicy()

        self._message_callbacks: list[Callable[[Message], None]] = []
        self._node_callbacks: list[Callable[[NodeInfo], None]] = []
        self._status_callbacks: list[Callable[[str], None]] = []

        self.messages: deque[Message] = deque(maxlen=100)
        self.nodes: dict[str, NodeInfo] = {}
        self.stats = RadioStats()
        self.connected = False
        self.my_node_id: str = ""
        self.my_node_name: str = ""

        if not MESHTASTIC_AVAILABLE:
            self._start_demo_mode()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def on_message(self, callback: Callable[[Message], None]) -> None:
        self._message_callbacks.append(callback)

    def on_node_update(self, callback: Callable[[NodeInfo], None]) -> None:
        self._node_callbacks.append(callback)

    def on_status_change(self, callback: Callable[[str], None]) -> None:
        self._status_callbacks.append(callback)

    def start(self) -> None:
        if not MESHTASTIC_AVAILABLE:
            return  # demo mode already running
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._connection_loop,
                                        name="meshtastic-reader", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        self._disconnect()

    def send(self, text: str) -> bool:
        """Send a broadcast text message. Returns True on success."""
        if not MESHTASTIC_AVAILABLE:
            # echo back in demo mode
            msg = Message(sender="YOU", text=text)
            self._deliver_message(msg)
            return True

        with self._lock:
            if self._interface is None:
                return False
            try:
                self._interface.sendText(text)
                msg = Message(sender="YOU", text=text)
                self._deliver_message(msg)
                return True
            except Exception as exc:
                logger.error("send error: %s", exc)
                return False

    def get_nodes(self) -> list[NodeInfo]:
        with self._lock:
            return list(self.nodes.values())

    def get_messages(self) -> list[Message]:
        return list(self.messages)

    # ------------------------------------------------------------------ #
    # Internal — connection loop                                           #
    # ------------------------------------------------------------------ #

    def _connection_loop(self) -> None:
        while self._running:
            try:
                self._connect()
                # Connection succeeded — reset backoff
                self._reconnect_policy.reset()
                # Block until disconnected
                while self._running and self._interface is not None:
                    if self._stop_event.wait(1):
                        return
            except Exception as exc:
                logger.error("connection error: %s", exc)
                self._set_connected(False)
                if self._running:
                    delay = self._reconnect_policy.next_delay()
                    self._notify_status(f"Riconnessione tra {delay}s…")
                    if self._stop_event.wait(delay):
                        return

    def _connect(self) -> None:
        logger.info("connecting to %s", self.port)
        self._notify_status("Connessione a " + self.port + "…")

        iface = meshtastic.serial_interface.SerialInterface(self.port)

        pub.subscribe(self._on_receive, "meshtastic.receive.text")
        pub.subscribe(self._on_node_info, "meshtastic.node.updated")
        pub.subscribe(self._on_connection_established,
                      "meshtastic.connection.established")
        pub.subscribe(self._on_connection_lost, "meshtastic.connection.lost")

        with self._lock:
            self._interface = iface

    def _disconnect(self) -> None:
        with self._lock:
            iface = self._interface
            self._interface = None
        if iface:
            try:
                iface.close()
            except Exception:
                pass
        self._set_connected(False)

    # ------------------------------------------------------------------ #
    # Meshtastic pubsub callbacks (called from reader thread)             #
    # ------------------------------------------------------------------ #

    def _on_connection_established(self, interface, topic=pub.AUTO_TOPIC) -> None:
        try:
            my_info = interface.getMyNodeInfo()
            with self._lock:
                self.my_node_id = str(my_info.get("num", ""))
                user = my_info.get("user", {})
                self.my_node_name = user.get("longName", self.my_node_id)
            self._set_connected(True)
            self._refresh_nodes(interface)
        except Exception as exc:
            logger.error("post-connect error: %s", exc)

    def _on_connection_lost(self, interface, topic=pub.AUTO_TOPIC) -> None:
        self._disconnect()

    def _on_receive(self, packet, interface) -> None:
        try:
            decoded = packet.get("decoded", {})
            text = decoded.get("text", "")
            if not text:
                return

            from_id = str(packet.get("from", "???"))

            # rxRssi and rxSnr are per-packet radio metrics (only in received packets,
            # not stored in the nodes dict — that's why we update the node here).
            rssi = packet.get("rxRssi", 0)
            snr  = packet.get("rxSnr", 0.0)
            hops = packet.get("hopStart", packet.get("hopLimit", 0))

            with self._lock:
                self.stats.rssi = rssi
                self.stats.snr  = snr
                self.stats.hops = hops
                self.stats.rx_packets += 1
                # Back-fill the node's RSSI with the latest received-packet value
                if from_id in self.nodes:
                    self.nodes[from_id].rssi = rssi
                    self.nodes[from_id].snr  = snr

            node = self.nodes.get(from_id)
            sender = node.display_name if node else from_id[-4:]

            msg = Message(sender=sender, text=text, rssi=rssi, snr=snr, hops=hops)
            self._deliver_message(msg)
        except Exception as exc:
            logger.error("receive error: %s", exc)

    def _on_node_info(self, node, interface) -> None:
        try:
            node_id = str(node.get("num", ""))
            if not node_id:
                return

            user    = node.get("user", {})
            metrics = node.get("deviceMetrics", {})
            pos     = node.get("position", {})

            # lastHeard is a unix timestamp (int); convert to datetime
            last_heard_ts = node.get("lastHeard", 0)
            if last_heard_ts:
                last_heard = datetime.fromtimestamp(last_heard_ts)
            else:
                last_heard = datetime.now()

            # NOTE: RSSI is NOT stored in the nodes dict — it only comes from
            # received packets (rxRssi).  We preserve any RSSI we already
            # learned via _on_receive; SNR from the node dict is the link SNR
            # that Meshtastic stores after the last observed packet.
            existing = self.nodes.get(node_id)
            existing_rssi = existing.rssi if existing else 0

            # channelUtilization / airUtilTx — update global RadioStats too
            ch_util  = metrics.get("channelUtilization", 0.0)
            air_util = metrics.get("airUtilTx", 0.0)

            info = NodeInfo(
                node_id=node_id,
                long_name=user.get("longName", ""),
                short_name=user.get("shortName", ""),
                rssi=existing_rssi,                    # kept from last rx packet
                snr=node.get("snr", 0.0),              # link SNR from node db
                hops=node.get("hopsAway", 0),          # hop distance from us
                last_heard=last_heard,
                latitude=pos.get("latitude", 0.0),
                longitude=pos.get("longitude", 0.0),
                battery_level=metrics.get("batteryLevel", -1),
            )

            with self._lock:
                self.nodes[node_id] = info
                if ch_util:
                    self.stats.channel_util = ch_util
                if air_util:
                    self.stats.air_util = air_util

            for cb in self._node_callbacks:
                try:
                    cb(info)
                except Exception:
                    pass
        except Exception as exc:
            logger.error("node_info error: %s", exc)

    def _refresh_nodes(self, interface) -> None:
        try:
            for nid, node in (interface.nodes or {}).items():
                self._on_node_info(node, interface)
        except Exception as exc:
            logger.error("refresh_nodes error: %s", exc)

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _set_connected(self, state: bool) -> None:
        self.connected = state
        status = "Connesso" if state else "Disconnesso"
        self._notify_status(status)

    def _notify_status(self, msg: str) -> None:
        for cb in self._status_callbacks:
            try:
                cb(msg)
            except Exception:
                pass

    def _deliver_message(self, msg: Message) -> None:
        self.messages.append(msg)
        for cb in self._message_callbacks:
            try:
                cb(msg)
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Demo mode — generates fake traffic so the UI is testable            #
    # ------------------------------------------------------------------ #

    def _start_demo_mode(self) -> None:
        self.connected = True
        self.my_node_id = "!DEMO"
        self.my_node_name = "MESH-PI-DEMO"
        self.nodes = {
            "!aabb": NodeInfo("!aabb", "Base Alpha",   "ALFA", rssi=-85,  snr=7.5,  hops=0, battery_level=80),
            "!ccdd": NodeInfo("!ccdd", "Patrol Bravo", "BRAV", rssi=-102, snr=3.2,  hops=1, battery_level=45),
            "!eeff": NodeInfo("!eeff", "Relay Charlie","CHAR", rssi=-78,  snr=10.1, hops=0, battery_level=12),
        }
        self.stats.rssi = -85
        self.stats.snr = 7.5
        self.stats.hops = 1
        threading.Thread(target=self._demo_loop, daemon=True,
                         name="demo-loop").start()

    def _demo_loop(self) -> None:
        import random
        senders = [("Base Alpha", -85, 7.5, 0),
                   ("Patrol Bravo", -102, 3.2, 1),
                   ("Relay Charlie", -78, 10.1, 0)]
        texts = [
            "Posizione confermata, tutto regolare.",
            "Segnale debole sul settore nord.",
            "Cambio frequenza mesh previsto tra 5 min.",
            "Nuovo nodo rilevato in rete.",
            "Test link — risponde?",
            "Roger, ricevuto 5 su 5.",
        ]
        time.sleep(2)
        for cb in self._status_callbacks:
            try:
                cb("Demo — nessun hardware rilevato")
            except Exception:
                pass
        for cb in self._node_callbacks:
            for node in self.nodes.values():
                try:
                    cb(node)
                except Exception:
                    pass

        while True:
            time.sleep(random.uniform(4, 10))
            sender, rssi, snr, hops = random.choice(senders)
            text = random.choice(texts)
            msg = Message(sender=sender, text=text, rssi=rssi, snr=snr, hops=hops)
            with self._lock:
                self.stats.rssi = rssi
                self.stats.snr = snr
                self.stats.hops = hops
                self.stats.rx_packets += 1
            self._deliver_message(msg)
