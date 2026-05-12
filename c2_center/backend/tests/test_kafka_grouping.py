"""
Diagnostic tests for KafkaConsumerService frame grouping and SyncEngine pairing.

These tests simulate the EXACT real-world data flow:
  - Jetson sends 1 Kafka msg per object per frame (25 FPS, ~20 objects/frame)
  - Backend pipeline runs at 15 FPS consuming pop_latest()
  - Tests verify: grouping correctness, completeness, timing, no ghost data
"""

import threading
import time

import numpy as np
import pytest

from app.infrastructure.kafka.consumer import KafkaConsumerService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_object(tracking_id: int, class_id: int = 0) -> dict:
    """Create a single detection object payload."""
    return {
        "class_id": class_id,
        "tracking_id": tracking_id,
        "bbox": [100.0 + tracking_id, 200.0, 150.0 + tracking_id, 250.0],
    }


def make_frame_messages(stream_id: str, timestamp: float, num_objects: int) -> list[dict]:
    """
    Simulate DeepStream output: one Kafka message per object, all sharing
    the same timestamp (same frame).
    """
    messages = []
    for i in range(num_objects):
        messages.append({
            "message_type": "c2_event",
            "stream_id": stream_id,
            "timestamp": timestamp,
            "frame_num": int(timestamp * 25),
            "objects": [make_object(tracking_id=i)],
        })
    return messages


# ---------------------------------------------------------------------------
# TEST 1: Basic grouping — objects from same frame merge correctly
# ---------------------------------------------------------------------------

class TestFrameGrouping:
    """Verify that per-object Kafka messages are grouped into complete frames."""

    def test_single_object_frame(self):
        """A frame with 1 object should become ready after next frame arrives."""
        svc = KafkaConsumerService()
        svc._running = True

        # Frame 1: 1 object
        svc._process_message({
            "stream_id": "cam1", "timestamp": 100.0,
            "objects": [make_object(0)],
        })

        # Frame 1 is still _building, not _ready yet
        assert svc._ready.get("cam1") is None

        # Frame 2 arrives → Frame 1 moves to _ready
        svc._process_message({
            "stream_id": "cam1", "timestamp": 100.04,
            "objects": [make_object(10)],
        })

        ready = svc._ready.get("cam1")
        assert ready is not None
        assert len(ready["objects"]) == 1
        assert ready["objects"][0]["tracking_id"] == 0

    def test_multi_object_grouping(self):
        """5 objects from same frame (same timestamp) should be grouped into 1 frame."""
        svc = KafkaConsumerService()
        svc._running = True

        msgs = make_frame_messages("cam1", timestamp=200.0, num_objects=5)
        for msg in msgs:
            svc._process_message(msg)

        # Still building — no second frame yet
        assert svc._ready.get("cam1") is None

        # Trigger flush with next frame
        svc._process_message({
            "stream_id": "cam1", "timestamp": 200.04,
            "objects": [make_object(99)],
        })

        ready = svc._ready.get("cam1")
        assert ready is not None
        assert len(ready["objects"]) == 5, f"Expected 5, got {len(ready['objects'])}"

        tracking_ids = {o["tracking_id"] for o in ready["objects"]}
        assert tracking_ids == {0, 1, 2, 3, 4}

    def test_20_objects_grouping(self):
        """Real-world scenario: 20 vehicles detected in one frame."""
        svc = KafkaConsumerService()
        svc._running = True

        msgs = make_frame_messages("cam1", timestamp=300.0, num_objects=20)
        for msg in msgs:
            svc._process_message(msg)

        # Flush
        svc._process_message({
            "stream_id": "cam1", "timestamp": 300.04,
            "objects": [make_object(99)],
        })

        ready = svc._ready.get("cam1")
        assert ready is not None
        assert len(ready["objects"]) == 20

    def test_successive_frames_overwrite_ready(self):
        """Each new complete frame should overwrite _ready (single-slot)."""
        svc = KafkaConsumerService()
        svc._running = True

        # Frame A: 3 objects
        for msg in make_frame_messages("cam1", 400.0, 3):
            svc._process_message(msg)
        # Frame B: 2 objects (flushes A to ready)
        for msg in make_frame_messages("cam1", 400.04, 2):
            svc._process_message(msg)
        # Frame C: 1 object (flushes B to ready, overwrites A)
        svc._process_message({
            "stream_id": "cam1", "timestamp": 400.08,
            "objects": [make_object(99)],
        })

        ready = svc._ready.get("cam1")
        assert ready is not None
        # Should be Frame B (2 objects), not Frame A (3 objects)
        assert len(ready["objects"]) == 2


