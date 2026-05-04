"""
C2 Center — Algorithm 3: PCE-Aware Density

Ported from density/density_pce_aware.py
"""

import cv2
import numpy as np
import supervision as sv
from analytics.base import AnalysisResult, BaseAnalyzer

DEFAULT_PCE_WEIGHTS = {"car": 1.0, "motor": 0.5, "heavy_vehicle": 2.5}
THRESHOLD_HEAVY = 800
THRESHOLD_JAM = 1500


class PCEDensityAnalyzer(BaseAnalyzer):
    @property
    def name(self): return "PCE-Aware Density"
    @property
    def slug(self): return "pce_density"

    def __init__(self):
        self._box_ann = sv.BoxAnnotator(thickness=2)
        self._lbl_ann = sv.LabelAnnotator(text_thickness=1, text_scale=0.5)

    def process(self, frame, detections, params):
        roi = params.get("roi_polygon")
        road_km = params.get("road_length_km", 0.1)
        pce_w = params.get("pce_weights", DEFAULT_PCE_WEIGHTS)
        lm = params.get("labels_map", {})
        out = frame.copy()

        if roi is None or len(detections) == 0:
            return AnalysisResult(out, {"total_pce": 0, "pce_density": 0, "status": "NORMAL", "method": self.slug})

        roi_np = np.array(roi, dtype=np.int32)
        total_pce, cls_counts, mask_list = 0.0, {}, []

        for i, bbox in enumerate(detections.xyxy):
            cx, cy = int((bbox[0]+bbox[2])/2), int((bbox[1]+bbox[3])/2)
            inside = cv2.pointPolygonTest(roi_np, (cx, cy), False) >= 0
            mask_list.append(inside)
            if inside:
                cn = lm.get(int(detections.class_id[i]), "unknown")
                total_pce += pce_w.get(cn, 1.0)
                cls_counts[cn] = cls_counts.get(cn, 0) + 1

        det_roi = detections[np.array(mask_list)]
        labels = [f"{lm.get(int(c),'?')} PCE:{pce_w.get(lm.get(int(c),''),1.0)}" for c in det_roi.class_id]
        out = self._box_ann.annotate(scene=out, detections=det_roi)
        out = self._lbl_ann.annotate(scene=out, detections=det_roi, labels=labels)

        pce_d = total_pce / road_km if road_km > 0 else 0
        status = "TRAFFIC JAM" if pce_d >= THRESHOLD_JAM else "HEAVY" if pce_d >= THRESHOLD_HEAVY else "NORMAL"
        sc = (0,0,255) if pce_d >= THRESHOLD_JAM else (0,165,255) if pce_d >= THRESHOLD_HEAVY else (0,255,0)

        overlay = out.copy()
        cv2.fillPoly(overlay, [roi_np], sc)
        cv2.addWeighted(overlay, 0.2, out, 0.8, 0, out)
        cv2.polylines(out, [roi_np], True, sc, 2)

        cv2.rectangle(out, (10,10), (460,110), (0,0,0), -1)
        cv2.putText(out, f"PCE: {total_pce:.1f}  Density: {pce_d:.0f} PCE/km", (20,45), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
        cv2.putText(out, f"Status: {status}", (20,85), cv2.FONT_HERSHEY_SIMPLEX, 0.7, sc, 2)

        return AnalysisResult(out, {"total_pce": round(total_pce,2), "pce_density": round(pce_d,1), "status": status, "class_counts": cls_counts, "method": self.slug})
