# C2 Center — System Architecture Overview

High-level overview connecting all subsystems across the distributed C2 Surveillance Center.

```mermaid
flowchart TD
    subgraph EDGE ["🟢 EDGE — Jetson Nano (192.168.1.14)"]
        direction TB
        SRC["RTSP Source\nrtsp://LaptopA:8554/cam"]
        SM["streammux\n640×640, batch=1"]
        PGIE["primary-gie\nYOLO FP16, interval=1"]
        TRACKER["NvDCF Tracker\n640×384, past-frame=1"]
        ANALYTICS["nvds-analytics\nROI Polygon Filtering"]
        MSGCONV["nvmsgconv\nType 257 Custom JSON\nlibnvds_msgconv_c2.so"]
        KAFKASINK["sink0: Kafka\nlibnvds_kafka_proto.so"]
        RTSPSINK["sink1: RTSP Out\nport 8555, H.264"]

        SRC --> SM --> PGIE --> TRACKER --> ANALYTICS
        ANALYTICS --> MSGCONV --> KAFKASINK
        ANALYTICS --> RTSPSINK
    end

    subgraph INFRA ["🟡 INFRASTRUCTURE — Laptop A (172.16.1.162)"]
        direction TB
        CAMERAS["🎥 IP Cameras"]
        FFMPEG["FFmpeg Publisher\nmanage_cameras.ps1"]
        MEDIAMTX["MediaMTX\nRTSP Server :8554"]
        ZK["Zookeeper :2181"]
        KAFKA["Kafka Broker :9092\ntopic: c2_metadata"]
        ZK --> KAFKA
        CAMERAS --> FFMPEG --> MEDIAMTX
    end

    subgraph SERVER ["🔵 WEB SERVER — Laptop A"]
        direction TB
        VR["RtspVideoReader\nthreaded OpenCV"]
        KC["KafkaConsumer\npop_nearest()"]
        SYNC["SyncEngine\ndrift correction +\nanti-flicker hold"]
        PM["PipelineManager\nasyncio task/stream"]
        AD["AnalyticsDispatcher\nplugin routing"]
        WS["WsStreamer\nWebSocket broadcast"]
        FE["React Frontend\nVite :5173"]

        VR --> SYNC
        KC --> SYNC
        SYNC --> PM --> AD --> PM
        PM --> WS --> FE
    end

    MEDIAMTX -- "RTSP pull" --> SRC
    MEDIAMTX -- "RTSP pull (raw frames)" --> VR
    KAFKASINK -- "JSON metadata" --> KAFKA
    KAFKA -- "consume c2_metadata" --> KC
```

## Subsystem Documentation

| Diagram | File | Description |
|---------|------|-------------|
| Edge Pipeline | [01_EDGE_PIPELINE.md](./01_EDGE_PIPELINE.md) | DeepStream GStreamer pipeline on Jetson Nano |
| Backend Architecture | [02_BACKEND_ARCHITECTURE.md](./02_BACKEND_ARCHITECTURE.md) | FastAPI layers: runtime, analytics, infrastructure, transport |
| Frontend Architecture | [03_FRONTEND_ARCHITECTURE.md](./03_FRONTEND_ARCHITECTURE.md) | React pages, components, WS/REST connections |
| Data Flow | [04_DATA_FLOW.md](./04_DATA_FLOW.md) | End-to-end sequence diagram from camera to dashboard |
