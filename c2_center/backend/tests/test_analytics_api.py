"""Tests for the analytics REST API: mode filter + live-rejects-offline."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.analytics.registry import registry as analytics_registry
from app.api import analytics_api as analytics_api_module


class _FakeDispatcher:
    """In-memory dispatcher that just records the last set algorithm."""

    def __init__(self) -> None:
        self.last_set: tuple[str, str] | None = None

    def set_algorithm(self, stream_id: str, slug: str) -> None:
        self.last_set = (stream_id, slug)


class _FakePipeline:
    def __init__(self) -> None:
        self.analytics_dispatcher = _FakeDispatcher()


@pytest.fixture(scope="module")
def client() -> TestClient:
    # Make sure the module-level registry has plugins discovered.
    if not analytics_registry.slugs():
        analytics_registry.discover("app.analytics.plugins")
    app = FastAPI()
    pipeline = _FakePipeline()
    app.include_router(analytics_api_module.get_router(pipeline))
    app.state.pipeline = pipeline  # so tests can inspect dispatcher
    return TestClient(app)


def test_list_algorithms_returns_all_by_default(client):
    resp = client.get("/api/analytics/algorithms")
    assert resp.status_code == 200
    slugs = {item["slug"] for item in resp.json()}
    assert slugs == {
        "heatmap", "absolute_count", "line_crossing",
        "pce_density", "area_occupancy", "fundamental_equation",
    }


def test_list_algorithms_filter_live(client):
    resp = client.get("/api/analytics/algorithms?mode=live")
    assert resp.status_code == 200
    slugs = {item["slug"] for item in resp.json()}
    assert slugs == {"heatmap", "absolute_count", "line_crossing"}
    for item in resp.json():
        assert item["mode"] == "live"


def test_list_algorithms_filter_offline(client):
    resp = client.get("/api/analytics/algorithms?mode=offline")
    assert resp.status_code == 200
    slugs = {item["slug"] for item in resp.json()}
    assert slugs == {"pce_density", "area_occupancy", "fundamental_equation"}


def test_list_algorithms_invalid_mode_rejected(client):
    resp = client.get("/api/analytics/algorithms?mode=bogus")
    # FastAPI Literal validation -> 422
    assert resp.status_code == 422


def test_set_algorithm_accepts_live_analyzer(client):
    resp = client.put(
        "/api/analytics/algorithm/cam01",
        json={"algorithm": "heatmap"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["algorithm"] == "heatmap"


def test_set_algorithm_rejects_offline_analyzer_for_live_stream(client):
    resp = client.put(
        "/api/analytics/algorithm/cam01",
        json={"algorithm": "pce_density"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "offline" in body["detail"].lower()
    assert "playground" in body["detail"].lower()


def test_set_algorithm_rejects_unknown_slug(client):
    resp = client.put(
        "/api/analytics/algorithm/cam01",
        json={"algorithm": "no_such_analyzer"},
    )
    assert resp.status_code == 400
    assert "Invalid algorithm" in resp.json()["detail"]
