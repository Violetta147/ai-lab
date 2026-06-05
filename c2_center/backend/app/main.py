"""
C2 Center backend — FastAPI entry point.

Composition root:
1. Wire the live monitoring pipeline (kafka, video, sync, analytics, ws).
2. Discover analytics plugins.
3. Mount REST + WebSocket routes.
4. Drive `pipeline.start()` / `pipeline.stop()` from FastAPI lifespan.

Run with:
    cd c2_center/backend
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

import logging
import os
import sys
from contextlib import asynccontextmanager

# Ensure the backend directory is importable so that `prune_module` (a top-level
# module referenced by some Ultralytics .pt checkpoints) can be loaded by
# torch's unpickler. This must happen before any model load.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR and _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.analytics.registry import registry
from app.api import analytics_api as analytics_api_module
from app.api import cameras as cameras_module
from app.api import mediamtx as mediamtx_module
from app.api import models_api as models_api_module
from app.api import playground as playground_module
from app.api import streams as streams_module
from app.api import zones as zones_module
from app.core.config import settings
from app.core.log_filters import HealthLogFilter
from app.infrastructure.database.camera_repository import camera_repo
from app.infrastructure.database.zone_repository import zone_repo
from app.infrastructure.models.registry import ModelRegistry
from app.pipelines.live_monitoring import wire_live_pipeline
from app.ws.streamer import WsStreamer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("c2_backend")

# Suppress noisy /api/health access log lines
logging.getLogger("uvicorn.access").addFilter(HealthLogFilter())

# --- Composition root: build singletons once at import time ---
registry.discover("app.analytics.plugins")

model_registry = ModelRegistry()
ws_streamer = WsStreamer()
pipeline = wire_live_pipeline(
    registry=registry,
    ws_streamer=ws_streamer,
    camera_repo=camera_repo,
    zone_repo=zone_repo,
    model_registry=model_registry,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 50)
    logger.info("C2 CENTER BACKEND STARTING")
    logger.info("=" * 50)
    logger.info("Configuration:")
    if settings.METADATA_SOURCE == "mqtt":
        logger.info(
            "  Metadata: MQTT %s:%d (topic: %s)",
            settings.MQTT_BROKER,
            settings.MQTT_PORT,
            settings.MQTT_TOPIC,
        )
    else:
        logger.info(
            "  Metadata: Kafka %s (topic: %s)",
            settings.KAFKA_BOOTSTRAP,
            settings.KAFKA_TOPIC,
        )
    logger.info("  Models dir: %s", settings.MODELS_DIR)

    cameras = camera_repo.list_cameras()
    logger.info("  Cameras: %d configured", len(cameras))
    for cam in cameras:
        logger.info(
            "    - %s: %s (enabled: %s)",
            cam["stream_id"],
            cam["rtsp_url"],
            cam["enabled"],
        )

    discovered = model_registry.scan()
    logger.info("Discovered %d models", len(discovered))

    discovered_plugins = registry.slugs()
    logger.info("Registered analytics plugins: %s", discovered_plugins)

    await pipeline.start()
    logger.info(
        "All services started. API: %s:%d", settings.API_HOST, settings.API_PORT
    )

    yield

    logger.info("Shutting down...")
    await pipeline.stop()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="C2 Surveillance Center",
    version="2.2.0",
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
app.include_router(
    streams_module.get_router(pipeline.stream_manager, pipeline.kafka_consumer)
)
app.include_router(cameras_module.get_router(pipeline))
app.include_router(zones_module.router)
app.include_router(analytics_api_module.get_router(pipeline))
app.include_router(models_api_module.get_router(model_registry))
app.include_router(playground_module.get_router(model_registry))
app.include_router(mediamtx_module.router)


# --- WebSocket endpoints ---
@app.websocket("/ws/stream/{stream_id}")
async def ws_video(websocket: WebSocket, stream_id: str):
    """WebSocket: live annotated video frames (base64 JPEG)."""
    await websocket.accept()
    ws_streamer.register_stream(stream_id)
    ws_streamer.add_video_client(stream_id, websocket)
    logger.info("WS video client connected: %s", stream_id)
    try:
        while True:
            await websocket.receive_text()  # keep-alive
    except WebSocketDisconnect:
        pass
    finally:
        ws_streamer.remove_video_client(stream_id, websocket)
        logger.info("WS video client disconnected: %s", stream_id)


@app.websocket("/ws/stats/{stream_id}")
async def ws_stats(websocket: WebSocket, stream_id: str):
    """WebSocket: analytics stats JSON at 2 Hz."""
    await websocket.accept()
    ws_streamer.register_stream(stream_id)
    ws_streamer.add_stats_client(stream_id, websocket)
    logger.info("WS stats client connected: %s", stream_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_streamer.remove_stats_client(stream_id, websocket)
        logger.info("WS stats client disconnected: %s", stream_id)


@app.get("/")
async def root():
    cameras = camera_repo.list_cameras()
    streams = {cam["stream_id"]: cam["rtsp_url"] for cam in cameras}
    return {
        "service": "C2 Surveillance Center",
        "version": "2.2.0",
        "docs": "/docs",
        "streams": streams,
    }
