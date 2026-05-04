# C2 Surveillance Center - Quick Start Guide

## Two-Screen Workflow

### Screen 1: Camera Management (PowerShell)
**File**: `manage_cameras.ps1`  
**Purpose**: Add, edit, enable/disable, delete any cameras in the network.

```powershell
cd D:\datas\Final.yolov8\c2_center\infrastructure
.\manage_cameras.ps1
```

**Menu options**:
- `[1]` List all cameras (shows stream_id, RTSP URL, status)
- `[2]` Add new camera (enter stream_id, RTSP URL, name, description)
- `[3]` Edit camera (modify name, URL, or description)
- `[4]` Enable/Disable camera (toggle on/off without deleting)
- `[5]` Delete camera (permanent removal)
- `[6]` Start camera publishers (launch FFmpeg to stream video)
- `[0]` Exit

**Example**: Add a parking lot camera
```
Select option: 2
Stream ID: parking_lot_zone_1
RTSP URL: rtsp://192.168.1.100:554/stream
Display name: Parking Lot - Zone 1
Description: Main entrance
[OK] Camera added: parking_lot_zone_1
```

---

### Screen 2: Verification & Monitoring (Web Frontend)
**URL**: `http://localhost:5173`  
**Purpose**: Verify cameras are configured correctly and see live video.

1. Open **Cameras** tab — shows all cameras from database with their status
2. If "Heartbeat" confirms RTSP reachability, stream will appear as **[ON]**
3. Open **Grid View** tab — displays live video from all connected cameras
4. Optionally edit/delete cameras directly in the frontend (syncs to backend)

---

## Complete Startup Sequence

**Terminal 1 - MediaMTX (RTSP server)**
```powershell
cd D:\datas\Final.yolov8\rstp\mediamtx_v1.17.1_windows_amd64
.\mediamtx.exe ..\..\c2_center\infrastructure\mediamtx.yml
```

**Terminal 2 - Backend (FastAPI)**
```powershell
cd D:\datas\Final.yolov8\c2_center\backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Terminal 3 - Frontend (Vite dev server)**
```powershell
cd D:\datas\Final.yolov8\c2_center\frontend
npm run dev
```

**Terminal 4 - Camera Manager (your remote/office worker)**
```powershell
cd D:\datas\Final.yolov8\c2_center\infrastructure
.\manage_cameras.ps1
```

---

## Backend Architecture (How It Works)

```
┌─────────────────────────────────────────────────────────────┐
│ manage_cameras.ps1 (Screen 1)                               │
│ Worker adds/edits cameras via REST API                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
            POST /api/cameras/{id}
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Backend (main.py)                                           │
│  ├─ SQLite DB: Stores camera configs (stream_id, RTSP URL) │
│  ├─ HeartbeatMonitor: Checks RTSP reachability every 5s    │
│  │  └─> On success: add_stream() to video_reader           │
│  └─ VideoReaderService: Pulls frames via cv2 + threading   │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
    WebSocket    /api/cameras  /api/streams
      (frames)   (config)      (status)
         │           │           │
         └───────────┼───────────┘
                     ▼
        Frontend (http://localhost:5173)
         ├─ Cameras tab (Screen 2): Verify configs
         ├─ Grid View: Live video from all streams
         └─ Analytics: Per-stream stats
```

---

## Key Design Principles

- **One Source of Truth**: SQLite database (`c2_cameras.db`)
- **Heartbeat-Driven**: Backend only pulls frames after RTSP test succeeds
- **No Redundancy**: Camera added via manage_cameras.ps1 automatically appears in frontend
- **Clean Separation**: Script (management) → API (persistence) → Frontend (monitoring)

---

## Troubleshooting

**"Cannot reach backend" error**
- Check: Is `uvicorn main:app --port 8000` running?

**Camera shows [OFF] in frontend but added in Script**
- Heartbeat monitor runs every 5 seconds
- If RTSP URL is unreachable, it waits for next check
- Verify RTSP server (MediaMTX) is running and RTSP URL is correct

**No live video in Grid View**
- Open browser console (F12) for errors
- Check backend logs for stream connection status

**Want to test with fake video?**
- In manage_cameras.ps1 option [6], point to your test video file
- Publishers will loop that video to all configured RTSP paths
