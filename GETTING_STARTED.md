# 🚀 C2 Surveillance & Data Pipeline - Getting Started Guide

Welcome to the project! This guide will walk you through setting up the entire system from scratch on your local development machine. 

The system consists of three main parts:
1. **Infrastructure**: MQTT Broker, PostgreSQL, Redis, MinIO.
2. **C2 Center**: FastAPI Backend & React Frontend for live video streaming and camera management.
3. **Data Pipeline**: Celery workers & MQTT listeners for background tracking and CVAT integration.
4. **Edge AI**: Jetson Nano running YOLOv8 (via `edge_server`) pushing detections.

---

## 🛠️ 1. Prerequisites

Ensure your machine has the following installed:
- **Docker & Docker Compose**
- **Python 3.13** (or using conda/virtualenv)
- **Node.js v18+**
- **Git**

---

## ⚙️ 3. Configure Environment Variables

Before starting the infrastructure, you must configure the global environment variables for the project.

```powershell
# Open terminal at the root of the project
cd D:\datas\Final.yolov8

# Copy the example environment file
cp .env.example .env
```

Open the newly created `.env` file in your code editor and update the default passwords and settings (like `DB_PASS`, `MINIO_ROOT_PASSWORD`) if necessary.

> 💡 **Note on sub-components:** Some sub-components have their own `.env` files that you will need to update with your local IP address (e.g., `172.16.x.x`):
> - **Edge Server:** `edge_server_cplusplus/.env` (Requires MQTT & MinIO IPs)
> - **Data Pipeline:** `data_pipeline/pipeline/.env` (Requires CVAT URL)
> - **C2 Center Frontend:** `c2_center/.env` (Requires Backend/MQTT IPs)

---

## 🏗️ 4. Start Core Infrastructure

The core infrastructure services share a common Docker network (`mlops_traffic_net`) so that all Python and Node applications can easily reach them.

```powershell
# Open terminal at the root of the project
cd D:\datas\Final.yolov8\data_pipeline\core-backbone

# Start MQTT, PostgreSQL, Redis, MinIO, and MediaMTX in the background
docker compose up -d
```
*Wait a few seconds for all containers to reach a `running` state.*

### 🪣 4.1 Configure MinIO Buckets
The MLOps Data Pipeline requires 5 specific buckets to function correctly. You must create them before starting the pipeline.

1. Open your browser and navigate to `http://localhost:9002` (MinIO Console).
2. Log in with the default credentials (as defined in `docker-compose.yml`):
   - Username: `admin`
   - Password: `password123`
3. Go to **Buckets** on the left menu and click **Create Bucket**. Create the following exactly as named:
   - `raw-data` *(Used by Edge Server to upload raw frames)*
   - `pseudo-labels` *(Used to store AI-generated pre-labels)*
   - `archived-images` *(Used for archiving old data)*
   - `archived-labels` *(Used for archiving old labels)*
   - `labeled-data` *(Used by CVAT for human annotations)*
   - `base-dataset` *(Used for training datasets)*
   - `production-models` *(Used to store .pt and .engine AI models)*

---

## 🏷️ 5. Install CVAT & Auto-Provisioning

Our `data_pipeline` automatically pushes unconfident detections to CVAT for manual labeling. CVAT is now integrated as a git submodule inside `data_pipeline`, which resolves network routing automatically (`mlops_traffic_net`).

```powershell
# 1. Initialize the CVAT submodule
cd D:\datas\Final.yolov8\data_pipeline
git submodule update --init --recursive

# 2. Start CVAT
cd cvat
# Set CVAT_HOST to your local network IP (e.g., 172.16.0.252) if accessing from another machine
$env:CVAT_HOST="172.16.0.252" 
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

# 3. Auto-Provision Project, User, and Cloud Storage
cd D:\datas\Final.yolov8\data_pipeline
python scripts/setup_cvat_env.py
```

