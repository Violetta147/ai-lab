import pytest
import asyncio
from unittest.mock import MagicMock
import numpy as np
from app.infrastructure.kafka.consumer import KafkaConsumerService
from app.runtime.sync_engine import SyncEngine

@pytest.mark.asyncio
async def test_kafka_consumer_parses_new_c2_format():
    """Verify that the consumer correctly parses the new stream_id and objects format."""
    service = KafkaConsumerService()
    # Mock data as planned in c2_payload.cpp update
    mock_msg = MagicMock()
    mock_msg.value = {
        "message_type": "c2_event",
        "stream_id": "cam_01",
        "timestamp": 1700000000.5,
        "frame_num": 100,
        "objects": [
            {"tracking_id": 1, "class_id": 0, "bbox": [10, 10, 50, 50]}
        ]
    }
    
    # We simulate the async iterator
    class MockIter:
        def __init__(self, msg): self.msg = msg; self.first = True
        def __aiter__(self): return self
        async def __anext__(self):
            if self.first: self.first = False; return self.msg
            raise StopAsyncIteration
            
    service._consumer = MockIter(mock_msg)
    service._running = True
    
    # Run loop for one iteration
    task = asyncio.create_task(service._consume_loop())
    await asyncio.sleep(0.1)
    service._running = False
    task.cancel()
    
    assert "cam_01" in service.buffers
    assert len(service.buffers["cam_01"]) == 1
    ts, data = service.buffers["cam_01"][0]
    assert ts == 1700000000.5
    assert data["objects"][0]["tracking_id"] == 1

@pytest.mark.asyncio
async def test_sync_engine_aggregates_multiple_objects():
    """Verify that SyncEngine collects ALL objects for a frame, not just one."""
    mock_reader = MagicMock()
    # Return a frame with timestamp 100.5
    mock_reader.get_frame.return_value = (np.zeros((100,100,3)), 100.5)
    
    # Helper to create awaitable responses
    async def mock_pop(*args, **kwargs):
        if not hasattr(mock_pop, "call_count"): mock_pop.call_count = 0
        responses = [
            {"objects": [{"tracking_id": 1}]},
            {"objects": [{"tracking_id": 2}]},
            None
        ]
        if mock_pop.call_count < len(responses):
            res = responses[mock_pop.call_count]
            mock_pop.call_count += 1
            return res
        return None

    mock_consumer = MagicMock()
    mock_consumer.pop_nearest.side_effect = mock_pop
    
    engine = SyncEngine(mock_reader, mock_consumer)
    frame, objects = await engine.get_synced_frame("cam_01")
    
    assert frame is not None
    # We expect BOTH objects to be aggregated. 
    # Current implementation only calls pop_nearest ONCE, so it will return 1.
    assert len(objects) == 2
    ids = [o["tracking_id"] for o in objects]
    assert 1 in ids
    assert 2 in ids