# ---------------------------------------------------------------------------
# TEST 2: pop_latest semantics
# ---------------------------------------------------------------------------

class TestPopLatest:
    """Verify pop_latest returns complete frames and clears the slot."""

    @pytest.mark.asyncio
    async def test_pop_latest_returns_none_when_empty(self):
        svc = KafkaConsumerService()
        result = await svc.pop_latest("cam1")
        assert result is None

    @pytest.mark.asyncio
    async def test_pop_latest_returns_none_while_building(self):
        """Should NOT return partially-built frames."""
        svc = KafkaConsumerService()
        svc._running = True

        # Send 3 objects for the SAME frame — still building
        for msg in make_frame_messages("cam1", 500.0, 3):
            svc._process_message(msg)

        result = await svc.pop_latest("cam1")
        assert result is None, "pop_latest should not return a frame that's still building"

    @pytest.mark.asyncio
    async def test_pop_latest_returns_complete_frame(self):
        """Should return a complete frame once the next frame arrives."""
        svc = KafkaConsumerService()
        svc._running = True

        # Frame 1: 5 objects
        for msg in make_frame_messages("cam1", 600.0, 5):
            svc._process_message(msg)
        # Frame 2: triggers flush
        svc._process_message({
            "stream_id": "cam1", "timestamp": 600.04,
            "objects": [make_object(99)],
        })

        result = await svc.pop_latest("cam1")
        assert result is not None
        assert len(result["objects"]) == 5

    @pytest.mark.asyncio
    async def test_pop_latest_returns_same_data_until_overwritten(self):
        """Peek semantics: same data returned until consumer thread overwrites."""
        svc = KafkaConsumerService()
        svc._running = True

        for msg in make_frame_messages("cam1", 700.0, 3):
            svc._process_message(msg)
        svc._process_message({
            "stream_id": "cam1", "timestamp": 700.04,
            "objects": [make_object(99)],
        })

        first = await svc.pop_latest("cam1")
        assert first is not None

        second = await svc.pop_latest("cam1")
        assert second is not None, "peek semantics: should return same data"
        assert second is first, "should be the exact same dict object"

    @pytest.mark.asyncio
    async def test_no_ghost_objects_across_frames(self):
        """Objects from frame N must NOT leak into frame N+1."""
        svc = KafkaConsumerService()
        svc._running = True

        # Frame 1: objects with tracking_id 0-4
        for msg in make_frame_messages("cam1", 800.0, 5):
            svc._process_message(msg)
        # Frame 2: objects with tracking_id 100-102
        for i in range(3):
            svc._process_message({
                "stream_id": "cam1", "timestamp": 800.04,
                "objects": [make_object(100 + i)],
            })
        # Frame 3: flush frame 2
        svc._process_message({
            "stream_id": "cam1", "timestamp": 800.08,
            "objects": [make_object(200)],
        })

        # Pop should give us frame 2 (the latest complete)
        result = await svc.pop_latest("cam1")
        assert result is not None
        tracking_ids = {o["tracking_id"] for o in result["objects"]}

        # Must contain ONLY frame 2 objects, NO frame 1 leakage
        assert tracking_ids == {100, 101, 102}, (
            f"Ghost objects detected! Got {tracking_ids}, expected {{100, 101, 102}}"
        )


