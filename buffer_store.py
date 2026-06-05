from __future__ import annotations

import json
import os
import time
import uuid
from typing import TypedDict

import cv2
from minio import Minio
from paho.mqtt import client as mqtt_client

from .config import (
    BUFFER_MESSAGE_PUBLISH_INTERVAL_SECONDS,
    CAMERA_ID,
    LOCAL_BUFFER_DIR,
    MAX_BUFFER_MESSAGES_PER_CYCLE,
    MAX_SYNC_FILES_PER_CYCLE,
    MQTT_QOS,
    MQTT_PUBLISH_WAIT_TIMEOUT_SECONDS,
    MQTT_TOPIC,
    MINIO_BUCKET,
)
from .logger import log


class DetectionMetadata(TypedDict):
    camera_id: str
    raw_image_url: str
    predicted_image_url: str
    image_url: str
    raw_image_name: str
    predicted_image_name: str
    class_id: int
    confidence: float
    timestamp: float
    trigger_reason: str


def ensure_local_buffer_dir() -> None:
    if os.path.exists(LOCAL_BUFFER_DIR):
        return
    os.makedirs(LOCAL_BUFFER_DIR)
    log(f"Created local buffer directory: {LOCAL_BUFFER_DIR}")


def build_image_name(image_kind: str, camera_id: str) -> str:
    image_uuid = str(uuid.uuid4())
    return f"{camera_id}_{image_kind}_{image_uuid}.jpg"


def build_buffer_file_path(image_name: str) -> str:
    return os.path.join(LOCAL_BUFFER_DIR, image_name)


def build_metadata_name(camera_id: str) -> str:
    metadata_uuid = str(uuid.uuid4())
    return f"{camera_id}_metadata_{metadata_uuid}.json"


def save_metadata_to_buffer(camera_id: str, metadata: DetectionMetadata) -> str:
    metadata_name = build_metadata_name(camera_id)
    metadata_path = build_buffer_file_path(metadata_name)
    with open(metadata_path, "w", encoding="utf-8") as metadata_file:
        json.dump(metadata, metadata_file)
    log(f"Saved metadata to local buffer: {metadata_path}")
    return metadata_path


def build_detection_metadata(
    raw_image_name: str,
    detections: list,
    trigger_reason: str,
) -> dict:
    return {
        "camera_id": CAMERA_ID,
        "image_url": raw_image_name, # Server dùng cái này để tải từ MinIO
        "timestamp": time.time(),
        "trigger_reason": trigger_reason,
        "detections": detections # Danh sách các box
    }


def save_frame_to_buffer(frame: cv2.typing.MatLike, image_name: str) -> str:
    local_path = build_buffer_file_path(image_name)
    if not cv2.imwrite(local_path, frame):
        raise RuntimeError(f"Failed to write local buffer file: {local_path}")
    log(f"Saved image to local buffer: {local_path}")
    return local_path


def upload_buffer_file(minio_client: Minio, local_path: str, object_name: str) -> bool:
    try:
        minio_client.fput_object(MINIO_BUCKET, object_name, local_path)
    except Exception as exc:
        log(f"Failed to upload buffered image {object_name}: {exc}")
        return False

    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Buffered file was not found: {local_path}")

    # Remove only after successful upload.
    os.remove(local_path)
    log(f"Uploaded and removed buffered image: {MINIO_BUCKET}/{object_name}")
    return True


def publish_detection(
    mqtt_client_instance: mqtt_client.Client,
    metadata: DetectionMetadata,
) -> None:
    payload = dict(metadata)
    payload.pop("raw_image_name", None)
    payload.pop("predicted_image_name", None)

    result = mqtt_client_instance.publish(
        MQTT_TOPIC,
        json.dumps(payload),
        qos=MQTT_QOS,
    )
    if result.rc != 0:
        raise RuntimeError(f"Failed to publish MQTT message, rc={result.rc}")

    result.wait_for_publish(timeout=MQTT_PUBLISH_WAIT_TIMEOUT_SECONDS)
    if not result.is_published():
        raise TimeoutError(
            f"MQTT publish did not receive PUBACK in {MQTT_PUBLISH_WAIT_TIMEOUT_SECONDS} seconds."
        )


def sync_buffer_to_server(
    minio_client: Minio,
    mqtt_client_instance: mqtt_client.Client,
    camera_id: str,
) -> None:
    ensure_local_buffer_dir()
    buffered_files = os.listdir(LOCAL_BUFFER_DIR)
    if len(buffered_files) == 0:
        return

    image_files = [name for name in buffered_files if name.endswith(".jpg")]
    synced_count = 0
    synced_or_tried_count = 0
    for filename in image_files:
        local_path = build_buffer_file_path(filename)
        if not os.path.isfile(local_path):
            continue
        if synced_or_tried_count >= MAX_SYNC_FILES_PER_CYCLE:
            break

        upload_success = upload_buffer_file(minio_client, local_path, filename)
        synced_or_tried_count += 1
        if upload_success:
            synced_count += 1
            continue
        # Stop early on first failure so infer loop is not delayed.
        break

    metadata_published_count = 0
    metadata_tried_count = 0
    refreshed_files = os.listdir(LOCAL_BUFFER_DIR)
    refreshed_metadata_files = [name for name in refreshed_files if name.endswith(".json")]
    for metadata_filename in refreshed_metadata_files:
        if metadata_tried_count >= MAX_BUFFER_MESSAGES_PER_CYCLE:
            break

        metadata_path = build_buffer_file_path(metadata_filename)
        if not os.path.isfile(metadata_path):
            continue

        with open(metadata_path, "r", encoding="utf-8") as metadata_file:
            metadata = json.load(metadata_file)

        raw_image_name = str(metadata["raw_image_name"])
        predicted_image_name = str(metadata["predicted_image_name"])
        raw_local_path = build_buffer_file_path(raw_image_name)
        predicted_local_path = build_buffer_file_path(predicted_image_name)
        if os.path.exists(raw_local_path) or os.path.exists(predicted_local_path):
            continue

        try:
            typed_metadata: DetectionMetadata = {
                "camera_id": str(metadata["camera_id"]),
                "raw_image_url": str(metadata["raw_image_url"]),
                "predicted_image_url": str(metadata["predicted_image_url"]),
                "image_url": str(metadata["image_url"]),
                "raw_image_name": str(metadata["raw_image_name"]),
                "predicted_image_name": str(metadata["predicted_image_name"]),
                "class_id": int(metadata["class_id"]),
                "confidence": float(metadata["confidence"]),
                "timestamp": float(metadata["timestamp"]),
                "trigger_reason": str(metadata["trigger_reason"]),
            }
            publish_detection(mqtt_client_instance, typed_metadata)
        except Exception as exc:
            log(f"Failed to publish buffered metadata {metadata_filename}: {exc}")
            metadata_tried_count += 1
            break

        os.remove(metadata_path)
        metadata_tried_count += 1
        metadata_published_count += 1
        log(f"Published and removed buffered metadata: {metadata_filename}")
        time.sleep(BUFFER_MESSAGE_PUBLISH_INTERVAL_SECONDS)

    pending_count = len(os.listdir(LOCAL_BUFFER_DIR))
    log(
        "Buffer sync result: "
        f"images_synced={synced_count}, images_tried={synced_or_tried_count}, "
        f"metadata_published={metadata_published_count}, metadata_tried={metadata_tried_count}, "
        f"pending={pending_count}"
    )

