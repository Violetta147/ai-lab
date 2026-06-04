"""Tests for SyncEngine detection holding (anti-flicker)."""

import numpy as np
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.runtime.sync_engine import SyncEngine

@pytest.mark.asyncio
async def test_sync_engine_holds_detections():
    # Setup mocks
    video_reader = MagicMock()
    metadata_reader = MagicMock()
    metadata_reader.pop_latest = AsyncMock()
    
    engine = SyncEngine(video_reader, metadata_reader)
    
    # Mock frame at t=100.0
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    video_reader.get_closest_frame.return_value = (frame, 100.0)
    
    # 1. First frame: has metadata
    metadata_reader.pop_latest.side_effect = [
        {"objects": [{"class_id": 0, "tracking_id": 1}]}, # Match
        None # End loop
    ]
    
    f1, d1 = await engine.get_synced_frame("stream1")
    assert len(d1) == 1
    assert d1[0]["tracking_id"] == 1
    
    # 2. Second frame: NO metadata (e.g. interval skip) at t=100.1
    video_reader.get_closest_frame.return_value = (frame, 100.1)
    metadata_reader.pop_latest.side_effect = [None]
    
    f2, d2 = await engine.get_synced_frame("stream1")
    # Should HOLD the detections from frame 1
    assert len(d2) == 1
    assert d2[0]["tracking_id"] == 1
