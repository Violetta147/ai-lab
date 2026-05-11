# 03 — Frontend Architecture (React + Vite)

React SPA at `c2_center/frontend/`, built with Vite.

## Page & Component Tree

```mermaid
flowchart TD
    subgraph APP ["App.jsx — Tab Router"]
        direction TB
        GV["GridView.jsx\n📺 Live multi-stream grid"]
        CM["CameraManagement.jsx\n📷 Add/Edit/Delete cameras"]
        DA["DeepAnalysis.jsx\n📊 Algorithm selector + ROI drawing"]
        MP["ModelPlayground.jsx\n🧪 Offline video analysis"]
    end

    subgraph COMPONENTS ["Shared Components"]
        SC["StreamCard.jsx\nSingle stream viewer"]
        DC["DetectionControls.jsx\nFilter/threshold controls"]
        PD["PolygonDrawer.jsx\nCanvas ROI polygon editor"]
        TC["TrafficChart.jsx\nLive metrics chart"]
        FDZ["FileDropZone.jsx\nVideo upload drag-and-drop"]
    end

    GV --> SC
    DA --> PD & DC & TC
    MP --> FDZ

    subgraph WS ["WebSocket Connections"]
        WSV["ws://host:8000/ws/stream/ID\nBase64 JPEG frames"]
        WSS["ws://host:8000/ws/stats/ID\nJSON metrics at 2Hz"]
    end

    subgraph REST ["REST API Calls"]
        RCAM["GET/POST/PUT/DELETE /api/cameras"]
        RANAL["POST /api/analytics/switch"]
        RZONE["POST /api/zones/stream_id"]
        RPLAY["POST /api/playground/analyze"]
        RMOD["GET /api/models"]
    end

    SC -- "frame subscription" --> WSV
    TC -- "stats subscription" --> WSS
    CM --> RCAM
    DA --> RANAL & RZONE
    MP --> RPLAY & RMOD
```

---

## Page Details

### GridView (`pages/GridView.jsx`)
- Renders a responsive grid of `StreamCard` components.
- One WebSocket per visible stream for live video.

### CameraManagement (`pages/CameraManagement.jsx`)
- Full CRUD UI for camera records stored in SQLite.
- Fields: `stream_id`, `rtsp_url`, `name`, `description`, `enabled`.
- On add/enable: calls `POST /api/cameras` → backend calls `pipeline.add_stream()`.

### DeepAnalysis (`pages/DeepAnalysis.jsx`)
- **Algorithm Selector**: Dropdown populated from `GET /api/analytics` → registry slugs.
- **ROI Drawing**: `PolygonDrawer` lets user draw polygon/lines on the canvas.
- **Live Metrics**: `TrafficChart` shows real-time analytics from `/ws/stats/ID`.
- **Controls**: `DetectionControls` for confidence thresholds, class filters.

### ModelPlayground (`pages/ModelPlayground.jsx`)
- Upload video via `FileDropZone` → `POST /api/playground/analyze`.
- Select model from `GET /api/models`.
- Choose analytics algorithm (live + offline modes available).
- Renders processed video result with detection overlays.

---

## Communication Protocols

| Protocol | Endpoint | Direction | Payload |
|----------|----------|-----------|---------|
| WebSocket | `/ws/stream/{id}` | Server → Client | `{type: "frame", data: "<base64 JPEG>"}` |
| WebSocket | `/ws/stats/{id}` | Server → Client | `{type: "stats", data: {vehicle_count, ...}}` |
| REST | `/api/cameras` | Bidirectional | Camera CRUD JSON |
| REST | `/api/analytics/switch` | Client → Server | `{stream_id, algorithm}` |
| REST | `/api/zones/{id}` | Client → Server | `{roi_polygon, entry_line, exit_line}` |
| REST | `/api/playground/analyze` | Client → Server | `multipart/form-data (video + params)` |
