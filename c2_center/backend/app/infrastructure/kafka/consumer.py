"""
Kafka consumer adapter.

Subscribes to the c2_metadata topic and routes JSON messages to per-stream
metadata buffers consumed by the sync engine.

Architecture note (2026-05-11):
  DeepStream's nvmsgconv New-API emits ONE Kafka message per detected object.
  All messages from the same frame share the same timestamp. This consumer
  groups them into a single list before handing them to the SyncEngine.

  The consumer runs on a DEDICATED THREAD (not an asyncio task) so that heavy
  CPU work on the asyncio event loop (annotation, JPEG encoding, WS send)
  cannot starve message consumption.
"""

import json
import logging
import threading
import time
from collections import defaultdict

from kafka import KafkaConsumer as SyncKafkaConsumer

from app.core.config import settings

logger = logging.getLogger(__name__)


class KafkaConsumerService:
    """
    Thread-based Kafka consumer that listens to DeepStream metadata messages.

    Uses a dedicated daemon thread for consumption, guaranteeing that asyncio
    event-loop starvation on the main thread cannot cause dropped or partially
    grouped metadata frames.

    Data flow:
      Kafka → _consume_thread → _building[stream] (per-object grouping)
                                → _ready[stream]   (complete frame, single-slot)
      SyncEngine → pop_latest() → reads _ready[stream]
    """

    def __init__(self) -> None:
        self._consumer: SyncKafkaConsumer | None = None
        self._thread: threading.Thread | None = None

        # Mapping: source_id (str) → semantic stream_id (str)
        self.stream_id_map: dict[str, str] = {}

        # --- Per-stream double-buffer (thread-safe via GIL) ---
        # _building: frame currently being assembled (objects still arriving)
        #   key = stream_id, value = (kafka_ts: float, data: dict)
        self._building: dict[str, tuple[float, dict]] = {}

        # _ready: last FULLY COMPLETED frame, ready for SyncEngine to pop
        #   key = stream_id, value = dict (the metadata payload with all objects)
        self._ready: dict[str, dict] = {}

        self._lock = threading.Lock()   # protects _building + _ready
        self._running = False

        # Track streams we've already warned about missing tracking_id to avoid log spam
        self._warned_missing_tracker: set[str] = set()

    def set_stream_mapping(self, source_index: int, stream_id: str) -> None:
        """Register that DeepStream source 'i' corresponds to backend 'stream_id'."""
        self.stream_id_map[str(source_index)] = stream_id
        logger.info("Kafka mapping registered: source %d -> %s", source_index, stream_id)

    async def start(self) -> None:
        """Start the Kafka consumer background thread."""
        logger.info(
            "Starting Kafka consumer: %s topic=%s",
            settings.KAFKA_BOOTSTRAP,
            settings.KAFKA_TOPIC,
        )
        # Generate a unique group ID on every startup to ignore committed offsets.
        # This ensures auto_offset_reset="latest" actually applies, preventing the 
        # consumer from processing historical backlogged messages after a restart.
        import uuid
        unique_group_id = f"{settings.KAFKA_GROUP_ID}_{uuid.uuid4().hex[:8]}"

        self._consumer = SyncKafkaConsumer(
            settings.KAFKA_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP,
            group_id=unique_group_id,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="latest",
            consumer_timeout_ms=500,  # poll returns after 500ms if no messages
        )
        self._running = True
        self._thread = threading.Thread(
            target=self._consume_thread,
            daemon=True,
            name="kafka-consumer",
        )
        self._thread.start()
        logger.info("Kafka consumer started successfully (dedicated thread).")

    async def stop(self) -> None:
        """Stop the consumer and join the background thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        if self._consumer:
            self._consumer.close()
        logger.info("Kafka consumer stopped.")

    def _consume_thread(self) -> None:
        """Main consume loop — runs in its own thread, never blocks asyncio."""
        logger.info("Kafka consume thread started.")
        while self._running:
            try:
                # poll() returns immediately with available records (up to max_records)
                records = self._consumer.poll(timeout_ms=100, max_records=500)
                for _tp, messages in records.items():
                    for msg in messages:
                        try:
                            self._process_message(msg.value)
                        except Exception:
                            logger.exception("Error processing Kafka message")
            except Exception:
                if self._running:
                    logger.exception("Kafka poll error, retrying in 1s...")
                    time.sleep(1.0)

        logger.info("Kafka consume thread exited.")

    def _process_message(self, data: dict) -> None:
        """Process a single Kafka message — group objects by frame timestamp."""
        raw_stream_id = data.get("stream_id") or data.get("source_id", "unknown")
        stream_id = self.stream_id_map.get(str(raw_stream_id), str(raw_stream_id))

        timestamp = float(data.get("timestamp", 0))
        objs = data.get("objects", [])

        # Warn once about missing tracker
        if objs:
            sample = objs[0]
            if "tracking_id" not in sample and stream_id not in self._warned_missing_tracker:
                logger.warning(
                    "Kafka message missing 'tracking_id' for stream %s. Sample: %s",
                    stream_id, str(sample)[:200],
                )
                self._warned_missing_tracker.add(stream_id)

        with self._lock:
            building = self._building.get(stream_id)

            if building is not None:
                build_ts, build_data = building
                if abs(build_ts - timestamp) < 0.001:
                    # Same frame — merge objects
                    build_data.setdefault("objects", []).extend(objs)
                    return
                else:
                    # New frame arrived -> previous frame is COMPLETE
                    # Publish previous frame to _ready slot
                    self._ready[stream_id] = build_data
                    n_objs = len(build_data.get("objects", []))
                    if not hasattr(self, '_diag_frame_count'):
                        self._diag_frame_count = 0
                    self._diag_frame_count += 1
                    if self._diag_frame_count <= 5:
                        logger.warning(
                            "[DIAG-KAFKA] Frame complete: stream=%s ts=%.3f objects=%d",
                            stream_id, build_ts, n_objs,
                        )

            # Start building the new frame
            self._building[stream_id] = (timestamp, data)

    async def pop_latest(self, stream_id: str) -> dict | None:
        """
        Return the latest complete metadata frame for a stream.

        Uses PEEK semantics: the data stays in _ready until the consumer
        thread overwrites it with a newer frame. This means every call
        returns the most recent complete frame (never None after bootstrap).
        
        Returns None only if NO frame has ever been completed for this stream.
        Thread-safe — called from the asyncio event loop.
        """
        with self._lock:
            return self._ready.get(stream_id)  # peek, don't pop

    async def pop_nearest(
        self, stream_id: str, target_ts: float, tolerance_ms: float = 50.0
    ) -> dict | None:
        """Legacy API — just delegates to pop_latest for backwards compatibility."""
        return await self.pop_latest(stream_id)

    @property
    def is_connected(self) -> bool:
        """Check if consumer is running."""
        return self._running and self._consumer is not None
