"""
C2 Center — Line Crossing Counter

Simple directional vehicle counting using sv.LineZone.
"""

import cv2
import numpy as np
import supervision as sv
from app.analytics.base import AnalysisResult, BaseAnalyzer


class LineCrossingAnalyzer(BaseAnalyzer):
    @property
    def name(self): return "Line Crossing"
    @property
    def slug(self): return "line_crossing"

    def __init__(self):
        self._line_zone: sv.LineZone | None = None
        self._line_ann = sv.LineZoneAnnotator(thickness=2, text_thickness=1, text_scale=0.5)
        self._box_ann = sv.BoxAnnotator(thickness=2)
        self._prev_line = None

    def reset(self):
        self._line_zone = None
        self._prev_line = None

    def process(self, frame, detections, params):
        line = params.get("entry_line")  # [[x1,y1],[x2,y2]]
        out = frame.copy()

        if line is None:
            return AnalysisResult(out, {"in_count": 0, "out_count": 0, "method": self.slug})

        # Recreate LineZone if line changed
        if line != self._prev_line:
            start = sv.Point(x=line[0][0], y=line[0][1])
            end = sv.Point(x=line[1][0], y=line[1][1])
            self._line_zone = sv.LineZone(start=start, end=end)
            self._prev_line = line

        self._line_zone.trigger(detections=detections)
        out = self._box_ann.annotate(scene=out, detections=detections)
        out = self._line_ann.annotate(frame=out, line_counter=self._line_zone)

        return AnalysisResult(out, {
            "in_count": self._line_zone.in_count,
            "out_count": self._line_zone.out_count,
            "method": self.slug,
        })
