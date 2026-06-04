import base64
import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from app.infrastructure.mqtt.mqtt_metadata_adapter import MqttMetadataAdapter
from app.infrastructure.mqtt.mqtt_video_adapter import MqttVideoAdapter


# Helper to generate mock MQTT messages
def make_mqtt_message(topic: str, payload: dict) -> SimpleNamespace:
    msg = SimpleNamespace()
    msg.topic = topic
    msg.payload = json.dumps(payload).encode("utf-8")
    return msg


# ============================================================================
# MqttMetadataAdapter Tests
# ============================================================================

def test_metadata_adapter_initial_state():
    adapter = MqttMetadataAdapter("localhost", 1883, "test/metadata")
    assert adapter.broker == "localhost"
    assert adapter.port == 1883
    assert adapter.topic == "test/metadata"
    assert adapter.is_connected is False
    assert len(adapter._queues) == 0


@patch("app.infrastructure.mqtt.mqtt_metadata_adapter.mqtt_client.Client")
def test_metadata_adapter_connect_disconnect(mock_client_cls):
    mock_client = mock_client_cls.return_value
    adapter = MqttMetadataAdapter("localhost", 1883, "test/metadata")
    
    adapter.connect()
    mock_client.connect_async.assert_called_once_with("localhost", 1883)
    mock_client.loop_start.assert_called_once()
    
    adapter.disconnect()
    mock_client.loop_stop.assert_called_once()
    mock_client.disconnect.assert_called_once()


def test_metadata_adapter_callbacks():
    adapter = MqttMetadataAdapter("localhost", 1883, "test/metadata")
    mock_client = MagicMock()
    
    # Test on_connect success (rc = 0)
    adapter._on_connect(mock_client, None, None, 0)
    assert adapter.is_connected is True
    mock_client.subscribe.assert_called_once_with("test/metadata")
    
    # Test on_disconnect
    adapter._on_disconnect(mock_client, None, 1)
    assert adapter.is_connected is False


@pytest.mark.asyncio
async def test_metadata_adapter_message_handling():
    adapter = MqttMetadataAdapter("localhost", 1883, "test/metadata")
    
    # Handle valid payload
    payload = {"camera_id": "CAM_01", "timestamp": 123456.78, "detections": [{"class_name": "car"}]}
    msg = make_mqtt_message("test/metadata", payload)
    
    adapter._on_message(None, None, msg)
    
    # Check popped item
    popped = await adapter.pop_latest("CAM_01")
    assert popped == payload
    
    # Queue should be empty now
    empty = await adapter.pop_latest("CAM_01")
    assert empty is None


@pytest.mark.asyncio
async def test_metadata_adapter_corrupt_payload():
    adapter = MqttMetadataAdapter("localhost", 1883, "test/metadata")
    
    # Send malformed JSON
    msg = SimpleNamespace()
    msg.topic = "test/metadata"
    msg.payload = b"invalid json"
    
    # Should not raise exception
    adapter._on_message(None, None, msg)
    
    # Queue should be empty
    popped = await adapter.pop_latest("CAM_01")
    assert popped is None


# ============================================================================
# MqttVideoAdapter Tests
# ============================================================================

def test_video_adapter_initial_state():
    adapter = MqttVideoAdapter("localhost", 1883, "test/video")
    assert adapter.broker == "localhost"
    assert adapter.port == 1883
    assert adapter.topic == "test/video"
    assert adapter.get_stream_ids() == []


@patch("app.infrastructure.mqtt.mqtt_video_adapter.mqtt_client.Client")
def test_video_adapter_connect_disconnect(mock_client_cls):
    mock_client = mock_client_cls.return_value
    adapter = MqttVideoAdapter("localhost", 1883, "test/video")
    
    adapter.connect()
    mock_client.connect_async.assert_called_once_with("localhost", 1883)
    mock_client.loop_start.assert_called_once()
    
    adapter.disconnect()
    mock_client.loop_stop.assert_called_once()
    mock_client.disconnect.assert_called_once()


def test_video_adapter_callbacks():
    adapter = MqttVideoAdapter("localhost", 1883, "test/video")
    mock_client = MagicMock()
    
    # Test on_connect success
    adapter._on_connect(mock_client, None, None, 0)
    assert adapter._connected is True
    mock_client.subscribe.assert_called_once_with("test/video")
    
    # Test stream connectivity property
    assert adapter.is_stream_connected("CAM_01") is False
    
    # Simulate a stream frame exists
    adapter._latest_frames["CAM_01"] = (np.zeros((100, 100, 3)), time.time())
    assert adapter.is_stream_connected("CAM_01") is True
    
    # Test on_disconnect
    adapter._on_disconnect(mock_client, None, 1)
    assert adapter.is_stream_connected("CAM_01") is False


def test_video_adapter_message_handling():
    adapter = MqttVideoAdapter("localhost", 1883, "test/video")
    
    # Create a small dummy image using numpy
    dummy_img = np.zeros((10, 10, 3), dtype=np.uint8)
    _, buffer = cv2.imencode('.jpg', dummy_img)
    b64_img = base64.b64encode(buffer).decode('utf-8')
    
    payload = {
        "camera_id": "CAM_02",
        "timestamp": 1700000000.0,
        "frame": b64_img
    }
    msg = make_mqtt_message("test/video", payload)
    
    adapter._on_message(None, None, msg)
    
    assert "CAM_02" in adapter.get_stream_ids()
    
    # Check retrieval closest frame
    retrieved = adapter.get_closest_frame("CAM_02", 1700000000.2, max_latency=0.5)
    assert retrieved is not None
    frame, ts = retrieved
    assert ts == 1700000000.0
    assert isinstance(frame, np.ndarray)
    assert frame.shape == (10, 10, 3)
    
    # Outside latency threshold should return None
    retrieved_stale = adapter.get_closest_frame("CAM_02", 1700000010.0, max_latency=1.0)
    assert retrieved_stale is None
