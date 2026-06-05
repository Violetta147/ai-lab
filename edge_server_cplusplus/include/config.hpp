#pragma once

#include <string>
#include <vector>
#include <tuple>

namespace edge {
namespace config {

// Active Learning
inline constexpr bool ACTIVE_LEARNING_ENABLED = true;
inline constexpr float ACTIVE_LEARNING_CONF_MIN = 0.3f;
inline constexpr float ACTIVE_LEARNING_CONF_MAX = 0.8f;
inline constexpr float ACTIVE_LEARNING_MIN_BRIGHTNESS = 40.0f;
inline constexpr float ACTIVE_LEARNING_MAX_BRIGHTNESS = 240.0f;
inline constexpr float ACTIVE_LEARNING_MIN_BLUR = 50.0f;

// Inference
inline constexpr float CONFIDENCE_THRESHOLD = 0.5f;
inline constexpr int INFERENCE_INTERVAL_MS = 100; // e.g. 100ms = 10 FPS

// General
inline constexpr const char* CAMERA_ID = "cam_01";
inline constexpr const char* MODEL_PATH = "../models/yolov8n.transd.engine";
inline constexpr bool USE_VIDEO_SOURCE = true;
inline constexpr const char* VIDEO_PATH = "rtsp://192.168.1.29:8554/cam_01"; // Update to your exact stream URL if different

// MQTT
inline constexpr const char* MQTT_BROKER = "192.168.1.29";
inline constexpr int MQTT_PORT = 1883;
inline constexpr const char* LIVE_TRACKING_TOPIC = "traffic/live_tracking";
inline constexpr const char* LIVE_VIDEO_TOPIC = "traffic/live_video";
inline constexpr const char* METADATA_TOPIC = "traffic/metadata";

// MinIO
inline constexpr const char* MINIO_BUCKET = "raw-images";

// Publish Gate
inline constexpr float PUBLISH_COOLDOWN_SECONDS = 1.0f;
inline constexpr float PUBLISH_WINDOW_SECONDS = 60.0f;
inline constexpr int MAX_UPLOADS_PER_WINDOW = 30;
inline constexpr int FRAME_DEDUP_PHASH_DISTANCE_MAX = 10;

// Rule OOD
inline constexpr bool RULE_OOD_ENABLED = true;
inline constexpr float RULE_OOD_VEHICLE_TOP_ZONE_MAX_Y = 0.3f;
inline constexpr float RULE_OOD_EXTREME_AREA_MAX_RATIO = 0.8f;
inline constexpr float RULE_OOD_BUS_VERTICAL_RATIO_MIN = 1.2f;
inline constexpr int RULE_OOD_EDGE_TOUCH_MIN_EDGES = 2;
inline constexpr float RULE_OOD_EDGE_TOUCH_MIN_AREA_RATIO = 0.4f;
inline constexpr int RULE_OOD_PERSISTENCE_WINDOW_FRAMES = 10;
inline constexpr int RULE_OOD_PERSISTENCE_MIN_HITS = 3;
inline constexpr float RULE_OOD_SCORE_THRESHOLD = 1.0f;
inline constexpr float RULE_OOD_SCORE_FORBIDDEN_CLASS = 1.0f;
inline constexpr float RULE_OOD_SCORE_EXTREME_AREA = 1.0f;
inline constexpr float RULE_OOD_SCORE_BUS_VERTICAL = 1.0f;
inline constexpr float RULE_OOD_SCORE_ASPECT_RATIO = 1.0f;
inline constexpr float RULE_OOD_SCORE_TOP_ZONE_VEHICLE = 1.0f;
inline constexpr float RULE_OOD_SCORE_EDGE_TOUCH = 1.0f;

} // namespace config
} // namespace edge
