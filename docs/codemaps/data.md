<!-- Generated: 2026-06-05 | Files scanned: ~15 | Token estimate: ~200 -->
# Data Flow & Storage

## Data Stores

### 1. Edge Local Buffer (`./buffer`)
- High-speed temporary local storage cache (SD Card / eMMC).
- Hard limit of `500MB` (controlled by `LOCAL_DISK_SAFETY_LIMIT_MB`).
- Stores raw frames (`.jpg`) and metadata (`.json`) temporarily before MinIO sync.

### 2. MinIO S3 (Remote Storage)
- Stores full resolution frames for Active Learning and Out-Of-Distribution (OOD) hits.

### 3. PostgreSQL
- Stores persistent metadata, user preferences, and historical event logs for the web application.

## Pipelines
**Live Feed Pipeline**: Camera → YOLO Inference → MQTT Publish (`traffic/live_tracking` / `traffic/live_video`) → C2 Center SyncEngine.
**Offline/Batch Pipeline**: Camera → YOLO Inference → AL/OOD Gate → Local Buffer → MinIO Upload → C2 Server Processing.
