"""
C2 Center Backend — Sync Engine

Pairs video frames with Kafka metadata by matching timestamps
within a configurable tolerance window (default ±50ms).
"""

import logging

import numpy as np

from config import settings
from services.kafka_consumer import KafkaConsumerService
from services.video_reader import VideoReaderService

logger = logging.getLogger(__name__)


class SyncEngine:
    """
    Synchronizes video frames from VideoReaderService
    with JSON metadata from KafkaConsumerService.

    For each stream, takes the latest video frame and finds the
    Kafka metadata message whose timestamp is closest (within tolerance).
    """

    def __init__(
        self,
        video_reader: VideoReaderService,
        kafka_consumer: KafkaConsumerService,
    ) -> None:
        self.video_reader = video_reader
        self.kafka_consumer = kafka_consumer

    async def get_synced_frame(
        self, stream_id: str
    ) -> tuple[np.ndarray | None, list[dict]]:
        """
        Get a synchronized (frame, detections) pair for a stream.

        Returns:
            - (frame, objects_list) if frame available
            - (None, []) if no frame available
        """
        # Get latest video frame (blocking with short timeout)
        result = self.video_reader.get_frame(stream_id, timeout=0.1)
        if result is None:
            return None, []

        frame, frame_ts = result

        # Try to find matching metadata
        metadata = await self.kafka_consumer.pop_nearest(
            stream_id=stream_id,
            target_ts=frame_ts,
            tolerance_ms=settings.SYNC_TOLERANCE_MS,
        )

        if metadata is not None:
            objects_list = metadata.get("objects", [])
        else:
            objects_list = []

        return frame, objects_list

    def get_stream_ids(self) -> list[str]:
        """Return all configured stream IDs."""
        return self.video_reader.get_stream_ids()

    def get_stream_status(self, stream_id: str) -> dict:
        """Get connection status for a stream."""
        return {
            "stream_id": stream_id,
            "video_connected": self.video_reader.is_stream_connected(stream_id),
            "kafka_connected": self.kafka_consumer.is_connected,
        }
