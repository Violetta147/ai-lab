"""Tests for MqttDetectionConsumerService — no real MQTT broker required."""

import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_msg(payload: dict, topic: str = "traffic/tracked"):
    msg = SimpleNamespace()
    msg.payload = json.dumps(payload).encode("utf-8")
    msg.topic = topic
    return msg


def make_consumer():
    """Instantiate without triggering paho I/O."""
    with patch("app.infrastructure.mqtt.consumer.mqtt_client"):
        from app.infrastructure.mqtt.consumer import MqttDetectionConsumerService

        svc = MqttDetectionConsumerService.__new__(MqttDetectionConsumerService)
        # Manually initialise internal state (bypass __init__ paho calls)
        import threading

        svc._ready = {}
        svc._lock = threading.Lock()
        svc._running = False
        svc._connected = False
        svc._thread = None
        return svc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_normalize_payload_basic():
    svc = make_consumer()
    msg = make_msg(
        {
            "stream_id": "CAM_01",
            "camera_id": "CAM_01",
            "timestamp": 1700000000.5,
            "objects": [
                {
                    "tracking_id": 1,
                    "class_id": 0,
                    "class_name": "car",
                    "confidence": 0.92,
                    "bbox": [100.0, 200.0, 250.0, 450.0],
                }
            ],
        }
    )
    svc._on_message(None, None, msg)

    import asyncio

    result = asyncio.get_event_loop().run_until_complete(svc.pop_latest("CAM_01"))
    assert result is not None
    assert result["stream_id"] == "CAM_01"
    assert result["timestamp"] == pytest.approx(1700000000.5)
    assert len(result["objects"]) == 1
    assert result["objects"][0]["tracking_id"] == 1


def test_camera_id_fallback_when_no_stream_id():
    svc = make_consumer()
    msg = make_msg({"camera_id": "CAM_02", "timestamp": 1700000001.0, "objects": []})
    svc._on_message(None, None, msg)

    import asyncio

    result = asyncio.get_event_loop().run_until_complete(svc.pop_latest("CAM_02"))
    assert result is not None
    assert result["stream_id"] == "CAM_02"


def test_invalid_json_skipped():
    svc = make_consumer()
    msg = SimpleNamespace()
    msg.payload = b"not valid json {"
    msg.topic = "traffic/tracked"
    svc._on_message(None, None, msg)  # must not raise

    import asyncio

    result = asyncio.get_event_loop().run_until_complete(svc.pop_latest("unknown"))
    assert result is None


def test_set_stream_mapping_is_noop():
    svc = make_consumer()
    svc.set_stream_mapping(0, "cam_01")  # should not raise
    svc.set_stream_mapping(5, "cam_99")


def test_is_connected_false_before_start():
    svc = make_consumer()
    assert svc.is_connected is False


def test_peek_semantics_returns_same_dict_until_overwritten():
    svc = make_consumer()
    msg = make_msg({"stream_id": "S1", "timestamp": 1.0, "objects": []})
    svc._on_message(None, None, msg)

    import asyncio

    loop = asyncio.get_event_loop()
    r1 = loop.run_until_complete(svc.pop_latest("S1"))
    r2 = loop.run_until_complete(svc.pop_latest("S1"))
    assert r1 is r2  # same object — peek, not pop
