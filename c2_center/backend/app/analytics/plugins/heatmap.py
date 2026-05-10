"""
C2 Center — Heatmap Analyzer

Accumulates detection positions over time using sv.HeatMapAnnotator.
"""

import numpy as np
import supervision as sv
from app.analytics.base import AnalysisResult, BaseAnalyzer


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
        # Build per-class counts
        labels_map = params.get("labels_map", {})
        class_counts = {}
        if detections.class_id is not None:
            for cid in detections.class_id:
                name = labels_map.get(int(cid), f"class_{cid}")
                class_counts[name] = class_counts.get(name, 0) + 1
        return AnalysisResult(out, {
            "vehicle_count": len(detections),
            "class_counts": class_counts,
            "method": self.slug,
        })