> 💡 **What does `setup_cvat_env.py` do?**
> Instead of manually migrating the database, creating superusers, manually clicking to create a Project, and hooking up MinIO Cloud Storage, this script uses CVAT's API to automate all of it. It then auto-writes the resulting `CVAT_PROJECT_ID` and `CVAT_CLOUD_STORAGE_ID` straight into your `.env` file!

---

## ⚙️ 6. Start the Data Pipeline

The Data Pipeline listens to MQTT for edge detections and uses Celery to process them in the background.

```powershell
cd D:\datas\Final.yolov8\data_pipeline\pipeline

# Start the Celery workers, Beat scheduler, and MQTT listener
docker compose up -d
```

---

## 🖥️ 7. Start the C2 Center (Backend & Frontend)

### Backend (FastAPI)
The backend coordinates WebSockets and RTSP streams.
```powershell
cd D:\datas\Final.yolov8\c2_center\backend

# Install dependencies (only needed the first time)
pip install -r requirements.txt

# Start the server on port 8000
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend (React)
The frontend provides the user interface for monitoring.
```powershell
cd D:\datas\Final.yolov8\c2_center\frontend

# Install dependencies (only needed the first time)
npm install

# Start the dev server
npm run dev
```
Open your browser and navigate to `http://localhost:5173`.

---

## 📹 8. Starting Camera Streams & Edge AI (Jetson Nano)

In this architecture, the **Jetson Nano (Edge Server)** is responsible for:
1. Capturing video directly from a USB/CSI camera or an IP Camera (RTSP).
2. Running YOLOv8 inference to generate bounding boxes.
3. Pushing the annotated video stream to **MediaMTX** (running in Docker on the backend).

### 🎥 8.1 Setup Video Input for Jetson

You can feed video into the Jetson in two ways:
- **Local Camera:** Plug a USB camera directly into the Jetson (e.g., `/dev/video0`).
- **IP Camera:** Use an RTSP URL from an IP Camera in the same local network.

*If you just want to test on your Laptop without a Jetson or real camera, you can use a simulated video stream instead. Check out [Simulating Edge Data](#-63-simulating-edge-data-no-videohardware-needed).*

### 🚀 8.2 Start the Edge Server (YOLO Inference)

We recommend using the C++ Edge Server for maximum performance on Jetson hardware.

```bash
cd D:\datas\Final.yolov8\edge_server_cplusplus
mkdir build && cd build
cmake ..
make -j4

# Define your video source (USB camera or RTSP URL)
export VIDEO_PATH="/dev/video0" # Or "rtsp://admin:1234@192.168.1.100/stream"

# Define the IP of your backend laptop running MediaMTX
export MEDIAMTX_HOST="172.16.0.252"
export MQTT_BROKER="172.16.0.252"

# Start the C++ edge server
./c2_edge_server
```

*(Once started, Jetson will push the final video to `rtsp://172.16.0.252:8554/cam_01`. The Backend will pull this stream automatically and display it in the Frontend!)*

### 🧪 6.3 Simulating Edge Data (No Video/Hardware Needed)
If you don't want to run FFmpeg or the YOLO models locally, you can use our built-in tests to push fake tracking data to your local MQTT broker:
```powershell
cd D:\datas\Final.yolov8\c2_center\backend
pytest tests/test_mqtt_adapters.py
```
*This will push fake tracking data to your local MQTT broker, which will then be picked up by the `data_pipeline` and shown on the `c2_center` frontend.*

---

## 🎯 7. Verify Everything is Working

1. **Check Infra:** Run `docker ps` - you should see Postgres, MinIO, Redis, Mosquitto, CVAT, and Celery running.
2. **Check API:** Go to `http://localhost:8000/api/health` - both `mqtt_connected` and `db_connected` should be `true`.
3. **Check UI:** Open `http://localhost:5173` and go to the "Grid View". You should see your camera feeds loading.
4. **Check Tracking:** If mock data is running or the Jetson is active, bounding boxes will begin drawing over the video feeds automatically!

Happy Coding! 🎉
