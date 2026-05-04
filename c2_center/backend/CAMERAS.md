# Camera Management System

The C2 Center Backend now supports **dynamic camera management** without requiring code changes or restarts.

## Overview

- **SQLite Database**: Cameras are stored in `c2_cameras.db`
- **REST API**: Add, list, update, and delete cameras on-the-fly
- **Dynamic Streaming**: New cameras are added without backend restart; live video appears only when an RTSP publisher is actually sending frames
- **Persistent Configuration**: All camera settings survive restarts

## Database Schema

```sql
CREATE TABLE cameras (
    stream_id TEXT PRIMARY KEY,
    rtsp_url TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
```

## API Endpoints

### List All Cameras
```bash
GET /api/cameras
GET /api/cameras?enabled_only=true
```

**Response:**
```json
{
  "count": 2,
  "cameras": [
    {
      "stream_id": "stream_1",
      "rtsp_url": "rtsp://localhost:8554/cam1",
      "name": "Camera 1",
      "description": "Simulated camera 1 (MediaMTX)",
      "enabled": true,
      "created_at": "2026-05-04T15:00:00",
      "updated_at": "2026-05-04T15:00:00"
    }
  ]
}
```

### Add a New Camera
```bash
POST /api/cameras
```

**Request Body:**
```json
{
  "stream_id": "stream_3",
  "rtsp_url": "rtsp://192.168.1.100:554/stream",
  "name": "Parking Lot",
  "description": "Main entrance",
  "enabled": true
}
```

**Response:**
```json
{
  "status": "created",
  "camera": { ... }
}
```

### Get Camera Details
```bash
GET /api/cameras/stream_1
```

### Update Camera
```bash
PUT /api/cameras/stream_1
```

**Request Body (all fields optional):**
```json
{
  "name": "Updated Name",
  "rtsp_url": "rtsp://new-ip:554/path",
  "description": "New description",
  "enabled": false
}
```

### Delete Camera
```bash
DELETE /api/cameras/stream_1
```

## Default Cameras

On first startup, if the database is empty, the backend seeds two default cameras:
- `stream_1` → `rtsp://localhost:8554/cam1` (Camera 1)
- `stream_2` → `rtsp://localhost:8554/cam2` (Camera 2)

These match the MediaMTX RTSP paths used by any publisher feeding the configured RTSP endpoint.

## Usage Examples

### Add a new camera dynamically
```bash
curl -X POST http://localhost:8000/api/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "stream_id": "parking_camera",
    "rtsp_url": "rtsp://192.168.1.50:554/stream",
    "name": "Parking Lot",
    "enabled": true
  }'
```

### Disable a camera (stops streaming)
```bash
curl -X PUT http://localhost:8000/api/cameras/stream_1 \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

### Update RTSP URL
```bash
curl -X PUT http://localhost:8000/api/cameras/stream_1 \
  -H "Content-Type: application/json" \
  -d '{"rtsp_url": "rtsp://new-ip:8554/cam1"}'
```

### Delete a camera
```bash
curl -X DELETE http://localhost:8000/api/cameras/parking_camera
```

### Backend Integration

### Automatic Stream Management
- **Adding**: When you `POST /api/cameras`, the camera is stored immediately
- **Updating**: Changing `rtsp_url` or toggling `enabled` updates the stored camera record
- **Removing**: `DELETE` or disabling removes the camera from the active set

### WebSocket Availability
Once a camera is added, its streams are immediately available via:
- `ws://localhost:8000/ws/stream/{stream_id}` — Live video
- `ws://localhost:8000/ws/stats/{stream_id}` — Analytics metrics

## No Code Changes Required

**Before:** Adding a camera required editing `config.py` and restarting the backend.

**Now:** Simply `POST` to `/api/cameras` — the backend handles camera persistence, and MediaMTX config can be deployed from that database.

## Database Location

The SQLite database is stored at:
```
d:\datas\Final.yolov8\c2_center\backend\c2_cameras.db
```

To reset or start fresh, delete the `.db` file. On next startup, defaults will be reseeded.