# ---------------------------------------------------------------------------
# TEST 3: Multi-stream isolation
# ---------------------------------------------------------------------------

class TestMultiStream:
    """Verify streams don't contaminate each other."""

    @pytest.mark.asyncio
    async def test_separate_streams_independent(self):
        svc = KafkaConsumerService()
        svc._running = True

        # cam1: 3 objects
        for msg in make_frame_messages("cam1", 900.0, 3):
            svc._process_message(msg)
        svc._process_message({
            "stream_id": "cam1", "timestamp": 900.04,
            "objects": [make_object(99)],
        })

        # cam2: 7 objects
        for msg in make_frame_messages("cam2", 900.0, 7):
            svc._process_message(msg)
        svc._process_message({
            "stream_id": "cam2", "timestamp": 900.04,
            "objects": [make_object(99)],
        })

        r1 = await svc.pop_latest("cam1")
        r2 = await svc.pop_latest("cam2")

        assert r1 is not None and len(r1["objects"]) == 3
        assert r2 is not None and len(r2["objects"]) == 7


# ---------------------------------------------------------------------------
# TEST 4: Stream ID mapping
# ---------------------------------------------------------------------------

class TestStreamMapping:
    """Verify numeric source_id → semantic stream_id mapping."""

    @pytest.mark.asyncio
    async def test_source_id_maps_to_stream_id(self):
        svc = KafkaConsumerService()
        svc._running = True
        svc.set_stream_mapping(0, "muahe")

        # Message uses numeric stream_id "0"
        svc._process_message({
            "stream_id": "0", "timestamp": 1000.0,
            "objects": [make_object(1)],
        })
        svc._process_message({
            "stream_id": "0", "timestamp": 1000.04,
            "objects": [make_object(2)],
        })

        result = await svc.pop_latest("muahe")
        assert result is not None
        assert result["objects"][0]["tracking_id"] == 1


# ---------------------------------------------------------------------------
# TEST 5: Throughput simulation — 25 FPS producer, 15 FPS consumer
# ---------------------------------------------------------------------------

