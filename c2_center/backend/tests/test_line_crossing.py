import pytest
import numpy as np
import supervision as sv
from app.analytics.plugins.line_crossing import LineCrossingAnalyzer

def test_line_crossing_missing_tracker_id():
    """
    Test that the LineCrossingAnalyzer can handle detections that lack tracker_ids
    (e.g., from raw playground predictions) by assigning local tracking IDs
    and correctly counting the crossings.
    """
    analyzer = LineCrossingAnalyzer()
    
    # 1. Setup a horizontal line at y=50
    params = {
        "entry_line": [[10, 50], [90, 50]],
        "fps": 30
    }
    
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    
    # 2. Frame 1: Object is at y=40 (above the line, heading down to exit/entry depending on line orientation)
    # The default line zone counts crossing based on line orientation.
    # We will simulate an object moving from y=40 to y=60 across the line.
    boxes_1 = np.array([[45, 35, 55, 45]]) # cx=50, cy=40
    class_ids_1 = np.array([0])
    conf_1 = np.array([0.9])
    
    det_1 = sv.Detections(
        xyxy=boxes_1,
        class_id=class_ids_1,
        confidence=conf_1,
        # NOTICE: NO tracker_id
    )
    
    res_1 = analyzer.process(frame, det_1, params)
    
    # 3. Frame 2: Object is at y=60 (crossed the line)
    boxes_2 = np.array([[45, 55, 55, 65]]) # cx=50, cy=60
    class_ids_2 = np.array([0])
    conf_2 = np.array([0.9])
    
    det_2 = sv.Detections(
        xyxy=boxes_2,
        class_id=class_ids_2,
        confidence=conf_2,
        # NOTICE: NO tracker_id
    )
    
    res_2 = analyzer.process(frame, det_2, params)
    
    # 4. Assert that either in_count or out_count is 1
    # Without tracker_id fallback, both will be 0.
    metrics = res_2.metrics
    crossed = metrics.get("in_count", 0) + metrics.get("out_count", 0)
    
    assert crossed == 1, f"Expected 1 crossing, got {crossed} (in: {metrics.get('in_count')}, out: {metrics.get('out_count')})"
