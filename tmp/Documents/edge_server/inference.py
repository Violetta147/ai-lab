from __future__ import annotations

import time

import cv2
from minio import Minio
from paho.mqtt import client as mqtt_client
from ultralytics import YOLO

from .active_learning import ActiveLearningFilter, PublishGate, RuleBasedOodFilter
from .buffer_store import (
    build_detection_metadata,
    build_image_name,
    publish_detection,
    save_metadata_to_buffer,
    save_frame_to_buffer,
    upload_buffer_file,
)
from .config import ACTIVE_LEARNING_CONF_MIN, ACTIVE_LEARNING_ENABLED, CONFIDENCE_THRESHOLD
from .logger import log


def process_and_send(
    frame: cv2.typing.MatLike,
    model: YOLO,
    minio_client: Minio,
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
    
    for result in results:
        boxes = result.boxes
        if len(boxes) == 0:
            continue

        # 3. Chạy các bộ lọc (Rule OOD, Active Learning)
        rule_ood_hit = False
        rule_ood_reason = "Rule OOD disabled"
        if ACTIVE_LEARNING_ENABLED:
            rule_ood_hit, rule_ood_reason = rule_ood_filter.should_flag_ood(result)

        al_hit = False
        al_reason = "Clear"
        if ACTIVE_LEARNING_ENABLED:
            al_hit, al_reason = active_learning_filter.should_save_frame(frame, result)
            
            # Nếu cả 2 bộ lọc đều không báo động thì bỏ qua
            if not al_hit and not rule_ood_hit:
                # log("Skipped frame: Normal data.")
                continue

        # 4. Kiểm tra Publish Gate (Tần suất gửi ảnh)
        should_publish, gate_reason = publish_gate.should_publish(frame)
        if not should_publish:
            log(f"Skipped frame due to publish gate: {gate_reason}")
            continue

        # 5. Tổng hợp lý do gửi ảnh
        save_reason = f"{al_reason} | {rule_ood_reason} | {gate_reason}"
        log(f"🚀 Active learning accepted frame: {save_reason}")

        # 6. Chuẩn bị ảnh và dữ liệu nhãn
        raw_image_name = build_image_name("raw", camera_id)
        
        # Gom tất cả các Box vào 1 danh sách
        detections_list = []
        for box in boxes:
            b = box.xyxy[0].tolist() # [x1, y1, x2, y2]
            detections_list.append({
                "class": model.names[int(box.cls[0])],
                "conf": float(box.conf[0]),
                "bbox": [int(b[0]), int(b[1]), int(b[2]), int(b[3])]
            })

        # 7. Lưu tạm ảnh vào Buffer và upload lên MinIO
        raw_local_path = save_frame_to_buffer(frame, raw_image_name)
        raw_uploaded = upload_buffer_file(minio_client, raw_local_path, raw_image_name)

        if raw_uploaded:
            # 8. Tạo Metadata JSON tổng hợp (Theo định dạng Server yêu cầu)
            metadata = {
                "camera_id": camera_id,
                "image_url": raw_image_name, # Key quan trọng để Server tải ảnh
                "timestamp": time.time(),
                "trigger_reason": save_reason,
                "detections": detections_list # Mảng chứa toàn bộ vật thể
            }
            
            try:
                # Gửi tin nhắn duy nhất qua MQTT
                publish_detection(mqtt_client_instance, metadata)
                log(f"✅ Successfully published {len(detections_list)} detections for {raw_image_name}")
            except Exception as exc:
                # Nếu mất mạng, lưu JSON vào buffer để gửi lại sau
                save_metadata_to_buffer(camera_id, metadata)
                log(f"❌ Live publish failed, metadata buffered: {exc}")
        else:
            log(f"❌ Failed to upload image {raw_image_name}, skipping MQTT.")


