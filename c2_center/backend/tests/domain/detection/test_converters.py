import numpy as np
import pytest
from typing import List, Dict, Any

from app.domain.detection.converters import metadata_to_detections

def test_metadata_to_detections_normal(sample_detection_payload: List[Dict[str, Any]]):
    """Test converting standard metadata into Detections object."""
    detections = metadata_to_detections(sample_detection_payload)
    
    assert len(detections) == 2
    assert detections.class_id.tolist() == [0, 2]
    assert np.allclose(detections.confidence, [0.95, 0.88])
    assert detections.tracker_id.tolist() == [1, 2]
    
    expected_bboxes = np.array([
        [10.0, 20.0, 50.0, 100.0],
        [200.0, 150.0, 300.0, 250.0]
    ])
    assert np.allclose(detections.xyxy, expected_bboxes)

def test_metadata_to_detections_empty():
    """Test handling of empty object list."""
    detections = metadata_to_detections([])
    
    assert len(detections) == 0
    assert detections.class_id.shape == (0,)
    assert detections.confidence.shape == (0,)
    # Output of empty detections has no tracker_id by default in supervision 0.22.0
    assert getattr(detections, "tracker_id", None) is None

def test_metadata_to_detections_missing_tracker_id():
    """Test that missing tracker_ids (-1) cause the field to be omitted."""
    payload = [
        {
            "class_id": 0,
            "class_name": "person",
            "confidence": 0.95,
            "tracking_id": -1,
            "bbox": [10.0, 20.0, 50.0, 100.0]
        },
        {
            "class_id": 2,
            "class_name": "car",
            "confidence": 0.88,
            "tracking_id": -1,
            "bbox": [200.0, 150.0, 300.0, 250.0]
        }
    ]
    detections = metadata_to_detections(payload)
    
    assert len(detections) == 2
    # Because all tracker_ids are -1, the attribute should not be injected
    assert getattr(detections, "tracker_id", None) is None
    
def test_metadata_to_detections_partial_tracker_id():
    """Test handling of some missing tracker_ids mixed with valid ones.
    Currently, the logic injects the array if *any* tracker_id != -1.
    """
    payload = [
        {
            "class_id": 0,
            "class_name": "person",
            "confidence": 0.95,
            "tracking_id": 1,
            "bbox": [10.0, 20.0, 50.0, 100.0]
        },
        {
            "class_id": 2,
            "class_name": "car",
            "confidence": 0.88,
            "tracking_id": -1,
            "bbox": [200.0, 150.0, 300.0, 250.0]
        }
    ]
    detections = metadata_to_detections(payload)
    
    assert len(detections) == 2
    # The array is injected. The missing one is preserved as -1.
    assert detections.tracker_id is not None
    assert detections.tracker_id.tolist() == [1, -1]
