"""
C2 Center — Algorithm 4: Fundamental Traffic Equation (k = q / v)

Ported from density/density_fundamental_equation.py
Uses entry/exit line crossing to compute flow rate and speed.
"""

import time
from collections import deque

import cv2
import numpy as np
import supervision as sv

from analytics.base import AnalysisResult, BaseAnalyzer

WINDOW_SEC = 30.0  # Sliding window for flow rate


class FundamentalEquationAnalyzer(BaseAnalyzer):
    @property
    def name(self): return "Fundamental Equation (k=q/v)"
    @property
    def slug(self): return "fundamental_equation"

    def __init__(self):
        self._box_ann = sv.BoxAnnotator(thickness=2)
        self._entry_events: deque = deque()  # (timestamp,)
        self._exit_events: deque = deque()   # (timestamp,)
        self._entry_tracker: dict[int, float] = {}  # tracking_id -> entry_time
        self._speeds: deque = deque(maxlen=100)  # recent speed measurements
        self._total_crossed = 0

    def reset(self):
        self._entry_events.clear()
        self._exit_events.clear()
        self._entry_tracker.clear()
        self._speeds.clear()
        self._total_crossed = 0

    def process(self, frame, detections, params):
        entry_line = params.get("entry_line")  # [[x1,y1],[x2,y2]]
        exit_line = params.get("exit_line")    # [[x1,y1],[x2,y2]]
        line_distance_km = params.get("line_distance_km", 0.02)
        speed_limit_kmh = params.get("speed_limit_kmh", 60)
        labels_map = params.get("labels_map", {})
        fps = params.get("fps", 30)

        out = frame.copy()
        now = time.time()

        if entry_line is None or exit_line is None:
            return AnalysisResult(out, {"flow_q": 0, "avg_speed": 0, "density_k": 0, "method": self.slug})

        entry_p1, entry_p2 = tuple(entry_line[0]), tuple(entry_line[1])
        exit_p1, exit_p2 = tuple(exit_line[0]), tuple(exit_line[1])

        # Check line crossings for each tracked vehicle
        if detections.tracker_id is not None:
            for i, trk_id in enumerate(detections.tracker_id):
                trk_id = int(trk_id)
                if trk_id == -1:
                    continue
                bbox = detections.xyxy[i]
                cx = int((bbox[0] + bbox[2]) / 2)
                cy = int((bbox[1] + bbox[3]) / 2)

                # Check entry line crossing (simple y-threshold)
                entry_y = (entry_p1[1] + entry_p2[1]) // 2
                exit_y = (exit_p1[1] + exit_p2[1]) // 2

                if trk_id not in self._entry_tracker:
                    if abs(cy - entry_y) < 15:
                        self._entry_tracker[trk_id] = now
                        self._entry_events.append(now)
                else:
                    if abs(cy - exit_y) < 15:
                        entry_time = self._entry_tracker.pop(trk_id, None)
                        if entry_time:
                            dt = now - entry_time
                            if dt > 0.1:
                                speed = (line_distance_km / dt) * 3600  # km/h
                                if 1 < speed < 250:
                                    self._speeds.append(speed)
                            self._exit_events.append(now)
                            self._total_crossed += 1

        # Purge old events outside sliding window
        cutoff = now - WINDOW_SEC
        while self._entry_events and self._entry_events[0] < cutoff:
            self._entry_events.popleft()
        while self._exit_events and self._exit_events[0] < cutoff:
            self._exit_events.popleft()

        # Clean stale tracker entries (>60s old)
        stale = [k for k, v in self._entry_tracker.items() if now - v > 60]
        for k in stale:
            del self._entry_tracker[k]

        # Compute metrics
        flow_q = (len(self._exit_events) / WINDOW_SEC) * 3600 if self._exit_events else 0
        avg_speed = sum(self._speeds) / len(self._speeds) if self._speeds else speed_limit_kmh
        density_k = flow_q / avg_speed if avg_speed > 0 else 0

        # Annotate
        out = self._box_ann.annotate(scene=out, detections=detections)
        cv2.line(out, entry_p1, entry_p2, (0, 255, 0), 3)
        cv2.line(out, exit_p1, exit_p2, (0, 0, 255), 3)
        cv2.putText(out, "ENTRY", (entry_p1[0], entry_p1[1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
        cv2.putText(out, "EXIT", (exit_p1[0], exit_p1[1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)

        cv2.rectangle(out, (10,10), (460,150), (0,0,0), -1)
        cv2.putText(out, f"Flow (q): {flow_q:.0f} veh/h", (20,40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
        cv2.putText(out, f"Speed (v): {avg_speed:.1f} km/h", (20,75), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
        cv2.putText(out, f"Density (k): {density_k:.1f} veh/km", (20,110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
        cv2.putText(out, f"Total crossed: {self._total_crossed}", (20,140), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1)

        return AnalysisResult(out, {
            "flow_q": round(flow_q, 1), "avg_speed": round(avg_speed, 1),
            "density_k": round(density_k, 2), "total_crossed": self._total_crossed,
            "method": self.slug,
        })
