"""
C2 Center Backend — Main Application Entry Point

Starts FastAPI with all services:
- Kafka consumer (background)
- Video readers (threaded)
- Sync engine
- Stream processor (WebSocket broadcaster)
- REST APIs (streams, zones, analytics, models, playground)
- WebSocket endpoints

Usage:
    cd c2_center/backend
    uvicorn main:app --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager
import os
import sys

# Ensure the backend package directory is on sys.path so custom modules
# required by model loading (for example `prune_module.py`) are importable
# before any model initialization occurs. This prevents torch/ultralytics
# from failing when a checkpoint refers to a custom module name.
_backend_dir = os.path.dirname(__file__)
if _backend_dir and _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from services.kafka_consumer import KafkaConsumerService
from services.model_registry import ModelRegistry
from services.sync_engine import SyncEngine
from services.video_reader import VideoReaderService
from services.camera_db import camera_db
from ws.streamer import StreamProcessor
from services.zone_db import zone_store

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("c2_backend")

# --- Global services ---
kafka_consumer = KafkaConsumerService()
video_reader = VideoReaderService()
sync_engine = SyncEngine(video_reader, kafka_consumer)
model_registry = ModelRegistry()
stream_processor = StreamProcessor(sync_engine, zone_store, model_registry)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("=" * 50)
    logger.info("C2 CENTER BACKEND STARTING")
    logger.info("=" * 50)

    # No automatic DB seeding at startup — cameras are managed via the
    # Cameras API or the interactive `manage_cameras.ps1` script.

    # Log configuration
    logger.info("Configuration:")
    logger.info("  Kafka: %s (topic: %s)", settings.KAFKA_BOOTSTRAP, settings.KAFKA_TOPIC)
    cameras = camera_db.list_cameras()
    logger.info("  Cameras: %d configured", len(cameras))
    for cam in cameras:
        logger.info("    - %s: %s (enabled: %s)", cam["stream_id"], cam["rtsp_url"], cam["enabled"])

    # Scan models
    models = model_registry.scan()
    logger.info("Discovered %d models", len(models))

    # Start services
    video_reader.start()

    # Start heartbeat monitor (adds streams only after RTSP check)
    from services.heartbeat import HeartbeatMonitor
    heartbeat = HeartbeatMonitor(video_reader)
    heartbeat.start()

    try:
        await kafka_consumer.start()
    except Exception:
        logger.warning("Kafka not available — running without metadata sync")

    stream_processor.start()

    logger.info("All services started. API: %s:%d", settings.API_HOST, settings.API_PORT)
    yield

    # Shutdown
    logger.info("Shutting down...")
    await stream_processor.stop()
    await kafka_consumer.stop()
    heartbeat.stop()
    video_reader.stop()
    logger.info("Shutdown complete.")


# --- App ---
app = FastAPI(
    title="C2 Surveillance Center",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REST API routes ---
from api.streams import get_router as streams_router
from api.cameras import get_router as cameras_router
from api.zones import router as zones_router
from api.analytics_api import get_router as analytics_router
from api.models_api import get_router as models_router
from api.playground import get_router as playground_router
from api.mediamtx import router as mediamtx_router

app.include_router(streams_router(sync_engine, kafka_consumer))
app.include_router(cameras_router(video_reader))
app.include_router(zones_router)
app.include_router(analytics_router(stream_processor))
app.include_router(models_router(model_registry))
app.include_router(playground_router(model_registry))
app.include_router(mediamtx_router)


# --- WebSocket endpoints ---
@app.websocket("/ws/stream/{stream_id}")
async def ws_video(websocket: WebSocket, stream_id: str):
    """WebSocket: live annotated video frames (base64 JPEG)."""
    await websocket.accept()
    stream_processor.register_stream(stream_id)
    stream_processor.add_video_client(stream_id, websocket)
    logger.info("WS video client connected: %s", stream_id)
    try:
        while True:
            await websocket.receive_text()  # Keep alive
    except WebSocketDisconnect:
        pass
    finally:
        stream_processor.remove_video_client(stream_id, websocket)
        logger.info("WS video client disconnected: %s", stream_id)


@app.websocket("/ws/stats/{stream_id}")
async def ws_stats(websocket: WebSocket, stream_id: str):
    """WebSocket: analytics stats JSON at 2Hz."""
    await websocket.accept()
    stream_processor.register_stream(stream_id)
    stream_processor.add_stats_client(stream_id, websocket)
    logger.info("WS stats client connected: %s", stream_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        stream_processor.remove_stats_client(stream_id, websocket)
        logger.info("WS stats client disconnected: %s", stream_id)


@app.get("/")
async def root():
    cameras = camera_db.list_cameras()
    streams = {cam["stream_id"]: cam["rtsp_url"] for cam in cameras}
    return {
        "service": "C2 Surveillance Center",
        "version": "2.1.0",
        "docs": "/docs",
        "streams": streams,
    }
