# 04 — End-to-End Data Flow

Complete sequence from camera capture to dashboard rendering.

## Sequence Diagram

```mermaid
sequenceDiagram
    participant CAM as 🎥 IP Camera
    participant FF as FFmpeg
    participant MTX as MediaMTX :8554
    participant JET as Jetson Nano
    participant KAF as Kafka :9092
    participant VR as RtspVideoReader
    participant KC as KafkaConsumer
    participant SE as SyncEngine
    participant PM as PipelineManager
    participant AD as AnalyticsDispatcher
    participant WS as WsStreamer
    participant FE as React Frontend

    Note over CAM,MTX: ① Video Ingestion
    CAM->>FF: Raw RTSP stream
    FF->>MTX: Publish to /cam path

    Note over MTX,JET: ② Dual Fan-Out
    MTX->>JET: RTSP pull (DeepStream source0)
    MTX->>VR: RTSP pull (threaded OpenCV)

    Note over JET,KAF: ③ Edge Inference
    JET->>JET: streammux → YOLO → NvDCF Tracker → ROI Filter
    JET->>KAF: Type 257 JSON via libnvds_kafka_proto.so

    Note over KC,SE: ④ Synchronization
    KAF->>KC: Consume c2_metadata topic
    VR->>SE: get_frame(stream_id) → (frame, timestamp)
    KC->>SE: pop_nearest(stream_id, target_ts, tolerance)
    SE->>SE: Apply drift correction (EMA α=0.05)
    SE->>SE: Anti-flicker hold (0.5s TTL)

    Note over PM,AD: ⑤ Analytics Processing
    SE->>PM: synced (frame, detections)
    PM->>AD: run(stream_id, frame, sv.Detections, params)
    AD->>AD: Execute active plugin (e.g. heatmap)
    AD->>PM: AnalysisResult(annotated_frame, metrics)

    Note over WS,FE: ⑥ Dashboard Delivery
    PM->>WS: on_frame(stream_id, annotated_frame, metrics)
    PM->>WS: on_stats(stream_id, metrics) — every 0.5s
    WS->>FE: WebSocket /ws/stream/ID (Base64 JPEG)
    WS->>FE: WebSocket /ws/stats/ID (JSON)
```

---

## Data Transformation Pipeline

```
Camera (H.264/RTSP)
  │
  ├──→ MediaMTX ──→ Jetson Nano
  │                    │
  │                    ├─ streammux (resize 640×640)
  │                    ├─ primary-gie (YOLO FP16, batch=1)
  │                    ├─ tracker (NvDCF 640×384)
  │                    ├─ nvds-analytics (ROI polygon filter)
  │                    ├─ nvmsgconv (Type 257 → JSON)
  │                    └─ sink0 → Kafka "c2_metadata"
  │                         │
  │                         │  JSON payload:
  │                         │  {timestamp, source_id, objects: [{class_id, label,
  │                         │   confidence, tracker_id, bbox, roi_status}]}
  │                         │
  │                         ▼
  │                    KafkaConsumer.pop_nearest()
  │                         │
  ├──→ MediaMTX ──→ RtspVideoReader.get_frame()
  │                         │
  │                         ▼
  │                    SyncEngine
  │                    ├─ Match frame_ts ↔ meta_ts (±tolerance)
  │                    ├─ Drift correction: offset = EMA(meta_ts - frame_ts)
  │                    └─ Anti-flicker: hold last detections for 0.5s
  │                         │
  │                         ▼
  │                    metadata_to_detections()
  │                    JSON objects → sv.Detections (supervision library)
  │                         │
  │                         ▼
  │                    AnalyticsDispatcher.run()
  │                    ├─ Load zone params (ROI polygon, lines)
  │                    ├─ Scale ROI to actual frame resolution
  │                    └─ Execute active plugin
  │                         │
  │                         ▼
  │                    AnalysisResult
  │                    ├─ annotated_frame (numpy array with overlays)
  │                    └─ metrics {vehicle_count, occupancy, ...}
  │                         │
  │                         ▼
  │                    WsStreamer
  │                    ├─ frame_to_base64(frame, quality=70)
  │                    ├─ /ws/stream/ID → {type:"frame", data:"<b64>"}
  │                    └─ /ws/stats/ID  → {type:"stats", data:{...}}  @2Hz
  │                         │
  │                         ▼
  │                    React Frontend
  │                    ├─ StreamCard: render base64 → <img>
  │                    └─ TrafficChart: plot metrics live
```

---

## Network Topology

```
┌──────────────────────────────────────────────────┐
│  Laptop A (172.16.1.162)                         │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ MediaMTX │  │  Kafka   │  │ FastAPI :8000  │  │
│  │  :8554   │  │  :9092   │  │  + React :5173 │  │
│  └────┬─────┘  └────┬─────┘  └───────┬───────┘  │
│       │              │                │          │
└───────┼──────────────┼────────────────┼──────────┘
        │              │                │
        │  LAN (192.168.1.x / 172.16.1.x)
        │              │                │
┌───────┼──────────────┼────────────────┘
│       ▼              ▼
│  ┌─────────────────────────┐
│  │ Jetson Nano             │
│  │ 192.168.1.14            │
│  │                         │
│  │ DeepStream 6.0          │
│  │ RTSP in  ← :8554       │
│  │ RTSP out → :8555        │
│  │ Kafka out → :9092       │
│  └─────────────────────────┘
│
│  ┌─────────┐  ┌─────────┐
│  │ Camera 1│  │ Camera 2│  ...
│  └─────────┘  └─────────┘
```
