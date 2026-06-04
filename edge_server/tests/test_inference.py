import queue
import time
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from edge_server.inference import process_and_send


class MockBox:
    def __init__(self):
        self.xyxy = [np.array([10, 20, 30, 40])]
        self.cls = [0]
        self.conf = [0.8]


class MockResult:
    def __init__(self):
        self.boxes = [MockBox()]


class MockYOLO:
    def __init__(self):
        self.names = {0: "car"}

    def __call__(self, frame, conf):
        return [MockResult()]


def test_process_and_send_live_telemetry_and_al_queue():
    frame = np.zeros((640, 640, 3), dtype=np.uint8)
    model = MockYOLO()
    ram_queue = queue.Queue(maxsize=10)
    mqtt_client_instance = MagicMock()
    
    active_learning_filter = MagicMock()
    active_learning_filter.should_save_frame.return_value = (True, "AL Hit")
    
    publish_gate = MagicMock()
    publish_gate.should_publish.return_value = (True, "Gate Open")
    
    rule_ood_filter = MagicMock()
    rule_ood_filter.should_flag_ood.return_value = (False, "Clear")

    with patch("edge_server.inference.build_image_name", return_value="test_img.jpg"):
        with patch("edge_server.inference.publish_detection") as mock_publish:
            process_and_send(
                frame=frame,
                model=model,
                ram_queue=ram_queue,
                mqtt_client_instance=mqtt_client_instance,
                camera_id="cam1",
                active_learning_filter=active_learning_filter,
                publish_gate=publish_gate,
                rule_ood_filter=rule_ood_filter,
            )
            
            # Live tracking logic
            mock_publish.assert_called_once()
            
            # AL hit logic -> frame + metadata in queue
            assert not ram_queue.empty()
            queued_item = ram_queue.get_nowait()
            assert queued_item["metadata"]["image_url"] == "test_img.jpg"
            assert np.array_equal(queued_item["frame"], frame)

def test_process_and_send_queue_full_non_blocking():
    frame = np.zeros((640, 640, 3), dtype=np.uint8)
    model = MockYOLO()
    ram_queue = queue.Queue(maxsize=1)
    
    # Fill the queue
    ram_queue.put_nowait({"mock": "data"})
    
    mqtt_client_instance = MagicMock()
    
    active_learning_filter = MagicMock()
    active_learning_filter.should_save_frame.return_value = (True, "AL Hit")
    
    publish_gate = MagicMock()
    publish_gate.should_publish.return_value = (True, "Gate Open")
    
    rule_ood_filter = MagicMock()
    rule_ood_filter.should_flag_ood.return_value = (False, "Clear")

    with patch("edge_server.inference.build_image_name", return_value="test_img.jpg"):
        with patch("edge_server.inference.publish_detection") as mock_publish:
            # Should not raise queue.Full exception! Should catch it and drop gracefully
            process_and_send(
                frame=frame,
                model=model,
                ram_queue=ram_queue,
                mqtt_client_instance=mqtt_client_instance,
                camera_id="cam1",
                active_learning_filter=active_learning_filter,
                publish_gate=publish_gate,
                rule_ood_filter=rule_ood_filter,
            )
            
            # Still published live detection
            mock_publish.assert_called_once()
            
            # Queue size remains 1
            assert ram_queue.qsize() == 1
