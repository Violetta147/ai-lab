<!-- Generated: 2026-06-05 | Files scanned: ~10 | Token estimate: ~300 -->

# Data & Persistence

## PostgreSQL Database
Stores edge detection metadata for CVAT automation and offline training.

### Tables
- `detections` (or similar DB_TABLE defined in config)
  - `id` (Primary Key)
  - `camera_id` (Stream/Device identifier)
  - `image_url` (MinIO path to raw image)
  - `timestamp` (Event time)
  - `trigger_reason` (e.g., motion, scheduled)
  - `status` (NEW, IN_CVAT, etc.)
  - `cvat_task_id` (Link to external annotation task)
  - `edge_predictions` (JSONB raw bounding boxes)

## Object Storage (MinIO)
Stores images captured by edge devices and training dataset artifacts.

### Key Handlers
`pipeline/utils/minio_handler.py` (Handles bucket creation, uploading, string downloads)
