from __future__ import annotations

import cv2
from minio import Minio
from paho.mqtt import client as mqtt_client
from ultralytics import YOLO

from .active_learning import (
    ActiveLearningConfig,
    ActiveLearningFilter,
    PublishGate,
    PublishGateConfig,
    RuleBasedOodFilter,
    RuleOodConfig,
)
from .config import (
    ACTIVE_LEARNING_CONF_MAX,
    ACTIVE_LEARNING_CONF_MIN,
    ACTIVE_LEARNING_MAX_BRIGHTNESS,
    ACTIVE_LEARNING_MIN_BLUR,
    ACTIVE_LEARNING_MIN_BRIGHTNESS,
    CAMERA_ID,
    CAMERA_INDEX,
    FRAME_DEDUP_PHASH_DISTANCE_MAX,
    MAX_UPLOADS_PER_WINDOW,
    MODEL_PATH,
    PUBLISH_COOLDOWN_SECONDS,
    PUBLISH_WINDOW_SECONDS,
    RULE_OOD_BUS_VERTICAL_RATIO_MIN,
    RULE_OOD_CLASS_ASPECT_RATIO_LIMITS,
    RULE_OOD_EDGE_TOUCH_MIN_AREA_RATIO,
    RULE_OOD_EDGE_TOUCH_MIN_EDGES,
    RULE_OOD_ENABLED,
    RULE_OOD_EXTREME_AREA_MAX_RATIO,
    RULE_OOD_FORBIDDEN_CLASSES,
    RULE_OOD_PERSISTENCE_MIN_HITS,
    RULE_OOD_PERSISTENCE_WINDOW_FRAMES,
    RULE_OOD_SCORE_ASPECT_RATIO,
    RULE_OOD_SCORE_BUS_VERTICAL,
    RULE_OOD_SCORE_EDGE_TOUCH,
    RULE_OOD_SCORE_EXTREME_AREA,
    RULE_OOD_SCORE_FORBIDDEN_CLASS,
    RULE_OOD_SCORE_THRESHOLD,
    RULE_OOD_SCORE_TOP_ZONE_VEHICLE,
    RULE_OOD_VEHICLE_TOP_ZONE_MAX_Y,
    USE_VIDEO_SOURCE,
    VIDEO_PATH,
)
from .buffer_store import sync_buffer_to_server
from .inference import process_and_send
from .logger import log
from .minio_client import create_minio_client
from .mqtt_client import create_mqtt_client


def main() -> None:
    minio_client: Minio = create_minio_client()
    mqtt_client_instance: mqtt_client.Client = create_mqtt_client(CAMERA_ID)
    model = YOLO(MODEL_PATH)
    active_learning_filter = ActiveLearningFilter(
        ActiveLearningConfig(
            conf_min=ACTIVE_LEARNING_CONF_MIN,
            conf_max=ACTIVE_LEARNING_CONF_MAX,
            min_brightness=ACTIVE_LEARNING_MIN_BRIGHTNESS,
            max_brightness=ACTIVE_LEARNING_MAX_BRIGHTNESS,
            min_blur=ACTIVE_LEARNING_MIN_BLUR,
        )
    )
    publish_gate = PublishGate(
        PublishGateConfig(
            publish_cooldown_seconds=PUBLISH_COOLDOWN_SECONDS,
            publish_window_seconds=PUBLISH_WINDOW_SECONDS,
            max_uploads_per_window=MAX_UPLOADS_PER_WINDOW,
            frame_dedup_phash_distance_max=FRAME_DEDUP_PHASH_DISTANCE_MAX,
        )
    )
    rule_ood_filter = RuleBasedOodFilter(
        RuleOodConfig(
            enabled=RULE_OOD_ENABLED,
            vehicle_top_zone_max_y=RULE_OOD_VEHICLE_TOP_ZONE_MAX_Y,
            extreme_area_max_ratio=RULE_OOD_EXTREME_AREA_MAX_RATIO,
            bus_vertical_ratio_min=RULE_OOD_BUS_VERTICAL_RATIO_MIN,
            edge_touch_min_edges=RULE_OOD_EDGE_TOUCH_MIN_EDGES,
            edge_touch_min_area_ratio=RULE_OOD_EDGE_TOUCH_MIN_AREA_RATIO,
            forbidden_classes=RULE_OOD_FORBIDDEN_CLASSES,
            class_aspect_ratio_limits=RULE_OOD_CLASS_ASPECT_RATIO_LIMITS,
            persistence_window_frames=RULE_OOD_PERSISTENCE_WINDOW_FRAMES,
            persistence_min_hits=RULE_OOD_PERSISTENCE_MIN_HITS,
            score_threshold=RULE_OOD_SCORE_THRESHOLD,
            score_forbidden_class=RULE_OOD_SCORE_FORBIDDEN_CLASS,
            score_extreme_area=RULE_OOD_SCORE_EXTREME_AREA,
            score_bus_vertical=RULE_OOD_SCORE_BUS_VERTICAL,
            score_aspect_ratio=RULE_OOD_SCORE_ASPECT_RATIO,
            score_top_zone_vehicle=RULE_OOD_SCORE_TOP_ZONE_VEHICLE,
            score_edge_touch=RULE_OOD_SCORE_EDGE_TOUCH,
        )
    )

    video_source: str | int = VIDEO_PATH if USE_VIDEO_SOURCE else CAMERA_INDEX
    capture = cv2.VideoCapture(video_source)
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open source: {video_source}")

    log(f"Start processing loop. source={video_source}")
    try:
        from .ota_updater import ota_manager
        while capture.isOpened():
            if ota_manager.model_needs_reload:
                log("🔄 OTA Update: Hot-reloading AI Model...")
                model = YOLO(ota_manager.active_model_path)
                ota_manager.model_needs_reload = False
                log("✅ OTA Update: Hot-reload complete. Resuming inference.")
                
            ok, frame = capture.read()
            if not ok:
                log("Reached end of stream or failed to read frame.")
                break

            sync_buffer_to_server(
                minio_client=minio_client,
                mqtt_client_instance=mqtt_client_instance,
                camera_id=CAMERA_ID,
            )
            process_and_send(
                frame=frame,
                model=model,
                minio_client=minio_client,
                mqtt_client_instance=mqtt_client_instance,
                camera_id=CAMERA_ID,
                active_learning_filter=active_learning_filter,
                publish_gate=publish_gate,
                rule_ood_filter=rule_ood_filter,
            )
    finally:
        capture.release()
        mqtt_client_instance.loop_stop()
        mqtt_client_instance.disconnect()
        log("Shutdown complete.")


if __name__ == "__main__":
    main()

