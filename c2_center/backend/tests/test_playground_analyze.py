"""Tests for POST /api/playground/analyze — runs an analyzer on an uploaded file."""

import io
import json
import types

import cv2
import numpy as np
import pytest
import supervision as sv
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.analytics.registry import registry as analytics_registry
from app.api import playground as playground_module


class _FakeUltralyticsResults:
    """Mimic ultralytics.YOLO predict()[0] output shape used by sv.Detections.from_ultralytics."""

    def __init__(self, frame: np.ndarray) -> None:
        h, w = frame.shape[:2]
        # one fake bounding box centered in the frame
        cx, cy = w // 2, h // 2
        bw, bh = w // 6, h // 6
        self.boxes = types.SimpleNamespace(
            xyxy=_FakeTensor(np.array([[cx - bw, cy - bh, cx + bw, cy + bh]], dtype=np.float32)),
            conf=_FakeTensor(np.array([0.9], dtype=np.float32)),
            cls=_FakeTensor(np.array([0], dtype=np.float32)),
            id=None,
        )
        self.names = {0: "vehicle"}
        self.orig_img = frame
        self.path = ""
        # supervision.Detections.from_ultralytics inspects these — must exist (None is fine)
        self.masks = None
        self.obb = None
        self.probs = None
        self.keypoints = None


class _FakeTensor:
    """Just enough to satisfy sv.Detections.from_ultralytics (.cpu().numpy())."""

    def __init__(self, arr: np.ndarray) -> None:
        self._arr = arr

    def cpu(self):
        return self

    def numpy(self):
        return self._arr

    def __len__(self) -> int:
        return len(self._arr)

    def __getitem__(self, k):
        return self._arr[k]


class _FakeYOLO:
    def predict(self, frame, **kwargs):
        return [_FakeUltralyticsResults(frame)]


class _FakeModelRegistry:
    def __init__(self) -> None:
        self.active_model_name = "fake_model"
        self._labels = ["vehicle"]
        self._yolo = _FakeYOLO()

    def list_models(self):
        return [types.SimpleNamespace(name="fake_model")]

    def get_active_model(self):
        return self._yolo

    def get_model(self, name):
        return self._yolo

    def get_labels(self, name):
        return self._labels


@pytest.fixture(scope="module")
def client() -> TestClient:
    if not analytics_registry.slugs():
        analytics_registry.discover("app.analytics.plugins")
    app = FastAPI()
    app.include_router(playground_module.get_router(_FakeModelRegistry()))
    return TestClient(app)


def _make_jpeg_bytes(width: int = 320, height: int = 240) -> bytes:
    img = np.full((height, width, 3), 128, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def test_analyze_image_with_heatmap(client):
    """Heatmap analyzer needs no params and runs against a single image upload."""
    jpeg = _make_jpeg_bytes()
    resp = client.post(
        "/api/playground/analyze",
        data={
            "algorithm": "heatmap",
            "confidence": "0.25",
            "overlap": "0.45",
            "params_json": "{}",
        },
        files={"file": ("test.jpg", io.BytesIO(jpeg), "image/jpeg")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["algorithm"] == "heatmap"
    assert body["model"] == "fake_model"
    assert body["kind"] == "image"
    assert body["frames_processed"] == 1
    assert body["data_b64"]  # non-empty base64 image
    assert body["metrics"]["method"] == "heatmap"


def test_analyze_image_with_offline_analyzer_works_in_playground(client):
    """Offline analyzers (pce_density) MUST be runnable in playground given calibration params."""
    jpeg = _make_jpeg_bytes()
    params = {
        "roi_polygon": [[10, 10], [200, 10], [200, 200], [10, 200]],
        "area_m2": 50.0,
    }
    resp = client.post(
        "/api/playground/analyze",
        data={
            "algorithm": "pce_density",
            "params_json": json.dumps(params),
        },
        files={"file": ("test.jpg", io.BytesIO(jpeg), "image/jpeg")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["algorithm"] == "pce_density"
    assert body["kind"] == "image"


def test_analyze_rejects_unknown_algorithm(client):
    jpeg = _make_jpeg_bytes()
    resp = client.post(
        "/api/playground/analyze",
        data={"algorithm": "no_such_thing", "params_json": "{}"},
        files={"file": ("test.jpg", io.BytesIO(jpeg), "image/jpeg")},
    )
    assert resp.status_code == 400
    assert "Unknown algorithm" in resp.json()["detail"]


def test_analyze_rejects_invalid_params_json(client):
    jpeg = _make_jpeg_bytes()
    resp = client.post(
        "/api/playground/analyze",
        data={"algorithm": "heatmap", "params_json": "{not valid json"},
        files={"file": ("test.jpg", io.BytesIO(jpeg), "image/jpeg")},
    )
    assert resp.status_code == 400
    assert "params_json" in resp.json()["detail"]
