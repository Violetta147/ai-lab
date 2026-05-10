"""
C2 Center — Algorithm 2: BEV Area Occupancy

Ported from density/density_area_occupancy.py
Uses Homography to compute Bird's Eye View occupancy percentage.
"""

import cv2
import numpy as np
import supervision as sv

from app.analytics.base import AnalysisResult, BaseAnalyzer


import os
import json

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "occupancy_config.json")
DEFAULT_THRESHOLDS = {
    "NORMAL": 20,
    "HEAVY": 40,
    "CONGESTED": 60
}

class AreaOccupancyAnalyzer(BaseAnalyzer):
    """
    Computes road occupancy by transforming vehicle bounding boxes
    into a Bird's Eye View (BEV) plane and measuring pixel coverage.
    """

    BEV_SIZE = 500  # BEV canvas width and height

    @property
    def name(self) -> str:
        return "Area Occupancy (BEV)"

    @property
    def slug(self) -> str:
        return "area_occupancy"

    def __init__(self) -> None:
        self._box_annotator = sv.BoxAnnotator(thickness=2)
        self._thresholds = self._load_config()
        # Cache homography matrix to avoid recomputing every frame
        self._cached_roi_key: tuple | None = None
        self._cached_matrix: np.ndarray | None = None

    def _load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r") as f:
                    data = json.load(f)
                    return data.get("thresholds", DEFAULT_THRESHOLDS)
            except Exception:
                return DEFAULT_THRESHOLDS
        return DEFAULT_THRESHOLDS

    def process(
        self,
        frame: np.ndarray,
        detections: sv.Detections,
        params: dict,
    ) -> AnalysisResult:
        """
        params:
            roi_polygon: list of exactly 4 [x, y] points (perspective source)
            labels_map: dict class_id -> class_name
        """
        roi_polygon = params.get("roi_polygon")
        labels_map = params.get("labels_map", {})

        annotated = frame.copy()

        if roi_polygon is None or len(roi_polygon) != 4:
            return AnalysisResult(
                annotated_frame=annotated,
                metrics={"occupancy_pct": 0.0, "method": self.slug},
            )

        src_pts = np.array(roi_polygon, dtype=np.float32)
        dst_pts = np.array(
            [
                [0, 0],
                [self.BEV_SIZE, 0],
                [self.BEV_SIZE, self.BEV_SIZE],
                [0, self.BEV_SIZE],
            ],
            dtype=np.float32,
        )

        # Cache homography — only recompute when ROI changes
        roi_key = tuple(tuple(pt) for pt in roi_polygon)
        if roi_key != self._cached_roi_key:
            self._cached_matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
            self._cached_roi_key = roi_key
        perspective_matrix = self._cached_matrix
        total_bev_pixels = self.BEV_SIZE * self.BEV_SIZE

        # BEV canvas
        bev_canvas = np.zeros((self.BEV_SIZE, self.BEV_SIZE), dtype=np.uint8)

        # Filter detections inside ROI polygon
        roi_int = src_pts.astype(np.int32)
        in_roi_mask = []
        for bbox in detections.xyxy:
            cx = int((bbox[0] + bbox[2]) / 2)
            cy = int((bbox[1] + bbox[3]) / 2)
            inside = cv2.pointPolygonTest(roi_int, (cx, cy), False) >= 0
            in_roi_mask.append(inside)

        mask = np.array(in_roi_mask, dtype=bool) if in_roi_mask else np.array([], dtype=bool)
        det_in_roi = detections[mask] if len(mask) > 0 else detections[:0]

        # Transform each bbox to BEV and paint
        for bbox in det_in_roi.xyxy:
            x1, y1, x2, y2 = bbox
            box_corners = np.array(
                [[[x1, y1], [x2, y1], [x2, y2], [x1, y2]]], dtype=np.float32
            )
            transformed = cv2.perspectiveTransform(box_corners, perspective_matrix)
            bev_polygon = np.int32(transformed)
            cv2.fillPoly(bev_canvas, bev_polygon, 255)

        # Compute occupancy
        occupied_pixels = cv2.countNonZero(bev_canvas)
        occupancy_pct = (occupied_pixels / total_bev_pixels) * 100

        # Annotate main frame
        annotated = self._box_annotator.annotate(scene=annotated, detections=det_in_roi)
        cv2.polylines(annotated, [roi_int], True, (0, 0, 255), 2)

        # Color-coded status using custom thresholds
        t = self._thresholds
        if occupancy_pct > t.get("CONGESTED", 60):
            status_color = (0, 0, 255)  # Red — congested
            status_text = "CONGESTED"
        elif occupancy_pct > t.get("HEAVY", 40):
            status_color = (0, 165, 255)  # Orange — heavy
            status_text = "HEAVY"
        else:
            status_color = (0, 255, 0)  # Green — normal
            status_text = "NORMAL"

        # HUD
        cv2.rectangle(annotated, (10, 10), (500, 70), (0, 0, 0), -1)
        
        display_text = f"Occupancy: {occupancy_pct:.1f}% | {status_text}"
        if not det_in_roi and occupancy_pct == 0.0:
            # Check if we've ever seen detections
            if not getattr(self, "_ever_seen_detections", False):
                display_text = "Occupancy: Initializing..."
        else:
            self._ever_seen_detections = True

        cv2.putText(
            annotated,
            display_text,
            (20, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            status_color,
            2,
        )

        # Minimap (BEV radar) — bottom-right corner
        colored_bev = cv2.cvtColor(bev_canvas, cv2.COLOR_GRAY2BGR)
        colored_bev[np.where((colored_bev == [255, 255, 255]).all(axis=2))] = [
            0,
            0,
            255,
        ]
        minimap = cv2.resize(colored_bev, (150, 150))
        h, w = annotated.shape[:2]
        y_start = h - 170
        x_start = w - 170
        if y_start > 0 and x_start > 0:
            annotated[y_start : y_start + 150, x_start : x_start + 150] = minimap
            cv2.putText(
                annotated,
                "BEV Radar",
                (x_start, y_start - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 255, 255),
                1,
            )

        # Per-class counts
        class_counts = {}
        if det_in_roi.class_id is not None:
            for cid in det_in_roi.class_id:
                name = labels_map.get(int(cid), f"class_{cid}")
                class_counts[name] = class_counts.get(name, 0) + 1

        return AnalysisResult(
            annotated_frame=annotated,
            metrics={
                "occupancy_pct": round(occupancy_pct, 2),
                "status": status_text,
                "vehicles_in_roi": len(det_in_roi),
                "class_counts": class_counts,
                "method": self.slug,
            },
        )
