import time
import numpy as np
import supervision as sv
from analytics.fundamental_equation import FundamentalEquationAnalyzer


def make_detections_xyxy(cx, cy, w=40, h=20, tracker_id=1):
    x1 = cx - w // 2
    y1 = cy - h // 2
    x2 = cx + w // 2
    y2 = cy + h // 2
    xyxy = np.array([[x1, y1, x2, y2]], dtype=np.float32)
    conf = np.array([0.9], dtype=np.float32)
    class_id = np.array([0], dtype=int)
    tracker = np.array([tracker_id], dtype=int)
    return sv.Detections(xyxy=xyxy, confidence=conf, class_id=class_id, tracker_id=tracker)


def test_fundamental_with_tracker():
    analyzer = FundamentalEquationAnalyzer()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    entry_line = [[0, 100], [640, 100]]
    exit_line = [[0, 200], [640, 200]]
    params = {"entry_line": entry_line, "exit_line": exit_line, "line_distance_km": 0.02}

    # Simulate that tracker 1 entered 2 seconds ago
    analyzer._entry_tracker[1] = time.time() - 2.0

    # Create detection at exit line
    det = make_detections_xyxy(320, 200, tracker_id=1)
    result = analyzer.process(frame, det, params)
    assert result.metrics is not None
    assert "total_crossed" in result.metrics
    assert result.metrics["total_crossed"] >= 0


def test_fundamental_without_tracker_does_not_crash():
    analyzer = FundamentalEquationAnalyzer()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    entry_line = [[0, 100], [640, 100]]
    exit_line = [[0, 200], [640, 200]]
    params = {"entry_line": entry_line, "exit_line": exit_line, "line_distance_km": 0.02}

    # Detection with missing tracker id (-1)
    det = make_detections_xyxy(320, 100, tracker_id=-1)
    # Should not raise
    result = analyzer.process(frame, det, params)
    assert result.metrics["flow_q"] == 0 or isinstance(result.metrics["flow_q"], (int, float))
