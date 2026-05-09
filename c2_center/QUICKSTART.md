# C2 Surveillance Center - Quick Start Guide (v2.2 Architecture)

This guide provides instructions to start the entire C2 Center pipeline: Infrastructure, Backend, Frontend, and DeepStream on the Jetson Nano.

## Prerequisites
- **Node.js** (v18+)
- **Python 3.13** (with dependencies in `c2_center/backend/requirements.txt` installed)
- **Docker / Docker Desktop** (for Kafka and Zookeeper)
- **MediaMTX** binary (for RTSP streaming)
- **Jetson Nano** (with DeepStream 6.0.1+ for edge AI)

---

## 1. Start Infrastructure (Kafka & Zookeeper)

The system relies on Kafka to receive metadata from the Edge AI.

```powershell
cd D:\datas\Final.yolov8\c2_center
docker compose up -d
```
Wait a few seconds for Kafka to be ready on port `9092`.

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

The Edge AI component runs on the Jetson Nano, pulling RTSP streams, running YOLO inference, and publishing JSON metadata to Kafka.

1. SSH into your Jetson Nano.
2. Ensure you have the `yolo_all_exports_p2n_fine-tuning2_best.engine` and the custom parser library built.
3. Set your environment variables and run the multi-stream script:

```bash
# Inside the DeepStream container or Jetson environment:
cd /workspace/c2_center/deepstream/multi-stream

# Set the IP of the server running Kafka (Laptop A)
export LAPTOP_A_IP="192.168.1.196" # Change to your actual server IP
export NUM_SOURCES=2               # Set to the number of active cameras

# Launch the pipeline
bash setup_c2_multistream.sh
```

---

## Verification Steps

Once all components are running, verify the pipeline:

1. **Backend Health:** Go to `http://localhost:8000/api/health`. You should see `"kafka_connected": true` and a list of streams.
2. **Grid View:** Open the Frontend -> **Grid View** tab. You should see live video feeds from all connected RTSP cameras.
3. **Model Playground:** Go to the **Model Playground** tab to test offline tracking and inference with uploaded videos/images.
4. **Deep Analysis:** Go to the **Deep Analysis** tab to see live metrics (Counts, Heatmap) and draw ROIs for offline/playground analytics.

*Next up: We will begin evaluating the separation of live monitoring (simple accumulation) vs offline advanced analytics (Option D) to optimize the system for reliability.*
