"""Tests for analyzer mode tagging (Option D: live vs offline split)."""

import pytest

from app.analytics.registry import AnalyticsRegistry, registry as global_registry


def test_global_registry_discovers_all_six_plugins():
    """The composition root in main.py runs registry.discover('app.analytics.plugins').
    For tests we re-discover into a fresh registry to keep the fixture isolated."""
    reg = AnalyticsRegistry()
    discovered = reg.discover("app.analytics.plugins")
    assert discovered == 6, f"Expected 6 analyzers, got {discovered}: {reg.slugs()}"


@pytest.fixture
def reg() -> AnalyticsRegistry:
    r = AnalyticsRegistry()
    r.discover("app.analytics.plugins")
    return r


def test_live_mode_filter_returns_only_live_analyzers(reg):
    live = {m.slug for m in reg.list_all(mode="live")}
    assert live == {"heatmap", "absolute_count", "line_crossing", "area_occupancy"}


def test_offline_mode_filter_returns_only_offline_analyzers(reg):
    offline = {m.slug for m in reg.list_all(mode="offline")}
    assert offline == {"pce_density", "fundamental_equation"}


def test_no_mode_filter_returns_all_six(reg):
    all_metas = reg.list_all()
    assert len(all_metas) == 6


def test_metadata_includes_mode_field(reg):
    for meta in reg.list_all():
        assert meta.mode in ("live", "offline", "both")
        # to_dict must include mode for the API response
        assert "mode" in meta.to_dict()


def test_get_mode_returns_correct_tag(reg):
    assert reg.get_mode("heatmap") == "live"
    assert reg.get_mode("pce_density") == "offline"
    assert reg.get_mode("does_not_exist") == "both"  # safe default
