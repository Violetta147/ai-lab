"""
MQTT consumer adapter for c2_center.

Subscribes to traffic/tracked (published by data_pipeline tracking bridge) and
stores latest metadata per stream_id for SyncEngine.

Interface: identical to KafkaConsumerService — drop-in replacement.
Runs on a dedicated daemon thread (never blocks asyncio event loop).
"""

import json
import logging
import threading
import time

from paho.mqtt import client as mqtt_client

from app.core.config import settings

logger = logging.getLogger(__name__)


class MqttDetectionConsumerService:
    """
    Thread-based MQTT consumer. Data flow:
      MQTT broker (traffic/tracked) → _on_message → _ready[stream_id]
      SyncEngine → pop_latest(stream_id) → reads _ready[stream_id]
    """

    def __init__(self) -> None:
        client_id = f"{settings.MQTT_CLIENT_ID}_{int(time.time())}"
        try:
            self._client = mqtt_client.Client(
                mqtt_client.CallbackAPIVersion.VERSION1, client_id
            )
        except AttributeError:
            self._client = mqtt_client.Client(client_id)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        self._ready: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._running = False
        self._connected = False
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------ #
    # paho callbacks (run in consumer thread)
    # ------------------------------------------------------------------ #

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            client.subscribe(settings.MQTT_TOPIC, qos=settings.MQTT_QOS)
            logger.info(
                "[MQTT] Connected to %s:%d, subscribed to %s",
                settings.MQTT_BROKER,
                settings.MQTT_PORT,
                settings.MQTT_TOPIC,
            )
        else:
            self._connected = False
            logger.error("[MQTT] Connect failed rc=%d", rc)

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0 and self._running:
            logger.warning("[MQTT] Unexpected disconnect rc=%d", rc)

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode("utf-8"))
        except Exception as e:
            logger.warning("[MQTT] JSON parse error: %s", e)
            return

        # Prefer explicit stream_id, fall back to camera_id
        stream_id = str(data.get("stream_id") or data.get("camera_id", "unknown"))
        metadata = {
            "stream_id": stream_id,
            "timestamp": float(data.get("timestamp", time.time())),
            "objects": data.get("detections", data.get("objects", [])),
        }
        with self._lock:
            self._ready[stream_id] = metadata

    # ------------------------------------------------------------------ #
    # Background thread
    # ------------------------------------------------------------------ #

    def _run_thread(self) -> None:
        logger.info(
            "[MQTT] Consumer thread starting. broker=%s:%d topic=%s",
            settings.MQTT_BROKER,
            settings.MQTT_PORT,
            settings.MQTT_TOPIC,
        )
        while self._running:
            try:
                self._client.connect(
                    settings.MQTT_BROKER, settings.MQTT_PORT, keepalive=60
                )
                self._client.loop_forever()  # blocks; returns on disconnect
            except Exception as e:
                if self._running:
                    logger.error("[MQTT] Connection error: %s. Retrying in 2s...", e)
                    time.sleep(2.0)
        logger.info("[MQTT] Consumer thread exited.")

    # ------------------------------------------------------------------ #
    # Public API — identical to KafkaConsumerService
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(
            target=self._run_thread, daemon=True, name="mqtt-consumer"
        )
        self._thread.start()
        logger.info(
            "[MQTT] Consumer started (source: %s:%d, topic: %s)",
            settings.MQTT_BROKER,
            settings.MQTT_PORT,
            settings.MQTT_TOPIC,
        )

    async def stop(self) -> None:
        self._running = False
        try:
            self._client.disconnect()
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        logger.info("[MQTT] Consumer stopped.")

    async def pop_latest(self, stream_id: str) -> dict | None:
        """Peek semantics — same as KafkaConsumerService."""
        with self._lock:
            return self._ready.get(stream_id)

    async def pop_nearest(
        self, stream_id: str, target_ts: float, tolerance_ms: float = 50.0
    ) -> dict | None:
        return await self.pop_latest(stream_id)

    def set_stream_mapping(self, source_index: int, stream_id: str) -> None:
        """No-op: MQTT identifies streams by stream_id/camera_id directly."""
        pass

    @property
    def is_connected(self) -> bool:
        return self._running and self._connected
