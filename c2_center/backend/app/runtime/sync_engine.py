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
        # TTL=0: disabled — Latest-to-Latest strategy means stale holds = ghost boxes
        self._hold_ttl_sec = 0.0
        
        # Dynamic Drift Correction for Diagnostics: {stream_id: average_offset_sec}
        self._offsets: dict[str, float] = {}
        self._alpha = 0.05  # Smoothing factor for drift

    async def get_synced_frame(
        self, stream_id: str
    ) -> tuple[np.ndarray | None, list[dict]]:
        """
        Optimized 'Latest-to-Latest' sync strategy.
        Since both Jetson (latency=0) and Web Server (nobuffer) run strictly live, 
        we can simply pair the absolute newest frame with the absolute newest Kafka metadata.
        This completely eliminates timestamp drift/EMA brittleness.
        """
        result = self.video_reader.get_frame(stream_id, timeout=0.1)
        if result is None:
            return None, []

        frame, frame_ts = result
        
        # Simply grab the absolute latest Kafka metadata
        metadata = await self.kafka_consumer.pop_latest(stream_id)

        if metadata:
            all_objects = metadata.get("objects", [])
            kafka_ts = metadata.get("timestamp", 0)
            
            # --- DIAGNOSTIC: measure video-metadata time delta ---
            if not hasattr(self, '_diag_sync_count'):
                self._diag_sync_count = 0
                self._last_kafka_ts: dict[str, float] = {}
                self._reuse_count: dict[str, int] = {}
            
            self._diag_sync_count += 1
            prev_kafka_ts = self._last_kafka_ts.get(stream_id, 0)
            
            if kafka_ts == prev_kafka_ts:
                self._reuse_count[stream_id] = self._reuse_count.get(stream_id, 0) + 1
            else:
                # New metadata frame arrived
                raw_delta = frame_ts - kafka_ts if kafka_ts > 0 else 0
                
                # --- AUTO CLOCK-DRIFT COMPENSATOR (For Diagnostics Only) ---
                # If clocks are out of sync by > 10 seconds (no NTP), we establish a baseline offset
                if stream_id not in self._offsets:
                    self._offsets[stream_id] = raw_delta if abs(raw_delta) > 10.0 else 0.0
                else:
                    # Slowly adapt to long-term drift
                    if abs(raw_delta) > 10.0:
                        self._offsets[stream_id] = (1 - self._alpha) * self._offsets[stream_id] + self._alpha * raw_delta
                
                delta = raw_delta - self._offsets[stream_id]
                
                if self._diag_sync_count <= 100 or self._diag_sync_count % 100 == 0:
                    reuses = self._reuse_count.get(stream_id, 0)
                    logger.warning(
                        "[SYNC-DIAG][%s] video_ts=%.3f kafka_ts=%.3f DELTA=%.0fms | "
                        "prev_metadata_reused=%d_times | objects=%d",
                        stream_id, frame_ts, kafka_ts, delta * 1000,
                        reuses, len(all_objects),
                    )
                
                # Hidden Error Detection: Metadata is way too old
                if delta > 1.0:
                    logger.error(
                        "[SYNC-ERROR][%s] STALE METADATA! Age is %.1fs. Bounding boxes will 'ghost'!",
                        stream_id, delta
                    )
                
                self._reuse_count[stream_id] = 0
                self._last_kafka_ts[stream_id] = kafka_ts
            # --- END DIAGNOSTIC ---
            
            self._last_detections[stream_id] = (frame_ts, all_objects)
            return frame, all_objects
        
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
