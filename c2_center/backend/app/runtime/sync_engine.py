"""
Sync engine — pairs RTSP video frames with Kafka metadata by timestamp.

Holds references to the video reader (frame source) and Kafka consumer
(metadata source), and exposes one main coroutine `get_synced_frame()` that
returns the latest frame plus its best-matching detection list.
"""

import collections
import logging
import time

import numpy as np

from typing import Any, Protocol

logger = logging.getLogger(__name__)

class VideoReaderProtocol(Protocol):
    def get_closest_frame(self, stream_id: str, timestamp: float, max_latency: float = 1.0) -> tuple[Any, float] | None: ...
    def get_stream_ids(self) -> list[str]: ...
    def is_stream_connected(self, stream_id: str) -> bool: ...

class MetadataReaderProtocol(Protocol):
    async def pop_latest(self, stream_id: str) -> dict | None: ...
    @property
    def is_connected(self) -> bool: ...


class SyncEngine:
    """
    Synchronizes video frames from any VideoReaderProtocol with JSON metadata
    from any MetadataReaderProtocol.

    For each stream, takes the latest video frame and finds the
    Kafka metadata message whose timestamp is closest (within tolerance).
    """

    def __init__(
        self,
        video_reader: VideoReaderProtocol,
        metadata_reader: MetadataReaderProtocol,
    ) -> None:
        self.video_reader = video_reader
        self.metadata_reader = metadata_reader
        # Anti-flicker: store last valid detections per stream
        self._last_detections: dict[str, tuple[float, list[dict]]] = {}
        # TTL=0: disabled — Latest-to-Latest strategy means stale holds = ghost boxes
        self._hold_ttl_sec = 0.0
        
        # Sliding Window for Pure Clock Drift extraction
        # stream_id -> deque of raw (now - kafka_ts) differences
        self._offset_windows: dict[str, collections.deque] = {}

    async def get_synced_frame(
        self, stream_id: str
    ) -> tuple[np.ndarray | None, list[dict]]:
        """
        Frame Buffering Sync Strategy (Time-Travel Matching).
        Waits for metadata, calculates the true historical capture time of the frame,
        and retrieves the exact matching frame from the video reader's past buffer.
        """
        # 1. Grab the latest metadata FIRST
        metadata = await self.metadata_reader.pop_latest(stream_id)
        now = time.time()
        
        if not metadata:
            # If no new metadata, just get the absolute newest video frame to keep the stream alive
            result = self.video_reader.get_closest_frame(stream_id, now)
            if result is None:
                return None, []
            frame, frame_ts = result
            # Re-use last known bounding boxes
            _, last_objs = self._last_detections.get(stream_id, (0, []))
            return frame, last_objs

        # 2. We have new metadata!
        kafka_ts = metadata.get("timestamp", 0)
        all_objects = metadata.get("objects", [])
        
        raw_diff = now - kafka_ts if kafka_ts > 0 else 0
        
        # Add the raw difference to the sliding window (track last 100 frames)
        if stream_id not in self._offset_windows:
            self._offset_windows[stream_id] = collections.deque(maxlen=100)
        self._offset_windows[stream_id].append(raw_diff)
            
        # The Unchangeable Order Property (NTP-style Minimum Filter):
        # raw_diff = Clock_Drift + Network_Latency + Processing_Latency.
        # Since Processing/Network Latency is always > 0 and fluctuates (Jitter),
        # the MINIMUM raw_diff in our window represents the fastest possible packet 
        # (closest to pure Clock Drift with zero jitter).
        pure_clock_drift = min(self._offset_windows[stream_id])
        
        # Calculate the exact timestamp when this frame arrived at our backend
        # No magic numbers needed! The pure clock drift natively aligns the sequence.
        expected_capture_ts = kafka_ts + pure_clock_drift
        
        # 3. Time-Travel: Fetch the historical frame from the deque buffer
        result = self.video_reader.get_closest_frame(stream_id, expected_capture_ts, max_latency=1.0)
        
        if result is None:
            return None, []
            
        frame, frame_ts = result
        
        # --- DIAGNOSTIC LOGGING ---
        if not hasattr(self, '_diag_sync_count'):
            self._diag_sync_count = 0
            
        self._diag_sync_count += 1
        if self._diag_sync_count % 100 == 0:
            error_ms = abs(expected_capture_ts - frame_ts) * 1000
            logger.info(
                "[SYNC-DIAG][%s] Video fetched from %dms ago. Alignment error: %dms | Objects: %d",
                stream_id, (now - frame_ts) * 1000, error_ms, len(all_objects)
            )
            
        self._last_detections[stream_id] = (frame_ts, all_objects)
        return frame, all_objects

    def get_stream_ids(self) -> list[str]:
        """Return all configured stream IDs."""
        return self.video_reader.get_stream_ids()

    def get_stream_status(self, stream_id: str) -> dict:
        """Get connection status for a stream."""
        return {
            "stream_id": stream_id,
            "video_connected": self.video_reader.is_stream_connected(stream_id),
            "metadata_connected": getattr(self.metadata_reader, "is_connected", True),
        }
