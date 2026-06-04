<!-- Generated: 2026-06-05 | Files scanned: ~50 | Token estimate: ~400 -->

# System Architecture

## Overview
The system is divided into two primary sub-repositories:
- **`c2_center`**: A FastAPI-based backend and frontend UI for managing cameras, streams, and presenting synchronized bounding boxes.
- **`data_pipeline`**: A background processing pipeline that consumes raw detections from edge devices via MQTT, tracks objects, and manages CVAT integrations.

## High-Level Data Flow
1. **Edge Devices (Jetson)** → Run YOLOv8, send raw detections to MQTT.
2. **Data Pipeline** (`TrackingBridge`) → Consumes raw MQTT, applies IoU Tracking, publishes tracked objects to MQTT.
3. **C2 Center Backend** (`SyncEngine`) → Pulls RTSP video frames + latest tracked MQTT metadata and fuses them into a single stream.
4. **Data Pipeline** (`DBHandler`) → Writes raw events to PostgreSQL for offline training and CVAT labeling.

## Key Boundaries
`c2_center/` (Web UI & Stream Serving)
`data_pipeline/` (Edge Data Ingestion & Tracking)
