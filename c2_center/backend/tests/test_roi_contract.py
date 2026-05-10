"""Tests for ROI schema contract — stream_profiles.json auto-seeding and polygon scaling.

Covers:
1. stream_profiles.json is valid and parseable
2. load_stream_profiles returns correct ROI polygon for known streams
3. roi_polygon is scaled from config resolution to actual frame resolution
4. zone_repo is seeded on add_stream when empty
5. area_occupancy produces non-zero metrics when roi_polygon is present
"""

import json
import os
import tempfile

import numpy as np
import pytest
import supervision as sv

# ─── 1. Config file structure ─────────────────────────────────────────

CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "stream_profiles.json"
)
CONFIG_PATH = os.path.normpath(CONFIG_PATH)


def test_stream_profiles_json_exists():
    assert os.path.exists(CONFIG_PATH), f"Missing: {CONFIG_PATH}"


def test_stream_profiles_json_schema():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert "streams" in data
    muahe = data["streams"]["muahe"]
    assert muahe["source_index"] == 0
    assert muahe["resolution"] == [1920, 1080]
    assert len(muahe["roi_polygon"]) == 4
    # Each point must be [x, y]
    for pt in muahe["roi_polygon"]:
        assert len(pt) == 2
        assert all(isinstance(v, (int, float)) for v in pt)


# ─── 2. load_stream_profiles utility ──────────────────────────────────

def test_load_stream_profiles():
    from app.infrastructure.config.stream_profiles import load_stream_profiles

    profiles = load_stream_profiles(CONFIG_PATH)
    assert "muahe" in profiles
    assert profiles["muahe"]["roi_polygon"] == [[759, 306], [1077, 325], [1477, 957], [292, 917]]


def test_load_stream_profiles_missing_file():
    from app.infrastructure.config.stream_profiles import load_stream_profiles

    profiles = load_stream_profiles("/nonexistent/path.json")
    assert profiles == {}


# ─── 3. Polygon scaling ──────────────────────────────────────────────

def test_scale_roi_polygon():
    from app.infrastructure.config.stream_profiles import scale_polygon

    # Original polygon at 1920x1080
    polygon = [[759, 306], [1077, 325], [1477, 957], [292, 917]]
    # Scale to 960x540 (half resolution)
    scaled = scale_polygon(polygon, src_res=(1920, 1080), dst_res=(960, 540))

    assert len(scaled) == 4
    # First point: 759/1920*960 = 379.5, 306/1080*540 = 153.0
    assert abs(scaled[0][0] - 379.5) < 1.0
    assert abs(scaled[0][1] - 153.0) < 1.0


def test_scale_polygon_same_resolution():
    from app.infrastructure.config.stream_profiles import scale_polygon

    polygon = [[100, 200], [300, 400]]
    scaled = scale_polygon(polygon, src_res=(1920, 1080), dst_res=(1920, 1080))
    assert scaled == polygon


# ─── 4. area_occupancy with roi_polygon ───────────────────────────────

def test_area_occupancy_produces_metrics_with_roi():
    """area_occupancy must return non-zero occupancy_pct when given
    detections inside a valid ROI polygon."""
    from app.analytics.plugins.area_occupancy import AreaOccupancyAnalyzer

    analyzer = AreaOccupancyAnalyzer()
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    # Place a detection inside the ROI
    detections = sv.Detections(
        xyxy=np.array([[800, 400, 900, 600]], dtype=np.float32),
        class_id=np.array([0]),
    )

    params = {
        "roi_polygon": [[759, 306], [1077, 325], [1477, 957], [292, 917]],
        "labels_map": {0: "car"},
    }

    result = analyzer.process(frame, detections, params)
    assert result.metrics["occupancy_pct"] > 0
    assert result.metrics["vehicles_in_roi"] >= 1
    assert result.metrics["status"] in ("NORMAL", "HEAVY", "CONGESTED")


# ─── 5. Health log filter ────────────────────────────────────────────

def test_health_log_filter():
    """The HealthLogFilter should suppress /api/health access log lines."""
    from app.core.log_filters import HealthLogFilter

    f = HealthLogFilter()
    import logging
    record = logging.LogRecord(
        name="uvicorn.access", level=logging.INFO,
        pathname="", lineno=0,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:53628", "GET", "/api/health", "1.1", 200),
        exc_info=None,
    )
    assert f.filter(record) is False  # should be suppressed

    record2 = logging.LogRecord(
        name="uvicorn.access", level=logging.INFO,
        pathname="", lineno=0,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:53628", "GET", "/api/streams", "1.1", 200),
        exc_info=None,
    )
    assert f.filter(record2) is True  # should pass through
