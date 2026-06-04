<!-- Generated: 2026-06-05 | Files scanned: ~50 | Token estimate: ~300 -->
# Project Architecture

## High-Level Flow
Edge Server (Jetson Nano) → MQTT / MinIO → C2 Center (Backend)

## Key Components

### 1. Edge Server (`edge_server/`)
- **Main Loop** (`inference.py`): Runs YOLO detection, pushes lightweight JSON telemtry to `traffic/live_tracking` and video to `traffic/live_video` via MQTT.
- **Disk Writer** (`threads.py`): Background thread writing raw frames to `./buffer` while protecting the 500MB local disk limit.
- **Background Sync** (`threads.py`): Periodically uploads buffered data to MinIO.

### 2. C2 Center Backend (`c2_center/backend/app/`)
- **SyncEngine** (`runtime/sync_engine.py`): Decoupled synchronizer matching video frames with AI metadata via exact timestamp logic.
- **Adapters** (`infrastructure/mqtt/`): `MqttVideoAdapter` and `MqttMetadataAdapter` ingest live data stream conforming to `VideoReaderProtocol` and `MetadataReaderProtocol`.

## Dependencies
- **MQTT Broker**: Used for low-latency live telemetry.
- **MinIO S3**: Used for reliable batch image uploads (Active Learning & OOD cases).
- **YOLOv8**: Core inference engine on Edge.
