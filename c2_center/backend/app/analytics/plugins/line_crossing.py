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
        self._entry_zone: sv.LineZone | None = None
        self._exit_zone: sv.LineZone | None = None
        # Green for entry, Red for exit
        self._entry_ann = sv.LineZoneAnnotator(thickness=2, text_thickness=1, text_scale=0.5, color=sv.Color.from_hex("#00FF00"))
        self._exit_ann = sv.LineZoneAnnotator(thickness=2, text_thickness=1, text_scale=0.5, color=sv.Color.from_hex("#FF0000"))
        self._box_ann = sv.BoxAnnotator(thickness=2)
        self._prev_entry = None
        self._prev_exit = None
        self._tracker = sv.ByteTrack(minimum_consecutive_frames=1)

    def reset(self):
        self._entry_zone = None
        self._exit_zone = None
        self._prev_entry = None
        self._prev_exit = None

    def process(self, frame, detections, params):
        entry_line = params.get("entry_line")  # [[x1,y1],[x2,y2]]
        exit_line = params.get("exit_line")    # [[x1,y1],[x2,y2]]
        out = frame.copy()

        if entry_line is None and exit_line is None:
            return AnalysisResult(out, {"in_count": 0, "out_count": 0, "method": self.slug})

        # Recreate Entry Zone if changed
        if entry_line != self._prev_entry:
            if entry_line:
                start = sv.Point(x=entry_line[0][0], y=entry_line[0][1])
                end = sv.Point(x=entry_line[1][0], y=entry_line[1][1])
                self._entry_zone = sv.LineZone(start=start, end=end, triggering_anchors=[sv.Position.BOTTOM_CENTER])
            else:
                self._entry_zone = None
            self._prev_entry = entry_line

        # Recreate Exit Zone if changed
        if exit_line != self._prev_exit:
            if exit_line:
                start = sv.Point(x=exit_line[0][0], y=exit_line[0][1])
                end = sv.Point(x=exit_line[1][0], y=exit_line[1][1])
                self._exit_zone = sv.LineZone(start=start, end=end, triggering_anchors=[sv.Position.BOTTOM_CENTER])
            else:
                self._exit_zone = None
            self._prev_exit = exit_line

        # If detections lack tracker_id, use local ByteTrack
        if getattr(detections, "tracker_id", None) is None:
            detections = self._tracker.update_with_detections(detections=detections)

        if self._entry_zone:
            self._entry_zone.trigger(detections=detections)
        if self._exit_zone:
            self._exit_zone.trigger(detections=detections)

        out = self._box_ann.annotate(scene=out, detections=detections)
        
        if self._entry_zone:
            out = self._entry_ann.annotate(frame=out, line_counter=self._entry_zone)
        if self._exit_zone:
            out = self._exit_ann.annotate(frame=out, line_counter=self._exit_zone)

        # Metrics: in_count comes from entry_zone crossing, out_count from exit_zone
        # Or if it's a single line, sv.LineZone handles both.
        # To satisfy the user's specific request about separate entry/exit lines:
        in_c = self._entry_zone.in_count if self._entry_zone else 0
        out_c = self._exit_zone.out_count if self._exit_zone else 0
        
        # If user only provided one line (e.g. entry_line), sv.LineZone.in_count and out_count
        # represent both directions on THAT line.
        if entry_line and not exit_line:
            in_c = self._entry_zone.in_count
            out_c = self._entry_zone.out_count

        return AnalysisResult(out, {
            "in_count": in_c,
            "out_count": out_c,
            "method": self.slug,
        })
