import pytest
import time
from unittest.mock import AsyncMock, MagicMock

from app.runtime.sync_engine import SyncEngine


class MockVideoReader:
    def get_closest_frame(self, stream_id, timestamp, max_latency=1.0):
        if stream_id == "cam1":
            return ("mock_frame", timestamp)
        return None
        
    def get_stream_ids(self):
        return ["cam1"]
        
    def is_stream_connected(self, stream_id):
        return stream_id == "cam1"


class MockMetadataReader:
    def __init__(self):
        self.is_connected = True
        
    async def pop_latest(self, stream_id):
        if stream_id == "cam1":
            return {"camera_id": "cam1", "timestamp": time.time(), "detections": []}
        return None


@pytest.mark.asyncio
async def test_sync_engine_decoupled():
    video_reader = MockVideoReader()
    metadata_reader = MockMetadataReader()
    
    engine = SyncEngine(video_reader=video_reader, metadata_reader=metadata_reader)
    
    # 1. Test Sync function
    result = await engine.get_synced_frame("cam1")
    assert result is not None
    frame, detections = result
    assert frame == "mock_frame"
    assert detections == []
    
    # 2. Test Stream Status
    status = engine.get_stream_status("cam1")
    assert status["video_connected"] is True
    assert status["metadata_connected"] is True
