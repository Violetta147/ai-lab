import pytest
import asyncio
import numpy as np
from unittest.mock import MagicMock, AsyncMock
from app.infrastructure.kafka.consumer import KafkaConsumerService
from app.runtime.sync_engine import SyncEngine

@pytest.mark.asyncio
async def test_kafka_consumer_parses_new_c2_format():
    """Verify that the consumer correctly groups objects under ready buffer."""
    service = KafkaConsumerService()
    service._running = True
    
    # Message for frame 1
    msg1 = {
        "message_type": "c2_event",
        "stream_id": "cam_01",
        "timestamp": 1700000000.5,
        "frame_num": 100,
        "objects": [
            {"tracking_id": 1, "class_id": 0, "bbox": [10, 10, 50, 50]}
        ]
    }
    service._process_message(msg1)
    
    # Should not be ready yet (still building)
    assert service._ready.get("cam_01") is None
    
    # Message for frame 2 (triggers flush of frame 1)
    msg2 = {
        "message_type": "c2_event",
        "stream_id": "cam_01",
        "timestamp": 1700000001.0,
        "frame_num": 125,
        "objects": []
    }
    service._process_message(msg2)
    
    # Frame 1 should now be ready
    ready = service._ready.get("cam_01")
    assert ready is not None
    assert ready["timestamp"] == 1700000000.5
    assert len(ready["objects"]) == 1
    assert ready["objects"][0]["tracking_id"] == 1

@pytest.mark.asyncio
async def test_sync_engine_basic_sync():
    """Verify that SyncEngine retrieves closest frame and handles pop_latest."""
    mock_reader = MagicMock()
    mock_reader.get_closest_frame.return_value = (np.zeros((100, 100, 3)), 100.5)
    
    mock_metadata = AsyncMock()
    mock_metadata.pop_latest.return_value = {
        "timestamp": 100.5,
        "objects": [{"tracking_id": 42}]
    }
    
    engine = SyncEngine(mock_reader, mock_metadata)
    frame, objects = await engine.get_synced_frame("cam_01")
    
    assert frame is not None
    assert len(objects) == 1
    assert objects[0]["tracking_id"] == 42
    
    mock_reader.get_closest_frame.assert_called_once()
    mock_metadata.pop_latest.assert_called_once_with("cam_01")
