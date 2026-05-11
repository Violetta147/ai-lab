# 02 — Backend Architecture (FastAPI)

The backend is a layered FastAPI application at `c2_center/backend/app/`.

## Composition Root

`main.py` wires everything at import time via `wire_live_pipeline()`.

```mermaid
flowchart TD
    subgraph MAIN ["main.py — Composition Root"]
        LIFESPAN["lifespan()\nstart/stop pipeline"]
        WIRE["wire_live_pipeline()\npipelines/live_monitoring.py"]
    end

    subgraph RUNTIME ["Runtime Layer"]
        SE["SyncEngine\nsync_engine.py"]
        PM["PipelineManager\npipeline_manager.py"]
        AD["AnalyticsDispatcher\nanalytics_dispatcher.py"]
        SM["StreamManager\nstream_manager.py"]
    end

    subgraph INFRA ["Infrastructure Layer"]
        VR["RtspVideoReader\nvideo/rtsp_reader.py"]
        KC["KafkaConsumerService\nkafka/consumer.py"]
        CR["CameraRepository\ndatabase/camera_repository.py"]
        ZR["ZoneRepository\ndatabase/zone_repository.py"]
        MR["ModelRegistry\nmodels/registry.py"]
        ENC["JPEG Encoder\nencoding/jpeg.py"]
    end

    subgraph ANALYTICS ["Analytics Plugin System"]
        REG["AnalyticsRegistry\nregistry.py"]
        P1["heatmap.py"]
        P2["absolute_count.py"]
        P3["line_crossing.py"]
        P4["pce_density.py"]
        P5["area_occupancy.py"]
        P6["fundamental_equation.py"]
    end

    subgraph TRANSPORT ["WebSocket Transport"]
        WS["WsStreamer\nws/streamer.py"]
        WSV["/ws/stream/ID — Base64 JPEG"]
        WSS["/ws/stats/ID — JSON 2Hz"]
    end

    subgraph API ["REST API Routes"]
        R1["/api/cameras — CRUD"]
        R2["/api/streams — status"]
        R3["/api/zones — ROI config"]
        R4["/api/analytics — switch algo"]
        R5["/api/models — list/activate"]
        R6["/api/playground — offline"]
        R7["/api/mediamtx — deploy config"]
    end

    WIRE --> VR & KC & SE & AD & PM & SM
    SE --> VR & KC
    PM --> SE & AD
    PM --> WS
    WS --> WSV & WSS
    AD --> REG
    REG --> P1 & P2 & P3 & P4 & P5 & P6
```

---

## Runtime Layer — Processing Loop

Each stream gets its own `asyncio.Task` inside `PipelineManager._loop()`:

```mermaid
flowchart LR
    A["SyncEngine\nget_synced_frame()"] --> B["metadata_to_detections()\nconvert JSON → sv.Detections"]
    B --> C["AnalyticsDispatcher\n.run(stream, frame, dets, params)"]
    C --> D["Active Plugin\ne.g. HeatmapAnalyzer"]
    D --> E["AnalysisResult\n(annotated_frame, metrics)"]
    E --> F["emit_frame → WsStreamer"]
    E --> G["emit_stats → WsStreamer (2Hz)"]
```

### SyncEngine Details

| Feature | Implementation |
|---------|---------------|
| **Drift Correction** | EMA offset `α=0.05`: `offset = (1-α)*offset + α*(meta_ts - frame_ts)` |
| **Anti-flicker Hold** | Re-use last detections for `0.5s` if no new Kafka match |
| **Matching Strategy** | `pop_nearest(stream_id, target_ts, tolerance_ms)` — one-pass closest timestamp |

---

## Analytics Plugin System

Plugins are auto-discovered from `app/analytics/plugins/` via `registry.discover()`.

| Slug | Mode | Requires Tracker | Requires Zones | Geometry |
|------|------|:-:|:-:|----------|
| `heatmap` | live | ✗ | ✗ | none |
| `absolute_count` | live | ✗ | ✔ | polygon |
| `line_crossing` | live | ✔ | ✔ | dual_line |
| `area_occupancy` | live | ✗ | ✔ | polygon |
| `pce_density` | offline | ✗ | ✔ | polygon |
| `fundamental_equation` | offline | ✔ | ✔ | dual_line |

---

## Infrastructure Components

| Component | File | Description |
|-----------|------|-------------|
| `RtspVideoReader` | `video/rtsp_reader.py` | Threaded OpenCV reader, one thread per stream |
| `KafkaConsumerService` | `kafka/consumer.py` | aiokafka consumer, in-memory buffer per stream, `pop_nearest()` |
| `CameraRepository` | `database/camera_repository.py` | SQLite CRUD for camera configs (`c2_cameras.db`) |
| `ZoneRepository` | `database/zone_repository.py` | In-memory dict for ROI/line zones per stream |
| `ModelRegistry` | `models/registry.py` | Scans `.pt`/`.onnx` files, tracks active model + labels |
| `JPEG Encoder` | `encoding/jpeg.py` | `frame_to_base64()` — OpenCV imencode → base64 for WS |
