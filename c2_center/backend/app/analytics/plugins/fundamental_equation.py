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

from app.analytics.base import AnalysisResult, BaseAnalyzer

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
        # Local lightweight tracker used when no tracker_id is provided by DeepStream
        self._local_tracks: dict[int, dict] = {}  # id -> {pos, last_seen, entered_time, active}
        self._local_next_id = 1

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

        # Check line crossings for each tracked vehicle. If tracker IDs are missing,
        # fall back to a lightweight local matcher that attempts to associate centroids
        # across frames for short-lived tracks.
        entry_y = (entry_p1[1] + entry_p2[1]) // 2
        exit_y = (exit_p1[1] + exit_p2[1]) // 2

        tracker_ids = None
        try:
            tracker_ids = detections.tracker_id if hasattr(detections, "tracker_id") else None
        except Exception:
            tracker_ids = None

        if tracker_ids is not None and tracker_ids.size > 0 and int(tracker_ids.max()) != -1:
            # Use provided tracker IDs
            for i, trk_id in enumerate(tracker_ids):
                trk_id = int(trk_id)
                if trk_id == -1:
                    continue
                bbox = detections.xyxy[i]
                cx = int((bbox[0] + bbox[2]) / 2)
                cy = int((bbox[1] + bbox[3]) / 2)

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
        else:
            # Local matching fallback (centroid nearest-neighbor within short time window)
            centroids = []
            for i in range(len(detections)):
                bbox = detections.xyxy[i]
                cx = int((bbox[0] + bbox[2]) / 2)
                cy = int((bbox[1] + bbox[3]) / 2)
                centroids.append((cx, cy))

            # Try to match centroids to existing local tracks
            matched = set()
            for cid, (cx, cy) in enumerate(centroids):
                matched_id = None
                best_dist = 1e9
                for tid, info in list(self._local_tracks.items()):
                    dist = (info["pos"][0] - cx) ** 2 + (info["pos"][1] - cy) ** 2
                    if dist < best_dist and (now - info["last_seen"]) < 2.0:
                        best_dist = dist
                        matched_id = tid

                if matched_id is None:
                    # Create new local track
                    tid = self._local_next_id
                    self._local_next_id += 1
                    self._local_tracks[tid] = {"pos": (cx, cy), "last_seen": now, "entered_time": None, "active": True}
                    matched_id = tid
                else:
                    # Update existing
                    self._local_tracks[matched_id]["pos"] = (cx, cy)
                    self._local_tracks[matched_id]["last_seen"] = now

                matched.add(matched_id)

                info = self._local_tracks[matched_id]
                # entry
                if info["entered_time"] is None and abs(cy - entry_y) < 15:
                    info["entered_time"] = now
                    self._entry_events.append(now)
                # exit
                elif info["entered_time"] is not None and abs(cy - exit_y) < 15:
                    entry_time = info["entered_time"]
                    if entry_time:
                        dt = now - entry_time
                        if dt > 0.1:
                            speed = (line_distance_km / dt) * 3600
                            if 1 < speed < 250:
                                self._speeds.append(speed)
                        self._exit_events.append(now)
                        self._total_crossed += 1
                    # reset the local track so it can be reused
                    info["entered_time"] = None

            # Purge stale local tracks
            stale = [k for k, v in self._local_tracks.items() if now - v["last_seen"] > 5]
            for k in stale:
                del self._local_tracks[k]

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
