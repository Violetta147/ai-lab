"""
C2 Center — Algorithm 1: Absolute Count Density (k = N / L)

Ported from density/density_absolute_count.py
Counts vehicles whose centroids fall within a user-drawn polygon.
"""

import cv2
import numpy as np
import supervision as sv

from app.analytics.base import AnalysisResult, BaseAnalyzer


class AbsoluteCountAnalyzer(BaseAnalyzer):
    """
    Density = N / L

    N = number of vehicles whose centroid is inside the ROI polygon
    L = real-world road length in km (user-configurable)
    """

    @property
    def name(self) -> str:
        return "Absolute Count"

    @property
    def slug(self) -> str:
        return "absolute_count"

    def __init__(self) -> None:
        self._box_annotator = sv.BoxAnnotator(thickness=2)
        self._label_annotator = sv.LabelAnnotator(
            text_thickness=1, text_scale=0.5, text_color=sv.Color.BLACK
        )

    def process(
        self,
        frame: np.ndarray,
        detections: sv.Detections,
        params: dict,
    ) -> AnalysisResult:
        """
        params:
            roi_polygon: list of [x, y] points defining the ROI
            road_length_km: real-world road length in km (default 0.1)
            labels_map: dict class_id -> class_name
        """
        roi_polygon = params.get("roi_polygon")
        road_length_km = params.get("road_length_km", 0.1)
        labels_map = params.get("labels_map", {})

        annotated = frame.copy()

        if roi_polygon is None or len(detections) == 0:
            # No ROI defined or no detections — return raw frame
            return AnalysisResult(
                annotated_frame=annotated,
                metrics={"vehicle_count": 0, "density_k": 0.0, "method": self.slug},
            )

        roi_np = np.array(roi_polygon, dtype=np.int32)

        # Count centroids inside polygon
        count = 0
        in_roi_mask = []
        for bbox in detections.xyxy:
            cx = int((bbox[0] + bbox[2]) / 2)
            cy = int((bbox[1] + bbox[3]) / 2)
            inside = cv2.pointPolygonTest(roi_np, (cx, cy), False) >= 0
            in_roi_mask.append(inside)
            if inside:
                count += 1

        # Filter detections to ROI
        mask = np.array(in_roi_mask, dtype=bool)
        det_in_roi = detections[mask]

        # Annotate
        labels = []
        if det_in_roi.tracker_id is not None:
            for i, (cls_id, trk_id) in enumerate(
                zip(det_in_roi.class_id, det_in_roi.tracker_id)
            ):
                cls_name = labels_map.get(int(cls_id), f"cls{cls_id}")
                labels.append(f"#{trk_id} {cls_name}")
        else:
            for cls_id in det_in_roi.class_id:
                cls_name = labels_map.get(int(cls_id), f"cls{cls_id}")
                labels.append(cls_name)

        annotated = self._box_annotator.annotate(scene=annotated, detections=det_in_roi)
        annotated = self._label_annotator.annotate(
            scene=annotated, detections=det_in_roi, labels=labels
        )

        # Draw centroids
        for bbox in det_in_roi.xyxy:
            cx = int((bbox[0] + bbox[2]) / 2)
            cy = int((bbox[1] + bbox[3]) / 2)
            cv2.circle(annotated, (cx, cy), 4, (0, 255, 255), -1)

        # Draw ROI polygon
        cv2.polylines(annotated, [roi_np], True, (0, 0, 255), 2)

        # Compute density
        density_k = count / road_length_km if road_length_km > 0 else 0

        # Draw HUD
        cv2.rectangle(annotated, (10, 10), (400, 100), (0, 0, 0), -1)
        cv2.putText(
            annotated,
            f"Vehicles (N): {count}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            annotated,
            f"Density (k): {density_k:.1f} veh/km",
            (20, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )

        return AnalysisResult(
            annotated_frame=annotated,
            metrics={
                "vehicle_count": count,
                "density_k": round(density_k, 2),
                "road_length_km": road_length_km,
                "method": self.slug,
            },
        )
