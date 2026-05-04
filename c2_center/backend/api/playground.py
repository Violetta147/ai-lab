"""C2 Center — Playground API (offline detection on uploaded files)."""

import base64
import asyncio

import cv2
import numpy as np
import supervision as sv
from fastapi import APIRouter, File, Form, UploadFile, HTTPException

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/playground", tags=["playground"])


def _normalize_01(value: float, default: float) -> float:
    """Normalize incoming numeric control values to [0,1].

    Accepts either normalized floats (0.0-1.0) or percentage-like values (0-100).
    """
    try:
        v = float(value)
    except Exception:
        return default
    if v > 1.0:
        v = v / 100.0
    return max(0.0, min(1.0, v))


def _apply_overlap_nms(detections: sv.Detections, overlap: float) -> sv.Detections:
    """Apply an explicit class-agnostic NMS pass using the overlap slider value.

    This guarantees that the playground overlap control has deterministic impact,
    independent of model-side NMS implementation details.
    """
    if len(detections) == 0:
        return detections

    if detections.confidence is None:
        return detections

    boxes_xyxy = detections.xyxy
    scores = detections.confidence.astype(float).tolist()

    boxes_xywh = []
    for box in boxes_xyxy:
        x1, y1, x2, y2 = [float(v) for v in box]
        boxes_xywh.append([x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1)])

    indices = cv2.dnn.NMSBoxes(
        bboxes=boxes_xywh,
        scores=scores,
        score_threshold=0.0,
        nms_threshold=float(overlap),
    )

    if indices is None or len(indices) == 0:
        return detections[[]]

    keep = []
    for idx in indices:
        if isinstance(idx, (list, tuple, np.ndarray)):
            keep.append(int(idx[0]))
        else:
            keep.append(int(idx))

    return detections[np.array(keep, dtype=int)]


def get_router(model_registry):
    @router.post("/detect")
    async def detect(
        file: UploadFile = File(...),
        confidence: float = Form(0.25),
        overlap: float = Form(0.45),
        opacity: float = Form(0.6),
        class_filter: str = Form(None),
        draw_confidence: bool = Form(True),
        draw_labels: bool = Form(True),
        draw_boxes: bool = Form(True),
        censor: bool = Form(False),
    ):
        active_model_name = model_registry.active_model_name
        # If no active model is set, attempt to auto-select the first available model.
        if active_model_name is None:
            models = model_registry.list_models()
            if models:
                # Set the first discovered model as active and load it.
                model_registry.active_model_name = models[0].name
                active_model_name = model_registry.active_model_name
            else:
                raise HTTPException(400, "No active model. Upload one to backend/models/")

        model = model_registry.get_active_model()
        if model is None:
            # Fallback to lazy-load the selected model if the cache is cold.
            model = model_registry.get_model(active_model_name)

        # Read uploaded file
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            raise HTTPException(400, "Could not decode image")

        confidence = _normalize_01(confidence, 0.25)
        iou_threshold = _normalize_01(overlap, 0.45)
        opacity = _normalize_01(opacity, 0.6)

        # Prepare classes filter for YOLO (None or list[int])
        classes_arg = None
        resolved_class_filter = "all"
        class_filter_value = "" if class_filter is None else str(class_filter).strip()
        if class_filter_value.lower() not in ("all", "all classes", ""):
            # Try numeric class id first
            try:
                class_id = int(class_filter_value)
                classes_arg = [class_id]
                resolved_class_filter = str(class_id)
            except Exception:
                # Treat class_filter as label name; map to class id using model registry
                try:
                    labels = model_registry.get_labels(active_model_name)
                    # Exact match first, then case-insensitive
                    if class_filter_value in labels:
                        class_id = labels.index(class_filter_value)
                        classes_arg = [class_id]
                        resolved_class_filter = str(class_id)
                    else:
                        lower_labels = [l.lower() for l in labels]
                        lowered = class_filter_value.lower()
                        if lowered in lower_labels:
                            class_id = lower_labels.index(lowered)
                            classes_arg = [class_id]
                            resolved_class_filter = str(class_id)
                except Exception:
                    classes_arg = None
                    resolved_class_filter = "all"

        logger.info(
            "Playground detect request: conf=%s iou=%s class_filter=%s resolved=%s draw_boxes=%s draw_labels=%s draw_confidence=%s opacity=%s",
            confidence,
            iou_threshold,
            class_filter,
            resolved_class_filter,
            draw_boxes,
            draw_labels,
            draw_confidence,
            opacity,
        )

        # Run inference in thread pool
        def _infer():
            # Pass classes list to YOLO if provided
            predict_kwargs = {
                "conf": float(confidence),
                # Keep model-side NMS permissive; overlap control is applied
                # explicitly below for deterministic UI behavior.
                "iou": 0.99,
                "agnostic_nms": True,
                "verbose": False,
            }
            # Always send classes explicitly so "all" does not inherit
            # class filters from previous requests.
            predict_kwargs["classes"] = classes_arg

            logger.info("Playground predict kwargs: %s", predict_kwargs)

            results = model.predict(image, **predict_kwargs)[0]
            detections = sv.Detections.from_ultralytics(results)
            before_nms_count = len(detections)
            detections = _apply_overlap_nms(detections, iou_threshold)
            after_nms_count = len(detections)
            out = image.copy()

            if censor:
                for bbox in detections.xyxy:
                    x1, y1, x2, y2 = map(int, bbox)
                    roi = out[y1:y2, x1:x2]
                    if roi.size > 0:
                        out[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (51, 51), 30)
            else:
                # Create an overlay to draw annotations with opacity
                overlay = out.copy()

                if draw_boxes:
                    ann = sv.BoxAnnotator(thickness=2, color_lookup=sv.ColorLookup.CLASS)
                    overlay = ann.annotate(scene=overlay, detections=detections)

                if draw_labels or draw_confidence:
                    labels = []
                    for i in range(len(detections)):
                        parts = []
                        if draw_labels:
                            cls_name = results.names.get(int(detections.class_id[i]), "?")
                            parts.append(cls_name)
                        if draw_confidence and detections.confidence is not None:
                            parts.append(f"{detections.confidence[i]:.0%}")
                        labels.append(" ".join(parts))
                    lbl_ann = sv.LabelAnnotator(text_scale=0.5, text_thickness=1)
                    overlay = lbl_ann.annotate(scene=overlay, detections=detections, labels=labels)

                # Blend overlay with original output using opacity
                try:
                    cv2.addWeighted(overlay, float(opacity), out, 1.0 - float(opacity), 0, out)
                except Exception:
                    # On failure, fallback to overlay
                    out = overlay

            _, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 90])
            class_counts = {}
            if detections.class_id is not None:
                for cls in detections.class_id:
                    cid = int(cls)
                    class_counts[cid] = class_counts.get(cid, 0) + 1

            return (
                base64.b64encode(buf).decode("utf-8"),
                len(detections),
                before_nms_count,
                after_nms_count,
                class_counts,
            )

        b64, count, before_nms_count, after_nms_count, class_counts = await asyncio.to_thread(_infer)

        return {
            "image": b64,
            "detections_count": count,
            "model": active_model_name,
            "used_iou": iou_threshold,
            "used_confidence": confidence,
            "used_opacity": opacity,
            "resolved_class_filter": resolved_class_filter,
            "before_nms_count": before_nms_count,
            "after_nms_count": after_nms_count,
            "class_counts": class_counts,
        }

    return router
