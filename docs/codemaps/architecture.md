<!-- Generated: 2026-06-05 | Files scanned: ~40 | Token estimate: ~500 -->
# C++ Edge Server Architecture

## High-Level Data Flow
Camera/Video → YOLO TensorRT Engine → Filters (OOD/AL) → RAM Queue → Disk Buffer → Cloud Sync (MinIO/MQTT)

## Core Components
- **Inference (`src/infer/`)**: CUDA/TensorRT based YOLOv8 inference and ByteTrack object tracking.
- **Filters (`src/filters/`)**: Logic to detect anomalies, out-of-distribution events, and trigger Active Learning data collection.
- **Core Orchestration (`src/core/`)**: Thread-safe queues, disk writers, and background sync loops.
- **Clients (`src/clients/`)**: MQTT and MinIO wrappers for cloud communication.

## Key Files
- `edge_server_cplusplus/src/main.cpp` (Primary event loop and pipeline orchestration)
- `edge_server_cplusplus/include/config.hpp` (Centralized thresholds and environment config)

## Dependencies
- CUDA & TensorRT (`nvinfer`)
- OpenCV (Image processing)
- Paho MQTT (Telemetry)
- libcurl (MinIO uploads)
- nlohmann_json (Metadata serialization)
