# 🚀 C2 Surveillance & Data Pipeline - Getting Started Guide

Welcome to the project! This guide will walk you through setting up the entire system from scratch on your local development machine. 

The system consists of three main parts:
1. **Infrastructure**: MQTT Broker, PostgreSQL, Redis, MinIO.
2. **C2 Center**: FastAPI Backend & React Frontend for live video streaming and camera management.
3. **Data Pipeline**: Celery workers & MQTT listeners for background tracking and CVAT integration.
4. **Edge AI**: Jetson Nano running DeepStream (YOLOv8) pushing detections.

---

## 🛠️ 1. Prerequisites

Ensure your machine has the following installed:
- **Docker & Docker Compose**
- **Python 3.13** (or using conda/virtualenv)
- **Node.js v18+**
- **Git**

---

## 🏗️ 2. Start Core Infrastructure

The core infrastructure services share a common Docker network (`mlops_traffic_net`) so that all Python and Node applications can easily reach them.

```powershell
# Open terminal at the root of the project
cd D:\datas\Final.yolov8

# Start MQTT, PostgreSQL, Redis, and MinIO in the background
docker compose up -d
```
*Wait a few seconds for all containers to reach a `running` state.*

---

## 🏷️ 3. Install CVAT (Computer Vision Annotation Tool)

Our `data_pipeline` automatically pushes unconfident detections to CVAT for manual labeling. CVAT needs to be installed in a separate directory.

```powershell
# Go to a directory outside this project, e.g. D:\datas
git clone https://github.com/cvat-ai/cvat
cd cvat

# Set CVAT_HOST to your local network IP (e.g., 192.168.1.50) so Docker containers can reach it
$env:CVAT_HOST="192.168.1.50" 

# Start CVAT
docker compose up -d

# Create an admin account
docker exec -it cvat_server bash -ic "python3 ~/manage.py createsuperuser"
```

> ⚠️ **Update Pipeline Config**: After installing CVAT, open `Final.yolov8/data_pipeline/pipeline/docker-compose.yml` and update `CVAT_URL` to match your local IP (e.g., `http://192.168.1.50:8080`).

---

## ⚙️ 4. Start the Data Pipeline

The Data Pipeline listens to MQTT for edge detections and uses Celery to process them in the background.

```powershell
cd D:\datas\Final.yolov8\data_pipeline\pipeline

# Start the Celery workers, Beat scheduler, and MQTT listener
docker compose up -d
```

---

## 🖥️ 5. Start the C2 Center (Backend & Frontend)

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

## 📹 6. Starting Edge AI (Jetson Nano)

If you have the physical Jetson Nano hardware:
1. Connect to the Jetson Nano via SSH.
2. Deploy the `deepstream` folder to the device.
3. Start the DeepStream pipeline to begin publishing bounding boxes to your MQTT broker (`192.168.1.50:1883`).

### 🧪 6.1 Simulating Edge Data (No Hardware Needed)
If you just want to see data flowing without a Jetson Nano, you can use our built-in tests to mock MQTT data:
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
