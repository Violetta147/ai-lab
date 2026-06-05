# Plan: Architecture Overhaul (Edge Tracking + Backend MediaMTX)

## Summary
The current architecture (Base64 Video over MQTT + Backend Python Sync + Backend Tracking) causes severe latency, high CPU overhead, and jerky tracking. Since DeepStream is not an option, we will implement a **Native C++ Edge Tracking & Streaming Architecture** where the Jetson acts purely as a UDP hardware streamer, and the Backend (Laptop) handles the MediaMTX multiplexing.

## Problem → Solution

**Current state**: 
- Edge runs YOLO inference but sends Raw Detections + Base64 Video over MQTT.
- Backend Python `SyncEngine` tries to match them back together, causing massive delay.
- Python `sv.ByteTrack` runs on these delayed/dropped frames, causing ID switches.
- Heavy fan-out network burden on Jetson if multiple clients watch the stream.

**Desired state (Zero-Sync Architecture)**:
1. **Edge Tracking:** Revive the currently unused `ByteTracker` in `edge_server_cplusplus`. Tracking happens instantly on the edge right after YOLO inference.
2. **Edge Drawing:** Draw bounding boxes and Track IDs directly onto the `cv::Mat` in C++.
3. **Hardware UDP Streaming (Jetson):** Stream the drawn frame directly from C++ using OpenCV's GStreamer backend (`cv::VideoWriter`) with Jetson's hardware encoder (`nvv4l2h264enc`). Send via `udpsink` targeted directly at the Laptop's IP address.
4. **MediaMTX (Laptop):** Run MediaMTX in Docker on the Backend Laptop to ingest the UDP stream and serve it as WebRTC/RTSP to frontend dashboards.
5. **Backend Analytics:** The Python backend no longer handles video frames or tracking. The Jetson appends the C++ `tracker_id` into the MQTT JSON payload. The backend simply listens to MQTT and runs density/speed calculations (geometry) using these pre-tracked coordinates.

## Proposed Changes

### 1. Edge Server: Enable C++ ByteTracker
#### [MODIFY] `edge_server_cplusplus/src/main.cpp`
- Instantiate `ByteTracker tracker(30, 30);`
- After YOLO inference, pass `detections` to `tracker.update()`.
- Append the `tracker_id` to the `nlohmann::json` MQTT payload.
- Draw the resulting tracked boxes/IDs onto the `cv::Mat` frame.

### 2. Edge Server: Hardware-Accelerated VideoWriter (UDP Sink)
#### [MODIFY] `edge_server_cplusplus/src/main.cpp`
- Remove `base64_encode_image` and `mqtt.publish(LIVE_VIDEO_TOPIC)`.
- Replace with a GStreamer `cv::VideoWriter`:
  ```cpp
  // IP_LAPTOP will be loaded from .env config
  cv::VideoWriter writer("appsrc ! videoconvert ! nvv4l2h264enc insert-sps-pps=true bitrate=4000000 ! h264parse ! rtph264pay ! udpsink host=" + IP_LAPTOP + " port=8522 sync=false", cv::CAP_GSTREAMER, 0, 15, cv::Size(640, 640), true);
  ```
- Write the drawn frames: `writer.write(drawn_frame);`

### 3. Backend Setup: Run MediaMTX
- Create a `mediamtx.yml` configuration defining a path that listens on UDP port `8522`.
- Run MediaMTX via Docker on the backend laptop:
  ```bash
  docker run --rm -it --network=host bluenviron/mediamtx
  ```

### 4. Backend Python: Remove Video Sync, Enable Edge IDs
#### [MODIFY] `c2_center/backend/app/runtime/pipeline_manager.py`
- Disable the `SyncEngine` and `sv.ByteTrack` logic.
- Update `pipeline_manager` to read `tracker_id` from the MQTT payload instead of assigning it.
- Continue passing the tracked coordinates to the Analytics Engine (Density, Line Crossing) which only needs mathematical coordinates, not pixels.

---

## User Review Required

> [!WARNING]  
> 1. We will need to add the Backend Laptop's IP address to the Jetson's `.env` file (e.g., `BACKEND_STREAM_IP=192.168.1.xxx`).
> 2. The Python Backend code will be heavily stripped down since it no longer needs to process or sync video frames.

---

## Verification Plan
1. Start `mediamtx` on the Laptop.
2. Compile and run `edge_server_cplusplus` on the Jetson.
3. Open a browser on the Laptop and navigate to the MediaMTX WebRTC stream.
4. Verify backend terminal logs show successful density calculations without video processing.
