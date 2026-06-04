<!-- Generated: 2026-06-05 | Files scanned: ~50 | Token estimate: ~600 -->

# Backend Services & Pipelines

## C2 Center Backend (FastAPI)

### Routes & Pipelines
RTSP stream processing & WebSocket emission.
`app/pipelines/live_monitoring.py` (Wires up the RTSP Reader, MQTT Consumer, and Sync Engine)

### Core Components
`app/runtime/sync_engine.py` (Fuses video frame + metadata with a latest-to-latest strategy. ~180 lines)
`app/infrastructure/mqtt/consumer.py` (Consumes tracking data for the Sync Engine. ~100 lines)

---

## Data Pipeline (Background Processing)

### Services
`python -m pipeline.services.tracking_bridge` → Subscribes to `traffic/detections`, applies `IouTracker`, publishes to `traffic/tracked`.

### Key Files
`pipeline/utils/iou_tracker.py` (Greedy IoU matching, `PerCameraTracker`, 160 lines)
`pipeline/utils/db_handler.py` (PostgreSQL interface for edge detections, 139 lines)
`pipeline/utils/mqtt_handler.py` (MQTT client for parsing edge payloads and storing them, 66 lines)
