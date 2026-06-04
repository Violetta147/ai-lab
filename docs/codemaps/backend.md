<!-- Generated: 2026-06-05 | Files scanned: ~20 | Token estimate: ~250 -->
# Backend Architecture (C2 Center)

## SyncEngine Core
`SyncEngine` (`app/runtime/sync_engine.py`, 130 lines) is the heart of the video/metadata alignment logic.
It implements Duck Typing using `typing.Protocol` for:
- `VideoReaderProtocol`
- `MetadataReaderProtocol`

## Infrastructure Adapters
- `MqttVideoAdapter` (`app/infrastructure/mqtt/mqtt_video_adapter.py`, 65 lines): Subscribes to `traffic/live_video`, decodes base64 OpenCV arrays, and caches the latest frames per stream.
- `MqttMetadataAdapter` (`app/infrastructure/mqtt/mqtt_metadata_adapter.py`, 60 lines): Queues up AI detection JSON payloads from `traffic/live_tracking`.

## External Services
- S3 / MinIO
- PostgreSQL (Primary Data Store)
