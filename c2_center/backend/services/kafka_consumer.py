"""
C2 Center Backend — Kafka Consumer Service

Subscribes to the c2_metadata topic and routes JSON messages
to per-stream metadata buffers for the sync engine.
"""

import asyncio
import json
import logging
from collections import defaultdict

from aiokafka import AIOKafkaConsumer

from config import settings

logger = logging.getLogger(__name__)


class KafkaConsumerService:
    """
    Async Kafka consumer that listens to DeepStream metadata messages.

    Each incoming JSON message is parsed and placed into a per-stream
    buffer (asyncio.Queue) keyed by stream_id.
    """

    def __init__(self) -> None:
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task | None = None
        # Per-stream metadata buffers: stream_id -> list of (timestamp, metadata)
        self.buffers: dict[str, list[tuple[float, dict]]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._running = False
        # Track streams we've already warned about missing tracking_id to avoid log spam
        self._warned_missing_tracker: set[str] = set()

    async def start(self) -> None:
        """Start the Kafka consumer background task."""
        logger.info(
            "Starting Kafka consumer: %s topic=%s",
            settings.KAFKA_BOOTSTRAP,
            settings.KAFKA_TOPIC,
        )
        self._consumer = AIOKafkaConsumer(
            settings.KAFKA_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP,
            group_id=settings.KAFKA_GROUP_ID,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="latest",
        )
        await self._consumer.start()
        self._running = True
        self._task = asyncio.create_task(self._consume_loop())
        logger.info("Kafka consumer started successfully.")

    async def stop(self) -> None:
        """Stop the consumer and cancel the background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._consumer:
            await self._consumer.stop()
        logger.info("Kafka consumer stopped.")

    async def _consume_loop(self) -> None:
        """Main consume loop — runs as a background task."""
        try:
            async for msg in self._consumer:
                if not self._running:
                    break
                try:
                    data = msg.value
                    stream_id = data.get("stream_id", "unknown")
                    timestamp = float(data.get("timestamp", 0))

                    # Basic schema validation: ensure objects list contains expected fields
                    objs = data.get("objects", [])
                    if objs:
                        sample = objs[0]
                        if "tracking_id" not in sample and stream_id not in self._warned_missing_tracker:
                            logger.warning(
                                "Kafka message missing 'tracking_id' for stream %s — analytics may fail. Sample: %s",
                                stream_id,
                                str(sample)[:200],
                            )
                            self._warned_missing_tracker.add(stream_id)

                    async with self._lock:
                        buffer = self.buffers[stream_id]
                        buffer.append((timestamp, data))
                        # Keep buffer bounded — discard old entries
                        if len(buffer) > 300:
                            self.buffers[stream_id] = buffer[-200:]

                except Exception:
                    logger.exception("Error processing Kafka message")

        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Kafka consume loop crashed")

    async def pop_nearest(
        self, stream_id: str, target_ts: float, tolerance_ms: float = 50.0
    ) -> dict | None:
        """
        Find and remove the metadata entry closest to target_ts.

        Returns None if no entry is within tolerance.
        """
        tolerance_sec = tolerance_ms / 1000.0

        async with self._lock:
            buffer = self.buffers.get(stream_id, [])
            if not buffer:
                return None

            # Find closest match
            best_idx = -1
            best_diff = float("inf")
            for i, (ts, _data) in enumerate(buffer):
                diff = abs(ts - target_ts)
                if diff < best_diff:
                    best_diff = diff
                    best_idx = i

            if best_idx >= 0 and best_diff <= tolerance_sec:
                _ts, metadata = buffer.pop(best_idx)
                return metadata

        return None

    @property
    def is_connected(self) -> bool:
        """Check if consumer is running."""
        return self._running and self._consumer is not None
