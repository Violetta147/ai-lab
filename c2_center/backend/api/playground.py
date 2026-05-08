"""C2 Center — Playground API (offline detection on uploaded files)."""

import base64
import asyncio

import cv2
import tempfile
import os
import platform
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


def _create_video_writer(base_path: str, fps: float, width: int, height: int):
    """Create a browser-compatible video writer, trying multiple codecs/containers."""
    system_name = platform.system().lower()
    if system_name == "windows":
        # Avoid OpenH264 dependency issues on Windows builds that bundle incompatible DLLs.
        candidates = [
            (".mp4", "mp4v", "video/mp4"),
            (".mp4", "avc1", "video/mp4"),
            (".webm", "VP80", "video/webm"),
        ]
    else:
        candidates = [
            (".mp4", "avc1", "video/mp4"),
            (".mp4", "H264", "video/mp4"),
            (".webm", "VP80", "video/webm"),
            (".mp4", "mp4v", "video/mp4"),
        ]

    for ext, codec, mime in candidates:
        out_path = f"{base_path}.out{ext}"
        fourcc = cv2.VideoWriter_fourcc(*codec)
        writer = cv2.VideoWriter(out_path, fourcc, float(fps), (int(width), int(height)))
        if writer is not None and writer.isOpened():
            logger.info("Playground video writer selected codec=%s path=%s", codec, out_path)
            return writer, out_path, mime
        logger.warning("Playground video writer failed codec=%s path=%s", codec, out_path)
        try:
            writer.release()
        except Exception:
            pass

    return None, None, None


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
        try:
            return await _detect_impl(
                file, confidence, overlap, opacity, class_filter,
                draw_confidence, draw_labels, draw_boxes, censor
            )
        except Exception as e:
            logger.exception("Playground detect endpoint error: %s", e)
            raise HTTPException(500, f"Playground error: {str(e)}")

    async def _detect_impl(
        file: UploadFile,
        confidence: float,
        overlap: float,
        opacity: float,
        class_filter: str,
        draw_confidence: bool,
        draw_labels: bool,
        draw_boxes: bool,
        censor: bool,
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

        # If decoding as image failed, attempt to treat upload as a video
        is_video = False
        temp_input_path = None
        if image is None:
            is_video = True
            # Persist upload to a temporary file and open with VideoCapture
            suffix = os.path.splitext(file.filename)[1] or ".mp4"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
                tf.write(contents)
                temp_input_path = tf.name
            cap = cv2.VideoCapture(temp_input_path)
            if not cap.isOpened():
                # Cleanup
                try:
                    os.unlink(temp_input_path)
                except Exception:
                    pass
                raise HTTPException(400, "Could not open uploaded video file")

        confidence = _normalize_01(confidence, 0.25)
        iou_threshold = _normalize_01(overlap, 0.45)
        opacity = _normalize_01(opacity, 0.6)

        # Prepare classes filter for YOLO (None or list[int])
        class_filter_list = None
        resolved_class_filter = "all"
        class_filter_value = "" if class_filter is None else str(class_filter).strip()
        if class_filter_value.lower() not in ("all", "all classes", ""):
            # Try numeric class id first
            try:
                class_id = int(class_filter_value)
                class_filter_list = [class_id]
                resolved_class_filter = str(class_id)
            except Exception:
                # Treat class_filter as label name; map to class id using model registry
                try:
                    labels = model_registry.get_labels(active_model_name)
                    # Exact match first, then case-insensitive
                    if class_filter_value in labels:
                        class_id = labels.index(class_filter_value)
                        class_filter_list = [class_id]
                        resolved_class_filter = str(class_id)
                    else:
                        lower_labels = [l.lower() for l in labels]
                        lowered = class_filter_value.lower()
                        if lowered in lower_labels:
                            class_id = lower_labels.index(lowered)
                            class_filter_list = [class_id]
                            resolved_class_filter = str(class_id)
                except Exception:
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

            # If this is a single image, run the existing image path
            if not is_video:
                # Note: YOLO's predict() 'iou' parameter may not apply NMS correctly in some versions.
                # We apply NMS manually using OpenCV's built-in function.
                results = model.predict(image, conf=confidence, classes=class_filter_list, verbose=False)[0]
                detections = sv.Detections.from_ultralytics(results)

                logger.info("Detection results BEFORE manual NMS: %d boxes (conf=%s)", 
                           len(detections), confidence)

                # Apply NMS manually using OpenCV if there are detections
                if len(detections) > 0:
                    boxes = detections.xyxy.astype(np.float32)
                    scores = detections.confidence

                    # Convert xyxy to xywh format for NMS
                    boxes_xywh = []
                    for x1, y1, x2, y2 in boxes:
                        w = x2 - x1
                        h = y2 - y1
                        boxes_xywh.append([x1, y1, w, h])

                    # Apply NMS per class
                    keep_indices = []
                    for class_id in np.unique(detections.class_id):
                        class_mask = detections.class_id == class_id
                        class_indices = np.where(class_mask)[0]
                        class_boxes = [boxes_xywh[i] for i in class_indices]
                        class_scores = scores[class_indices].tolist()

                        if len(class_boxes) > 0:
                            # Use OpenCV NMS
                            nms_indices = cv2.dnn.NMSBoxes(class_boxes, class_scores, 0.0, iou_threshold)
                            nms_indices = nms_indices.flatten().tolist() if len(nms_indices) > 0 else []
                            # Map back to global indices
                            keep_indices.extend([class_indices[i] for i in nms_indices])

                    # Filter detections to keep only NMS-approved boxes
                    keep_indices = sorted(keep_indices)
                    if len(keep_indices) > 0:
                        detections = detections[np.array(keep_indices)]
                    else:
                        detections = sv.Detections.empty()

                    logger.info("Detection results AFTER manual NMS: %d boxes (iou=%s)", 
                               len(detections), iou_threshold)

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
                return base64.b64encode(buf).decode("utf-8"), len(detections), None

            # Video processing path: decode frames, run inference per frame, write annotated video
            max_frames = 300  # Safety cap to avoid excessive processing
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            if not fps or fps <= 1e-3:
                fps = 25.0

            # Prime one frame so dimensions are always valid and writer can be created reliably.
            first_ret, first_frame = cap.read()
            if not first_ret or first_frame is None:
                return "", 0, "video/mp4"

            height, width = first_frame.shape[:2]
            writer, out_path, video_mime = _create_video_writer(temp_input_path, fps, width, height)
            if writer is None:
                logger.error("Playground video writer could not be opened for any codec")
                return "", 0, "video/mp4"

            frames_written = 0
            try:
                # Process primed first frame then continue with remaining frames.
                pending_frame = first_frame
                while frames_written < max_frames:
                    if pending_frame is not None:
                        frame = pending_frame
                        pending_frame = None
                    else:
                        ret, frame = cap.read()
                        if not ret:
                            break

                    # Inference
                    results = model.predict(frame, conf=confidence, classes=class_filter_list, verbose=False)[0]
                    detections = sv.Detections.from_ultralytics(results)

                    # Manual NMS (same as image path)
                    if len(detections) > 0:
                        boxes = detections.xyxy.astype(np.float32)
                        scores = detections.confidence
                        boxes_xywh = []
                        for x1, y1, x2, y2 in boxes:
                            w = x2 - x1
                            h = y2 - y1
                            boxes_xywh.append([x1, y1, w, h])

                        keep_indices = []
                        for class_id in np.unique(detections.class_id):
                            class_mask = detections.class_id == class_id
                            class_indices = np.where(class_mask)[0]
                            class_boxes = [boxes_xywh[i] for i in class_indices]
                            class_scores = scores[class_indices].tolist()
                            if len(class_boxes) > 0:
                                nms_indices = cv2.dnn.NMSBoxes(class_boxes, class_scores, 0.0, iou_threshold)
                                nms_indices = nms_indices.flatten().tolist() if len(nms_indices) > 0 else []
                                keep_indices.extend([class_indices[i] for i in nms_indices])

                        keep_indices = sorted(keep_indices)
                        if len(keep_indices) > 0:
                            detections = detections[np.array(keep_indices)]
                        else:
                            detections = sv.Detections.empty()

                    # Annotate frame
                    out_frame = frame.copy()
                    if censor:
                        for bbox in detections.xyxy:
                            x1, y1, x2, y2 = map(int, bbox)
                            roi = out_frame[y1:y2, x1:x2]
                            if roi.size > 0:
                                out_frame[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (51, 51), 30)
                    else:
                        overlay = out_frame.copy()
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
                        try:
                            cv2.addWeighted(overlay, float(opacity), out_frame, 1.0 - float(opacity), 0, out_frame)
                        except Exception:
                            out_frame = overlay

                    writer.write(out_frame)
                    frames_written += 1

            finally:
                try:
                    writer.release()
                except Exception:
                    pass
                try:
                    cap.release()
                except Exception:
                    pass

            # Read output video and cleanup
            try:
                file_size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
                logger.info("Playground video file size: %d bytes", file_size)
                if file_size < 100:
                    logger.warning("Playground video file suspiciously small, may be incomplete")
                    return "", 0, "video/mp4"
                    
                with open(out_path, "rb") as f:
                    data = f.read()
                
                logger.info("Playground video read: %d bytes from %s", len(data), out_path)
                b64_video = base64.b64encode(data).decode("utf-8")
                logger.info("Playground video encoded to base64: %d chars", len(b64_video))
            except Exception as e:
                logger.exception("Playground video file read/encode failed: %s", e)
                b64_video = ""
                video_mime = "video/mp4"

            # Cleanup temporary files
            try:
                if os.path.exists(out_path):
                    os.unlink(out_path)
                if os.path.exists(temp_input_path):
                    os.unlink(temp_input_path)
            except Exception:
                pass

            return b64_video, frames_written, video_mime

        b64, count, video_mime = await asyncio.to_thread(_infer)

        if is_video:
            response_obj = {
                "video": b64,
                "video_mime": video_mime,
                "frames_processed": count,
                "model": active_model_name,
                "used_iou": iou_threshold,
                "used_confidence": confidence,
                "used_opacity": opacity,
                "resolved_class_filter": resolved_class_filter,
            }
            logger.info("Playground returning video response: video_size=%d video_mime=%s frames=%d",
                       len(b64) if b64 else 0, video_mime, count)
            return response_obj
        else:
            response_obj = {
                "image": b64,
                "detections_count": count,
                "model": active_model_name,
                "used_iou": iou_threshold,
                "used_confidence": confidence,
                "used_opacity": opacity,
                "resolved_class_filter": resolved_class_filter,
            }
            logger.info("Playground returning image response: image_size=%d detections=%d",
                       len(b64) if b64 else 0, count)
            return response_obj

    return router
