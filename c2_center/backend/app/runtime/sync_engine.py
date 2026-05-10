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
        self._initial_lock_range_ms = 2000.0  # Search up to 2s to find initial lock

    async def get_synced_frame(
        self, stream_id: str
    ) -> tuple[np.ndarray | None, list[dict]]:
        """
        Get a synchronized (frame, detections) pair for a stream.

        Implements anti-flicker and dynamic drift correction.
        """
        result = self.video_reader.get_frame(stream_id, timeout=0.1)
        if result is None:
            return None, []

        frame, frame_ts = result
        
        # Apply drift correction to the search target
        has_offset = stream_id in self._offsets
        offset = self._offsets.get(stream_id, 0.0)
        search_ts = frame_ts + offset
        
        # If no offset known yet, use a wider tolerance for initial lock
        current_tolerance = settings.SYNC_TOLERANCE_MS if has_offset else self._initial_lock_range_ms
        
        all_objects = []
        new_metadata_found = False

        # Aggregate multiple metadata entries within tolerance
        while True:
            metadata = await self.kafka_consumer.pop_nearest(
                stream_id=stream_id,
                target_ts=search_ts,
                tolerance_ms=current_tolerance,
            )
            if not metadata:
                break
            
            new_metadata_found = True
            all_objects.extend(metadata.get("objects", []))
            
            # Update drift estimate using the first metadata entry's timestamp
            if len(all_objects) == len(metadata.get("objects", [])):
                meta_ts = float(metadata.get("timestamp", search_ts))
                current_diff = meta_ts - frame_ts
                self._offsets[stream_id] = (1 - self._alpha) * offset + self._alpha * current_diff

            if len(all_objects) > 1000:
                break

        if new_metadata_found:
            self._last_detections[stream_id] = (frame_ts, all_objects)
            return frame, all_objects
        
        last_entry = self._last_detections.get(stream_id)
        if last_entry:
            last_ts, last_objs = last_entry
            age = frame_ts - last_ts
            if 0 <= age <= self._hold_ttl_sec:
                held_objs = [dict(obj, _is_held=True) for obj in last_objs]
                return frame, held_objs

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
