# RTSP + MQTT Metadata Streaming Architecture

Provide a brief description of the problem, any background context, and what the change accomplishes.
- **Current Problem**: Streaming Base64 encoded images over MQTT creates massive CPU overhead on both the Jetson (encoding) and Backend (decoding/re-encoding), while choking the MQTT broker bandwidth.
- **Solution**: Split the data into two streams. Use Jetson's hardware NVENC encoder to stream 30 FPS video via RTSP, while sending only lightweight JSON bounding box metadata via MQTT at the AI's processing rate (e.g., 10 FPS). The Python backend will consume the RTSP stream and sync the metadata by matching timestamps.

## Proposed Changes

### Edge Server (Jetson C++)

- Remove `base64_encode_image` and the MQTT video publishing loop.
- Implement an RTSP server or use a GStreamer pipeline output (e.g., `appsrc ! nvvidconv ! nvv4l2h264enc ! rtspclientsink`) to stream raw frames at 30 FPS.
- Continue running YOLO inference at a controlled interval (e.g., `INFERENCE_INTERVAL_MS = 100`).
- Ensure each MQTT Metadata payload includes the precise `timestamp` corresponding to the exact frame the AI processed.

### Python Backend (`LiveSyncEngine`)

- Stop subscribing to the MQTT video topic for raw frames.
- Initialize `cv2.VideoCapture("rtsp://ip_jetson/live")` to read the 30 FPS video stream.
- Maintain an internal buffer of received MQTT metadata.
- For each frame pulled from RTSP, check its timestamp and query the metadata buffer for the closest match.
- Overlay the bounding boxes onto the frame.
- Stream the processed frame to the frontend via WebSockets or MJPEG exactly as it works today.

## Verification Plan

### Manual Verification
- Verify the video stream remains smooth at 30 FPS.
- Verify bounding boxes appear and track objects without noticeable drift (though updating at a lower framerate).
- Check CPU utilization on the Jetson Nano to ensure hardware encoding is being utilized (CPU usage should drop significantly).
- Check MQTT broker traffic to ensure it is no longer overloaded.
