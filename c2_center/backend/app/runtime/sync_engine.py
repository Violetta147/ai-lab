"""
Sync engine — pairs RTSP video frames with Kafka metadata by timestamp.

Holds references to the video reader (frame source) and Kafka consumer
(metadata source), and exposes one main coroutine `get_synced_frame()` that
returns the latest frame plus its best-matching detection list.
"""

import logging

import numpy as np

from app.core.config import settings
from app.infrastructure.kafka.consumer import KafkaConsumerService
from app.infrastructure.video.rtsp_reader import RtspVideoReader

logger = logging.getLogger(__name__)


class SyncEngine:
    """
    Synchronizes video frames from RtspVideoReader with JSON metadata
    from KafkaConsumerService.

    For each stream, takes the latest video frame and finds the
    Kafka metadata message whose timestamp is closest (within tolerance).
    """

    def __init__(
        self,
        video_reader: RtspVideoReader,
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
            - (frame, objects_list) if a frame is available
            - (None, []) if no frame is available
        """
        result = self.video_reader.get_frame(stream_id, timeout=0.1)
        if result is None:
            return None, []

        frame, frame_ts = result

        metadata = await self.kafka_consumer.pop_nearest(
            stream_id=stream_id,
            target_ts=frame_ts,
            tolerance_ms=settings.SYNC_TOLERANCE_MS,
        )

        objects_list = metadata.get("objects", []) if metadata else []
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
