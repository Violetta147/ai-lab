"""
C2 Center — Heatmap Analyzer

Accumulates detection positions over time using sv.HeatMapAnnotator.
"""

import numpy as np
import supervision as sv
from analytics.base import AnalysisResult, BaseAnalyzer


class HeatmapAnalyzer(BaseAnalyzer):
    @property
    def name(self): return "Heatmap"
    @property
    def slug(self): return "heatmap"

    def __init__(self):
        self._heatmap = sv.HeatMapAnnotator(radius=40, opacity=0.6)

    def reset(self):
        self._heatmap = sv.HeatMapAnnotator(radius=40, opacity=0.6)

    def process(self, frame, detections, params):
        out = self._heatmap.annotate(scene=frame.copy(), detections=detections)
        return AnalysisResult(out, {"vehicle_count": len(detections), "method": self.slug})
