"""
Per-stream analytics dispatcher.

Owns the mapping `stream_id -> active analyzer instance` and runs the
selected analyzer for each frame. Knows about the analytics registry
but nothing about transport (WebSocket) or video acquisition.
"""

import logging

import numpy as np
import supervision as sv

from app.analytics.base import BaseAnalyzer
from app.analytics.registry import AnalyticsRegistry
from app.domain.analytics import AnalysisResult

logger = logging.getLogger(__name__)

# Default live analyzer for newly attached streams.
# `heatmap` is chosen because it requires zero user-drawn calibration (no ROI,
# no lines) and produces meaningful output the moment the first frame arrives.
DEFAULT_ALGORITHM_SLUG = "heatmap"


class AnalyticsDispatcher:
    """Routes (stream, frame, detections) to the analyzer chosen for that stream."""

    def __init__(self, registry: AnalyticsRegistry) -> None:
        self._registry = registry
        self._active_slug: dict[str, str] = {}
        self._analyzers: dict[str, BaseAnalyzer] = {}

    def attach_stream(self, stream_id: str, slug: str | None = None) -> None:
        """Bind a default analyzer to a stream. No-op if already attached."""
        if stream_id in self._analyzers:
            return
        chosen = slug or DEFAULT_ALGORITHM_SLUG
        if not self._registry.has(chosen):
            raise KeyError(f"Unknown algorithm: {chosen}")
        self._active_slug[stream_id] = chosen
        self._analyzers[stream_id] = self._registry.get(chosen)()
        logger.info("[%s] Analyzer attached: %s", stream_id, chosen)

    def detach_stream(self, stream_id: str) -> None:
        """Remove the analyzer binding for a stream."""
        self._active_slug.pop(stream_id, None)
        self._analyzers.pop(stream_id, None)

    def set_algorithm(self, stream_id: str, slug: str) -> None:
        """Switch the active analyzer for a stream."""
        if not self._registry.has(slug):
            raise KeyError(f"Unknown algorithm: {slug}")
        self._active_slug[stream_id] = slug
        self._analyzers[stream_id] = self._registry.get(slug)()
        logger.info("[%s] Algorithm switched to: %s", stream_id, slug)

    def get_active_slug(self, stream_id: str) -> str | None:
        return self._active_slug.get(stream_id)

    def run(
        self,
        stream_id: str,
        frame: np.ndarray,
        detections: sv.Detections,
        params: dict,
    ) -> AnalysisResult:
        """Execute the analyzer attached to `stream_id`.

        If no analyzer is attached, returns a passthrough result so the
        frame can still flow to consumers.
        """
        analyzer = self._analyzers.get(stream_id)
        if analyzer is None:
            return AnalysisResult(annotated_frame=frame, metrics={})
        return analyzer.process(frame, detections, params)