class TestThroughputSimulation:
    """Simulate real-world timing: Jetson at 25fps, backend at 15fps."""

    @pytest.mark.asyncio
    async def test_25fps_producer_15fps_consumer(self):
        """
        Simulate 2 seconds of operation:
        - Producer: 25 fps, 15 objects/frame = 50 frames, 750 messages
        - Consumer: 15 fps = 30 pop_latest calls
        
        EVERY pop_latest must return a COMPLETE frame (all 15 objects).
        """
        svc = KafkaConsumerService()
        svc._running = True

        producer_fps = 25
        consumer_fps = 15
        objects_per_frame = 15
        duration_sec = 2.0

        # --- Producer: send all messages ---
        total_frames = int(producer_fps * duration_sec)
        for frame_idx in range(total_frames):
            ts = 1000.0 + frame_idx / producer_fps
            for msg in make_frame_messages("cam1", ts, objects_per_frame):
                svc._process_message(msg)

        # --- Consumer: pop at 15fps rate ---
        results = []
        total_pops = int(consumer_fps * duration_sec)
        for _ in range(total_pops):
            result = await svc.pop_latest("cam1")
            if result is not None:
                results.append(result)

        # Assertions
        assert len(results) > 0, "Consumer got zero frames!"

        # CRITICAL: every returned frame must have ALL 15 objects
        incomplete_frames = []
        for i, r in enumerate(results):
            n_objs = len(r.get("objects", []))
            if n_objs != objects_per_frame:
                incomplete_frames.append((i, n_objs))

        assert len(incomplete_frames) == 0, (
            f"Found {len(incomplete_frames)} incomplete frames! "
            f"Expected {objects_per_frame} objects each. "
            f"Failures: {incomplete_frames[:5]}"
        )

    @pytest.mark.asyncio
    async def test_threaded_producer_consumer_no_corruption(self):
        """
        True concurrency test: producer thread vs consumer on asyncio.
        Verifies no data corruption under real threading conditions.
        """
        svc = KafkaConsumerService()
        svc._running = True

        objects_per_frame = 20
        num_frames = 100
        errors = []

        def producer():
            """Simulate Jetson sending messages at ~25fps."""
            for frame_idx in range(num_frames):
                ts = 2000.0 + frame_idx * 0.04  # 25fps = 40ms per frame
                for msg in make_frame_messages("cam1", ts, objects_per_frame):
                    svc._process_message(msg)
                time.sleep(0.001)  # Simulate tiny network delay between frames

        # Start producer thread
        t = threading.Thread(target=producer, daemon=True)
        t.start()

        # Consumer: poll at ~15fps for 5 seconds max
        results = []
        deadline = time.time() + 5.0
        while time.time() < deadline:
            result = await svc.pop_latest("cam1")
            if result is not None:
                n_objs = len(result.get("objects", []))
                results.append(n_objs)
                if n_objs != objects_per_frame:
                    errors.append(f"Frame got {n_objs} objects, expected {objects_per_frame}")
            await __import__("asyncio").sleep(0.066)  # ~15fps

            # Stop when producer is done and we've drained
            if not t.is_alive() and result is None:
                break

        t.join(timeout=5.0)

        assert len(results) > 0, "Consumer received zero frames!"
        assert len(errors) == 0, (
            f"Data corruption detected! {len(errors)} bad frames out of {len(results)}:\n"
            + "\n".join(errors[:10])
        )
        print(f"\n  [OK] Received {len(results)} complete frames, all with {objects_per_frame} objects")


# ---------------------------------------------------------------------------
# TEST 6: SyncEngine integration
# ---------------------------------------------------------------------------

class TestSyncEngineIntegration:
    """Test SyncEngine with the real KafkaConsumerService (no mocks)."""

    @pytest.mark.asyncio
    async def test_synced_frame_returns_all_objects(self):
        """SyncEngine should return ALL objects from the latest complete Kafka frame."""
        from unittest.mock import MagicMock
        from app.runtime.sync_engine import SyncEngine

        svc = KafkaConsumerService()
        svc._running = True

        # Prepare 2 frames
        for msg in make_frame_messages("cam1", 3000.0, 10):
            svc._process_message(msg)
        for msg in make_frame_messages("cam1", 3000.04, 8):
            svc._process_message(msg)
        # Flush frame 2
        svc._process_message({
            "stream_id": "cam1", "timestamp": 3000.08,
            "objects": [make_object(99)],
        })

        # Mock video reader
        mock_reader = MagicMock()
        mock_reader.get_frame.return_value = (np.zeros((480, 640, 3), dtype=np.uint8), time.time())

        engine = SyncEngine(mock_reader, svc)
        frame, objects = await engine.get_synced_frame("cam1")

        assert frame is not None
        # Should get frame 2 (8 objects) since frame 1 was overwritten
        assert len(objects) == 8, f"Expected 8 objects, got {len(objects)}"

    @pytest.mark.asyncio
    async def test_synced_frame_returns_empty_when_no_kafka(self):
        """When Kafka has no data, SyncEngine should return empty (no ghost boxes)."""
        from unittest.mock import MagicMock
        from app.runtime.sync_engine import SyncEngine

        svc = KafkaConsumerService()
        svc._running = True

        mock_reader = MagicMock()
        mock_reader.get_frame.return_value = (np.zeros((480, 640, 3), dtype=np.uint8), time.time())

        engine = SyncEngine(mock_reader, svc)
        frame, objects = await engine.get_synced_frame("cam1")

        assert frame is not None
        assert objects == [], f"Expected empty, got {len(objects)} ghost objects!"
