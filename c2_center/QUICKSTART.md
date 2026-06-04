# C2 Surveillance Center - Quick Start Guide (v2.2 Architecture)

This guide provides instructions to start the entire C2 Center pipeline: Infrastructure, Backend, Frontend, and DeepStream on the Jetson Nano.

## Prerequisites
- **Node.js** (v18+)
- **Python 3.13** (with dependencies in `c2_center/backend/requirements.txt` installed)
- **Docker / Docker Desktop** (for MQTT, Postgres, Redis, MinIO)
- **MediaMTX** binary (for RTSP streaming)
- **Jetson Nano** (with DeepStream 6.0.1+ for edge AI)

---

## 1. Start Infrastructure (MQTT, Database, Cache, Storage)

The system relies on MQTT to receive metadata from the Edge AI.

```powershell
cd D:\datas\Final.yolov8
docker compose up -d
```
Wait a few seconds for MQTT to be ready on port `1883`.

---

## 2. Start the Backend

The backend is a FastAPI application that coordinates streams, analytics pipelines, and WebSockets.

```powershell
cd D:\datas\Final.yolov8\c2_center\backend
# Install dependencies if you haven't already:
# pip install -r requirements.txt

# Run the backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
*Note the path is now `app.main:app` as part of the new v2.2 layered architecture.*

---

## 3. Start the Frontend

The frontend is a React + Vite application.

```powershell
cd D:\datas\Final.yolov8\c2_center\frontend
# Install dependencies if you haven't already:
# npm install

# Run the dev server
npm run dev
```
Open your browser at `http://localhost:5173`.

---

## 4. Camera Management & MediaMTX

### Adding Cameras
Open the **Camera Management** tab in the Frontend (or run `infrastructure/manage_cameras.ps1`) to add RTSP streams. The backend stores them in `app/storage/sqlite/c2_cameras.db`.

### Starting MediaMTX
If you are simulating cameras or relying on the backend to deploy the MediaMTX config:
1. Ensure cameras are enabled in the Backend/Frontend.
2. In the backend API (or via the frontend), trigger the MediaMTX deployment to generate `c2_center/infrastructure/mediamtx.yml`.
3. Start MediaMTX:
```powershell
cd D:\datas\Final.yolov8\rstp\mediamtx_v1.17.1_windows_amd64
.\mediamtx.exe ..\..\c2_center\infrastructure\mediamtx.yml
```

---

## 5. Start DeepStream on Jetson Nano (Edge AI)

> ⚠️ **HARDWARE LIMITS**: Per [RCA-2026-05-09-DS001](docs/RCA-2026-05-09-DS001.md), the Jetson Nano operates at its absolute ceiling when running the C2 pipeline. 
> - **GPU**: ~98% utilization.
> - **CPU**: Core #4 pegged at 99%.
> - **Risk**: Imminent thermal throttling and frame drops. INT8 optimization or resolution downscaling is highly recommended.

The Edge AI component runs on the Jetson Nano, pulling RTSP streams, running YOLO inference, and publishing JSON metadata to MQTT.

1. **Deployment**: Upload your model (`.engine`), labels (`_labels.txt`), ONNX file, and the appropriate setup script to the Jetson Nano.
2. **Launch Container**:
```bash
sudo docker run -dit --name c2-deepstream --net=host \
    --runtime nvidia \
    -v ~/deepstream_yolo:/root/deepstream_yolo \
    nvcr.io/nvidia/deepstream-l4t:6.0.1-samples \
    sleep infinity

sudo docker exec -it c2-deepstream bash
```
3. **Run Pipeline**: Inside the container, choose the script that matches your algorithm's geometry needs:

```bash
cd /root/deepstream_yolo/multi-stream

# Set Environment Variables
export LAPTOP_A_IP="192.168.1.234" # Your server IP
export NUM_SOURCES=2               # Number of active streams
export RTSP_PATHS="cam1,cam2"      # RTSP paths on MediaMTX

# OPTION A: Area Occupancy / Density (Polygon ROI)
bash setup_c2_roi.sh

# OPTION B: Line Crossing / Speed (Entry/Exit Lines)
bash setup_c2_crossing.sh
```

### Jetson Optimization & Headless Mode
The setup scripts now automatically apply critical fixes from the latest [RCA](docs/RCA-2026-05-09-DS001.md):
- **Headless Fix**: Forcing `EGL_DISPLAY=none` and stripping EGL sink stubs to prevent plugin blacklisting in SSH sessions.
- **Batch Alignment**: Forcing `batch-size=1` for both `streammux` and `nvinfer` to match static ONNX exports and prevent OOM on the Nano.
- **Cache Clearing**: Automatically wipes the GStreamer registry on start to ensure plugin changes are picked up.

---

## Verification Steps

Once all components are running, verify the pipeline:

1. **Backend Health:** Go to `http://localhost:8000/api/health`. You should see `"mqtt_connected": true`.
2. **Grid View:** Open the Frontend -> **Grid View** tab. You should see live video feeds.
3. **Deep Analysis:** Go to the **Deep Analysis** tab. Select your algorithm (e.g., Line Crossing). The UI will present the corresponding parameters (Entry/Exit lines).
4. **Live Telemetry:** Monitor `jtop` on the Jetson Nano to ensure the pipeline is stable and not thermal throttling.

*Note: For production, we are transitioning from simple accumulation to Option D (Server-side Advanced Analytics) where the Jetson provides high-frequency raw metadata and the server performs the complex geometry logic.*
