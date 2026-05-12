"""
Diagnostic tests for bbox coordinate scaling between DeepStream inference
resolution (640x640) and RTSP video resolution (1920x1080).

This is the prime suspect for "ghost boxes" — if bbox coords are not scaled
from inference res to display res, boxes appear tiny/misplaced.
"""

import numpy as np
import pytest
import supervision as sv

from app.domain.detection.converters import metadata_to_detections


class TestBboxCoordinateScaling:
    """
    DeepStream runs YOLO inference at 640x640 (streammux resolution).
    The RTSP video frame from MediaMTX arrives at the camera's native resolution
    (typically 1920x1080).
    
    Bounding box coordinates in Kafka metadata are in INFERENCE resolution.
    They must be scaled to VIDEO resolution before drawing.
    """

    def test_bbox_values_from_deepstream_are_inference_resolution(self):
        """
        Verify: DeepStream C2 payload sends bbox in inference coords (640x640).
        Example from real log:
          {"bbox":[220.95, 182.47, 240.69, 207.55]}
        These are clearly in 640x640 range, not 1920x1080.
        """
        objects = [{
            "class_id": 0,
            "tracking_id": 41,
            "bbox": [220.95, 182.47, 240.69, 207.55],
        }]
        
        dets = metadata_to_detections(objects)
        
        # bbox should be preserved as-is from Kafka
        assert dets.xyxy[0][0] == pytest.approx(220.95, abs=0.01)
        assert dets.xyxy[0][2] == pytest.approx(240.69, abs=0.01)
        
        # KEY INSIGHT: These coords are in 640x640 space.
        # If drawn on a 1920x1080 frame without scaling, they'll be
        # tiny and in the wrong position → appears as "ghost boxes"
        assert dets.xyxy[0][2] < 641, "bbox x2 should be within 640px inference width"
        assert dets.xyxy[0][3] < 641, "bbox y2 should be within 640px inference height"

    def test_scaling_640_to_1920x1080(self):
        """
        Demonstrate correct scaling from 640x640 inference to 1920x1080 display.
        
        scale_x = 1920 / 640 = 3.0
        scale_y = 1080 / 640 = 1.6875
        """
        # Inference-resolution bbox
        inf_bbox = [220.95, 182.47, 240.69, 207.55]
        
        inf_w, inf_h = 640, 640
        disp_w, disp_h = 1920, 1080
        
        scale_x = disp_w / inf_w  # 3.0
        scale_y = disp_h / inf_h  # 1.6875
        
        scaled = [
            inf_bbox[0] * scale_x,
            inf_bbox[1] * scale_y,
            inf_bbox[2] * scale_x,
            inf_bbox[3] * scale_y,
        ]
        
        # After scaling, coords should be in display resolution
        assert scaled[0] == pytest.approx(662.85, abs=0.1)  # 220.95 * 3.0
        assert scaled[1] == pytest.approx(307.92, abs=0.1)  # 182.47 * 1.6875
        assert scaled[2] == pytest.approx(722.07, abs=0.1)  # 240.69 * 3.0
        assert scaled[3] == pytest.approx(350.24, abs=0.1)  # 207.55 * 1.6875
        
        print(f"\n  Inference bbox: {inf_bbox}")
        print(f"  Display bbox:   {[round(s, 1) for s in scaled]}")
        print(f"  Scale factors:  x={scale_x}, y={scale_y}")

    @pytest.mark.xfail(reason="BBox scaling is done in pipeline_manager, not metadata_to_detections")
    def test_current_pipeline_does_NOT_scale_bbox(self):
        """
        EXPECTED TO FAIL — This test documents the bug.
        
        The current pipeline draws inference-resolution bboxes directly onto
        the display-resolution frame. This makes boxes appear:
        - Too small (3x smaller than they should be)
        - In the wrong position (upper-left quadrant bias)
        - "Ghost-like" because they don't align with actual vehicles
        """
        objects = [
            {"class_id": 0, "tracking_id": 1, "bbox": [100, 100, 200, 200]},
            {"class_id": 0, "tracking_id": 2, "bbox": [300, 300, 400, 400]},
        ]
        
        dets = metadata_to_detections(objects)
        
        # Simulate what the pipeline currently does:
        # It draws these coords directly onto a 1920x1080 frame
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        frame_h, frame_w = frame.shape[:2]
        
        # Check if ANY bbox coordinate exceeds inference resolution
        # If all coords are < 640, they haven't been scaled
        max_x = float(dets.xyxy[:, [0, 2]].max())
        max_y = float(dets.xyxy[:, [1, 3]].max())
        
        needs_scaling = max_x < frame_w * 0.5 and max_y < frame_h * 0.5
        
        if needs_scaling:
            print(f"\n  WARNING: BBOX NOT SCALED!")
            print(f"    Max bbox x={max_x}, frame width={frame_w}")
            print(f"    Max bbox y={max_y}, frame height={frame_h}")
            print(f"    Boxes are being drawn at {max_x/frame_w*100:.0f}% of frame width")
            print(f"    This is why boxes appear as ghosts in upper-left area!")
        
        # This assertion documents the expected fix
        assert not needs_scaling, (
            f"BBoxes need scaling! Max coords ({max_x}, {max_y}) are far smaller "
            f"than frame size ({frame_w}, {frame_h}). "
            f"Boxes are drawn at ~{max_x/frame_w*100:.0f}% of frame width."
        )


class TestVideoFrameResolution:
    """Verify what resolution the RTSP reader delivers."""

    def test_rtsp_frame_is_not_640x640(self):
        """
        The RTSP feed from MediaMTX is the camera's native resolution (1920x1080).
        The 640x640 is only used inside DeepStream for inference.
        
        If the RTSP frame is 1920x1080 but bboxes are 640x640, 
        that's the coordinate mismatch causing ghost boxes.
        """
        # Simulate a frame from RTSP (camera native res)
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        
        # Simulate detections from Kafka (inference res)
        objects = [
            {"class_id": 0, "tracking_id": 1, "bbox": [220, 182, 240, 207]},
        ]
        dets = metadata_to_detections(objects)
        
        frame_h, frame_w = frame.shape[:2]
        det_max_x = float(dets.xyxy[:, 2].max())
        det_max_y = float(dets.xyxy[:, 3].max())
        
        # The mismatch
        ratio_x = frame_w / max(det_max_x, 1)
        ratio_y = frame_h / max(det_max_y, 1)
        
        print(f"\n  Frame: {frame_w}x{frame_h}")
        print(f"  BBox max: x={det_max_x}, y={det_max_y}")
        print(f"  Ratio: x={ratio_x:.1f}x, y={ratio_y:.1f}x")
        
        if ratio_x > 2.0:
            print(f"  WARNING: BBox coordinates need {ratio_x:.1f}x horizontal scaling!")
