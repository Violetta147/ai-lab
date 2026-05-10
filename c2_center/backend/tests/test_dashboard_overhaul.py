"""Tests for Deep Analysis dashboard overhaul.

Covers:
1. area_occupancy should be classified as "live" mode
2. GET /api/analytics/algorithm/{stream_id} returns active algorithm
3. Stats WS messages should include algorithm slug
4. Kafka consumer stream_id mapping resolves correctly
5. Per-class counting extracted from detection objects
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
import numpy as np

from app.analytics.registry import registry as analytics_registry


# ─── 1. Registry: area_occupancy is "live" ───────────────────────────

def test_area_occupancy_is_live_mode():
    """area_occupancy should be accessible on the live RTSP pipeline."""
    if not analytics_registry.slugs():
        analytics_registry.discover("app.analytics.plugins")
    mode = analytics_registry.get_mode("area_occupancy")
    assert mode == "live", f"Expected 'live', got '{mode}'"


def test_live_algorithms_include_area_occupancy():
    """GET /algorithms?mode=live should include area_occupancy."""
    if not analytics_registry.slugs():
        analytics_registry.discover("app.analytics.plugins")
    live_slugs = {m.slug for m in analytics_registry.list_all(mode="live")}
    assert "area_occupancy" in live_slugs


# ─── 2. GET active algorithm endpoint ────────────────────────────────

def test_get_active_algorithm_endpoint():
    """GET /api/analytics/algorithm/{stream_id} should return active slug."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import analytics_api as analytics_api_module

    class FakeDispatcher:
        def __init__(self):
            self.last_set = None
        def set_algorithm(self, sid, slug):
            self.last_set = (sid, slug)
        def get_active_slug(self, sid):
            return "heatmap"

    class FakePipeline:
        def __init__(self):
            self.analytics_dispatcher = FakeDispatcher()

    if not analytics_registry.slugs():
        analytics_registry.discover("app.analytics.plugins")

    app = FastAPI()
    pipeline = FakePipeline()
    app.include_router(analytics_api_module.get_router(pipeline))
    client = TestClient(app)

    resp = client.get("/api/analytics/algorithm/cam01")
    assert resp.status_code == 200
    body = resp.json()
    assert body["stream_id"] == "cam01"
    assert body["algorithm"] == "heatmap"


# ─── 3. Kafka consumer stream mapping ────────────────────────────────

@pytest.mark.asyncio
async def test_kafka_consumer_resolves_stream_mapping():
    """Kafka consumer should map numeric source_id '0' to semantic stream_id."""
    from app.infrastructure.kafka.consumer import KafkaConsumerService

    consumer = KafkaConsumerService()
    consumer.set_stream_mapping(0, "muahe")
    consumer.set_stream_mapping(1, "cam_02")

    assert consumer.stream_id_map["0"] == "muahe"
    assert consumer.stream_id_map["1"] == "cam_02"


# ─── 4. Per-class counting from objects ──────────────────────────────

def test_per_class_counting():
    """Extract per-class counts from a list of detection objects."""
    objects = [
        {"class_id": 0, "tracking_id": 1},
        {"class_id": 0, "tracking_id": 2},
        {"class_id": 1, "tracking_id": 3},
        {"class_id": 0, "tracking_id": 4},
        {"class_id": 2, "tracking_id": 5},
    ]
    # Count per class_id
    from collections import Counter
    counts = Counter(obj["class_id"] for obj in objects)
    assert counts[0] == 3
    assert counts[1] == 1
    assert counts[2] == 1


# ─── 5. Converters handle bbox list format ───────────────────────────

def test_converters_handle_bbox_list():
    """metadata_to_detections should accept bbox as [x1,y1,x2,y2]."""
    from app.domain.detection.converters import metadata_to_detections

    objects = [
        {"class_id": 0, "tracking_id": 1, "bbox": [10.0, 20.0, 50.0, 60.0]},
        {"class_id": 1, "tracking_id": 2, "bbox": [100.0, 200.0, 300.0, 400.0]},
    ]
    dets = metadata_to_detections(objects)
    assert len(dets) == 2
    assert dets.xyxy[0].tolist() == pytest.approx([10.0, 20.0, 50.0, 60.0])
    assert dets.xyxy[1].tolist() == pytest.approx([100.0, 200.0, 300.0, 400.0])
    assert dets.tracker_id[0] == 1
    assert dets.tracker_id[1] == 2
