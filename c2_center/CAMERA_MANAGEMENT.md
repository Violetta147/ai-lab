# Dynamic Camera Management System

Complete guide to adding, managing, and testing cameras in the C2 Center.

## Overview

The system now supports **fully dynamic camera management** without code changes or restarts:

1. **Backend API** — REST endpoints for camera CRUD operations
2. **SQLite Persistence** — Cameras persist across restarts
3. **Dynamic Publisher** — Reads cameras from API and manages RTSP streams
4. **Frontend UI** — Web interface for camera management
5. **Test Script** — Automated setup and testing

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Frontend (React)                                        │
│ ├─ Camera Management Tab (Add/Edit/Delete/Enable)     │
│ └─ Displays real-time camera status                    │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP REST API
                     ↓
┌─────────────────────────────────────────────────────────┐
│ Backend API (FastAPI)                                   │
│ ├─ /api/cameras (CRUD endpoints)                       │
│ ├─ SQLite database (c2_cameras.db)                     │
│ └─ Dynamic video reader integration                    │
└────────────────────┬────────────────────────────────────┘
                     │ Reads camera config
                     ↓
┌─────────────────────────────────────────────────────────┐
│ Dynamic Publisher (PowerShell)                          │
│ ├─ Polls backend for enabled cameras                   │
│ ├─ Starts FFmpeg processes for each                    │
│ └─ Auto-restarts on config changes                     │
└────────────────────┬────────────────────────────────────┘
                     │ FFmpeg RTSP streams
                     ↓
┌─────────────────────────────────────────────────────────┐
│ MediaMTX (RTSP Server)                                  │
│ ├─ Listens on :8554                                    │
│ └─ Serves multiple paths (cam1, cam2, etc.)           │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Start MediaMTX (RTSP Server)

```powershell
cd D:\datas\Final.yolov8\rstp\mediamtx_v1.17.1_windows_amd64
.\mediamtx.exe ..\..\c2_center\infrastructure\mediamtx.yml
```

### 2. Start Backend

```bash
cd D:\datas\Final.yolov8\c2_center\backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. Start Frontend

```bash
cd D:\datas\Final.yolov8\c2_center\frontend
npm run dev
# Open http://localhost:5173
```

### 4. Publisher is External

This workflow no longer includes a built-in FFmpeg launcher script.

- Register cameras in the backend
- Deploy `mediamtx.yml` from the backend
- Start your own external publisher if you need live RTSP input

## Frontend Camera Management

Navigate to **📷 Cameras** tab in the web interface.

### Add a Camera

1. Click **+ Add Camera**
2. Fill in:
   - **Stream ID**: Unique identifier (e.g., `parking_lot`)
   - **RTSP URL**: Source RTSP stream (e.g., `rtsp://192.168.1.100:554/stream`)
   - **Name**: Display name (e.g., `Parking Lot Camera`)
   - **Description**: Optional details
   - **Enabled**: Toggle to start/stop streaming
3. Click **Add Camera**

The publisher will automatically pick up the new camera and start streaming within 10 seconds.

### Edit Camera

Click **✎ Edit** on any camera card to modify:
- Name and description
- RTSP URL (will restart the stream)
- Enabled status

### Disable Camera

Click **⏸ Disable** to stop streaming without deleting the camera. The FFmpeg process stops but the configuration is preserved.

### Enable Camera

Click **▶ Enable** to resume streaming a disabled camera.

### Delete Camera

Click **🗑 Delete** to remove a camera completely. The publisher will stop the stream immediately.

## API Endpoints

### List Cameras

```bash
curl http://localhost:8000/api/cameras
curl http://localhost:8000/api/cameras?enabled_only=true  # Only active cameras
```

### Add Camera

```bash
curl -X POST http://localhost:8000/api/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "stream_id": "parking_lot",
    "rtsp_url": "rtsp://192.168.1.100:554/stream",
    "name": "Parking Lot",
    "description": "Main entrance",
    "enabled": true
  }'
```

### Get Camera Details

```bash
curl http://localhost:8000/api/cameras/parking_lot
```

### Update Camera

```bash
# Change name
curl -X PUT http://localhost:8000/api/cameras/parking_lot \
  -H "Content-Type: application/json" \
  -d '{"name": "Parking Lot - South"}'

# Disable camera (stops streaming)
curl -X PUT http://localhost:8000/api/cameras/parking_lot \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'

# Update RTSP URL (stream restarts)
curl -X PUT http://localhost:8000/api/cameras/parking_lot \
  -H "Content-Type: application/json" \
  -d '{"rtsp_url": "rtsp://192.168.1.50:554/new"}'
```

### Delete Camera

```bash
curl -X DELETE http://localhost:8000/api/cameras/parking_lot
```

## Publisher Flow

This version does **not** include a script to start FFmpeg publishers.

- Camera records live in the backend database.
- MediaMTX config is deployed from the backend based on those records.
- Live video appears only when an external publisher is pushing to the RTSP path.

If you need a publisher, run FFmpeg manually or use your own external process manager.

## Default Cameras

On first startup, if the database is empty, the backend creates:

| Stream ID | RTSP URL | Name |
|-----------|----------|------|
| `stream_1` | `rtsp://localhost:8554/cam1` | Camera 1 |
| `stream_2` | `rtsp://localhost:8554/cam2` | Camera 2 |

These match the MediaMTX paths configured in `mediamtx.yml`.

## Database

**Location:** `D:\datas\Final.yolov8\c2_center\backend\app\storage\sqlite\c2_cameras.db`

**Schema:**
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

**To reset:** Delete the `.db` file. On next backend start, defaults will be reseeded.

## Troubleshooting

### Camera streams not appearing in Grid View

- Ensure camera is enabled: check frontend status or API
- Check WebSocket connections: open browser DevTools → Network → WS
- Verify backend video reader has started threads for cameras

### Database locked error

- Another backend instance is running
- Delete `.db` file if corrupted (will reseed on next start)

## Advanced Usage

### Add Cameras Programmatically

```python
import requests

backend = "http://localhost:8000"

# Add camera
response = requests.post(f"{backend}/api/cameras", json={
    "stream_id": "camera_3",
    "rtsp_url": "rtsp://192.168.1.50:554/stream",
    "name": "Warehouse",
    "enabled": True
})
print(response.json())

# Disable camera
requests.put(f"{backend}/api/cameras/camera_3", json={"enabled": False})

# Delete camera
requests.delete(f"{backend}/api/cameras/camera_3")
```

### Monitor Camera Activity

```bash
# Watch camera list updates in real-time
watch -n 1 'curl -s http://localhost:8000/api/cameras | jq ".cameras[] | {stream_id, enabled, rtsp_url}"'
```

## Performance Tips

- **Resolution:** Use `640:640` or `1280:720` for YOLO models
- **Bitrate:** Use `2M` for most scenarios, increase for 4K sources
- **Frame Rate:** FFmpeg reads at native rate (`-re` flag)
- **Stream Count:** Test with 5-10 concurrent streams on typical hardware

## See Also

- [CAMERAS.md](./CAMERAS.md) — API documentation
- [Backend README](./backend/README.md) — Backend setup
- [Frontend README](./frontend/README.md) — Frontend setup
