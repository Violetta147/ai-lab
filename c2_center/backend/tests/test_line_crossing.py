import numpy as np
import supervision as sv
from app.analytics.plugins.line_crossing import LineCrossingAnalyzer


def test_line_crossing_missing_tracker_id():
    """
    Test that the LineCrossingAnalyzer can handle detections that lack tracker_ids
    (e.g., from raw playground predictions) by assigning local tracking IDs
    via ByteTrack and correctly counting the crossings.
    """
    analyzer = LineCrossingAnalyzer()

    # Horizontal line at y=250 on a 500x500 frame
    params = {
        "entry_line": [[100, 250], [400, 250]],
        "fps": 30,
    }

    frame = np.zeros((500, 500, 3), dtype=np.uint8)

    # Simulate a vehicle (100x100 bbox) moving from y=100 to y=400 in 5px steps.
    # Each step has high IOU overlap with the previous, so ByteTrack maintains the
    # same tracker_id.  The object crosses the line at y=250.
    for y in range(100, 400, 5):
        boxes = np.array([[200.0, float(y - 50), 300.0, float(y + 50)]])
        det = sv.Detections(
            xyxy=boxes,
            class_id=np.array([0]),
            confidence=np.array([0.9]),
            # NOTE: no tracker_id — this is the bug we're fixing
        )
        res = analyzer.process(frame, det, params)

    metrics = res.metrics
    crossed = metrics.get("in_count", 0) + metrics.get("out_count", 0)

    assert crossed == 1, (
        f"Expected 1 crossing, got {crossed} "
        f"(in: {metrics.get('in_count')}, out: {metrics.get('out_count')})"
    )


def test_line_crossing_with_tracker_id():
    """
    Ensure that when detections already carry a tracker_id (the normal
    DeepStream path), the analyzer does NOT double-track and still counts
    correctly.
    """
    analyzer = LineCrossingAnalyzer()

    params = {
        "entry_line": [[100, 250], [400, 250]],
        "fps": 30,
    }

    frame = np.zeros((500, 500, 3), dtype=np.uint8)

    for y in range(100, 400, 5):
        boxes = np.array([[200.0, float(y - 50), 300.0, float(y + 50)]])
        det = sv.Detections(
            xyxy=boxes,
            class_id=np.array([0]),
            confidence=np.array([0.9]),
            tracker_id=np.array([42]),  # pre-assigned by DeepStream
        )
        res = analyzer.process(frame, det, params)

    metrics = res.metrics
    crossed = metrics.get("in_count", 0) + metrics.get("out_count", 0)

    assert crossed == 1, (
        f"Expected 1 crossing with pre-assigned tracker_id, got {crossed}"
    )
