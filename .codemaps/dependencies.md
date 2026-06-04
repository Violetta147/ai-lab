<!-- Generated: 2026-06-05 | Files scanned: ~50 | Token estimate: ~250 -->

# External Dependencies

## Infrastructure
- **MQTT Broker (Eclipse Mosquitto)**: High-throughput metadata transit. Topics include `traffic/detections`, `traffic/tracked`.
- **MinIO**: S3-compatible local object storage for Edge detection frames.
- **PostgreSQL**: Relational data store for offline tracking and state management.
- **Redis & Celery**: Background task queueing (e.g., CVAT integration tasks).

## Computer Vision
- **YOLOv8**: Running on Edge nodes (Jetson) for raw box extraction.
- **CVAT**: Computer Vision Annotation Tool instance used for automated data-loop labeling.

## Key Python Packages
- `paho-mqtt` (MQTT client)
- `minio` (S3 interactions)
- `psycopg2-binary` (PostgreSQL driver)
- `fastapi` & `uvicorn` (C2 Center API)
