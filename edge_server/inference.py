from __future__ import annotations

import queue
import time
import base64

import cv2
from paho.mqtt import client as mqtt_client
from ultralytics import YOLO

from .active_learning import ActiveLearningFilter, PublishGate, RuleBasedOodFilter
from .buffer_store import (
    build_detection_metadata,
    build_image_name,
    publish_detection,
    publish_video_frame,
)
from .config import ACTIVE_LEARNING_CONF_MIN, ACTIVE_LEARNING_ENABLED, CONFIDENCE_THRESHOLD, LIVE_MQTT_TOPIC
from .logger import log


def process_and_send(
    frame: cv2.typing.MatLike,
    model: YOLO,
    ram_queue: queue.Queue,
    mqtt_client_instance: mqtt_client.Client,
    camera_id: str,
    active_learning_filter: ActiveLearningFilter,
    publish_gate: PublishGate,
    rule_ood_filter: RuleBasedOodFilter,
) -> None:
    # 1. Thiết lập ngưỡng Confidence
    inference_confidence_threshold = CONFIDENCE_THRESHOLD
    if ACTIVE_LEARNING_ENABLED:
        inference_confidence_threshold = min(CONFIDENCE_THRESHOLD, ACTIVE_LEARNING_CONF_MIN)

    # 2. Chạy Model Inference
    results = model(frame, conf=inference_confidence_threshold)
    # Gom tất cả Box từ tất cả các result (trong trường hợp xử lý batch, dù YOLO frame-by-frame thường là 1 result)
    detections_list = []
    rule_ood_hit = False
    rule_ood_reason = "Rule OOD disabled"
    al_hit = False
    al_reason = "Clear"
    save_reason = "Normal data"
    
    for result in results:
        boxes = result.boxes
        
        for box in boxes:
            b = box.xyxy[0].tolist() # [x1, y1, x2, y2]
            detections_list.append({
                "class": model.names[int(box.cls[0])],
                "conf": float(box.conf[0]),
                "bbox": [int(b[0]), int(b[1]), int(b[2]), int(b[3])]
            })
            
        if len(boxes) == 0:
            continue

        # 3. Chạy các bộ lọc (Rule OOD, Active Learning)
        if ACTIVE_LEARNING_ENABLED:
            rule_ood_hit, rule_ood_reason = rule_ood_filter.should_flag_ood(result)
            al_hit, al_reason = active_learning_filter.should_save_frame(frame, result)

    # 4. Gửi Live Telemetry (Tọa độ) và Live Video (Ảnh nén)
    # BẮT BUỘC gửi mọi frame, kể cả frame không có xe để web UI hiển thị video liên tục!
    metadata = {
        "camera_id": camera_id,
        "image_url": build_image_name("raw", camera_id), # Not actually used for live, but required by schema
        "timestamp": time.time(),
        "trigger_reason": "live_stream",
        "detections": detections_list
    }

    try:
        publish_detection(mqtt_client_instance, metadata, LIVE_MQTT_TOPIC)
        # Nén và publish video frame
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
        b64_img = base64.b64encode(buffer).decode('utf-8')
        publish_video_frame(mqtt_client_instance, camera_id, time.time(), b64_img)
    except Exception as exc:
        log(f"❌ Live publish failed: {exc}")

    # 5. Nếu frame có anomaly, đưa vào Queue cho Active Learning / OOD (Luồng 2 xử lý)
    if al_hit or rule_ood_hit:
        # Kiểm tra Publish Gate (Tần suất gửi ảnh)
        should_publish, gate_reason = publish_gate.should_publish(frame)
        if should_publish:
            save_reason = f"{al_reason} | {rule_ood_reason} | {gate_reason}"
            log(f"🚀 Active learning accepted frame: {save_reason}")
            
            # Cập nhật metadata với lý do lưu thực tế
            metadata["trigger_reason"] = save_reason
            
            try:
                ram_queue.put_nowait({"frame": frame, "metadata": metadata})
                log(f"📦 Pushed to RAM queue. Queue size: {ram_queue.qsize()}")
            except queue.Full:
                log("⚠️ RAM Queue FULL! Dropped frame to protect memory.")
        else:
            log(f"Skipped frame due to publish gate: {gate_reason}")


