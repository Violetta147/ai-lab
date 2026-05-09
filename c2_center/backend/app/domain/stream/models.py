"""Stream domain types."""

from dataclasses import dataclass
from typing import NewType

# Stable ID for a video stream (e.g. "cam_8554" or DB stream_id).
StreamId = NewType("StreamId", str)


@dataclass(frozen=True)
class StreamStatus:
    """Connectivity status of a single stream."""

    stream_id: str
    video_connected: bool
    kafka_connected: bool

    def to_dict(self) -> dict:
        return {
            "stream_id": self.stream_id,
            "video_connected": self.video_connected,
            "kafka_connected": self.kafka_connected,
        }
