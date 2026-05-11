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
        # Anti-flicker: store last valid detections per stream
        self._last_detections: dict[str, tuple[float, list[dict]]] = {}
        self._hold_ttl_sec = 0.5 
        
        # Dynamic Drift Correction: {stream_id: average_offset_sec}
        self._offsets: dict[str, float] = {}
        self._alpha = 0.05  # Smoothing factor for drift

    async def get_synced_frame(
        self, stream_id: str
    ) -> tuple[np.ndarray | None, list[dict]]:
        """
        Optimized 'Latest-First' sync strategy.
        Prioritizes smoothness by taking the most recent metadata.
        """
        result = self.video_reader.get_frame(stream_id, timeout=0.1)
        if result is None:
            return None, []

        frame, frame_ts = result
        
        # Apply drift correction
        offset = self._offsets.get(stream_id, 0.0)
        search_ts = frame_ts + offset
        
        # NEW: Optimized one-pass pop. 
        # Instead of while-looping thousands of items, we grab the closest 
        # single packet (which contains an objects array in our Type 257 payload).
        metadata = await self.kafka_consumer.pop_nearest(
            stream_id=stream_id,
            target_ts=search_ts,
            tolerance_ms=settings.SYNC_TOLERANCE_MS,
        )

        if metadata:
            all_objects = metadata.get("objects", [])
            # Update drift estimate
            meta_ts = float(metadata.get("timestamp", search_ts))
            current_diff = meta_ts - frame_ts
            self._offsets[stream_id] = (1 - self._alpha) * offset + self._alpha * current_diff
            
            self._last_detections[stream_id] = (frame_ts, all_objects)
            return frame, all_objects
        
        # Anti-flicker hold
        last_entry = self._last_detections.get(stream_id)
        if last_entry:
            last_ts, last_objs = last_entry
            if 0 <= (frame_ts - last_ts) <= self._hold_ttl_sec:
                return frame, [dict(obj, _is_held=True) for obj in last_objs]

        return frame, []

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
