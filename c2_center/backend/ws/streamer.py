"""
C2 Center — WebSocket Video Streamer

Processing loop per stream:
1. Get synced frame from SyncEngine
2. Convert JSON objects → sv.Detections
3. Run active analyzer
4. Encode as JPEG → base64
5. Broadcast via WebSocket
"""

import asyncio
import base64
import logging
import time

import cv2
import numpy as np
import supervision as sv

from analytics import ANALYZER_REGISTRY, BaseAnalyzer
from config import settings

logger = logging.getLogger(__name__)

# Track whether we've already warned about missing tracking IDs in Kafka metadata
missing_tracker_warned = False


def metadata_to_detections(objects: list[dict]) -> sv.Detections:
    """Convert Kafka JSON objects list into sv.Detections."""
    global missing_tracker_warned
    if not objects:
        return sv.Detections.empty()

    xyxy, confs, class_ids, tracker_ids = [], [], [], []

    for obj in objects:
        bbox = obj.get("bbox", {})
        x = bbox.get("x", 0)
        y = bbox.get("y", 0)
        w = bbox.get("w", 0)
        h = bbox.get("h", 0)
        xyxy.append([x, y, x + w, y + h])
        confs.append(obj.get("confidence", 0.5))
        class_ids.append(obj.get("class_id", 0))

        t_id = obj.get("tracking_id", -1)
        if t_id == -1 and not missing_tracker_warned:
            logger.warning("Missing tracking_id in Kafka metadata! Algorithms relying on tracking may fail.")
            missing_tracker_warned = True
        tracker_ids.append(t_id)
        

    return sv.Detections(
        xyxy=np.array(xyxy, dtype=np.float32),
        confidence=np.array(confs, dtype=np.float32),
        class_id=np.array(class_ids, dtype=int),
        tracker_id=np.array(tracker_ids, dtype=int),
    )


def frame_to_base64(frame: np.ndarray, quality: int = 75) -> str:
    """Encode frame as JPEG and return base64 string."""
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    _, buffer = cv2.imencode(".jpg", frame, encode_params)
    return base64.b64encode(buffer).decode("utf-8")


class StreamProcessor:
    """Manages per-stream analytics and WebSocket broadcasting."""

    def __init__(self, sync_engine, zone_store, model_registry):
        self.sync_engine = sync_engine
        self.zone_store = zone_store
        self.model_registry = model_registry
        # Per-stream analyzer instances: stream_id -> BaseAnalyzer
        self._analyzers: dict[str, BaseAnalyzer] = {}
        self._active_algo: dict[str, str] = {}  # stream_id -> algo slug
        self._ws_clients: dict[str, set] = {}  # stream_id -> set of websockets
        self._stats_clients: dict[str, set] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False

    def start(self):
        self._running = True
        for stream_id in self.sync_engine.get_stream_ids():
            self.register_stream(stream_id)

    def register_stream(self, stream_id: str):
        if stream_id in self._tasks:
            return

        self._ws_clients[stream_id] = set()
        self._stats_clients[stream_id] = set()
        self._active_algo[stream_id] = "absolute_count"
        self._analyzers[stream_id] = ANALYZER_REGISTRY["absolute_count"]()

        if self._running:
            task = asyncio.create_task(self._stream_loop(stream_id))
            self._tasks[stream_id] = task
        logger.info("Stream processor started: %s", stream_id)

    def unregister_stream(self, stream_id: str):
        task = self._tasks.pop(stream_id, None)
        if task:
            task.cancel()
        self._ws_clients.pop(stream_id, None)
        self._stats_clients.pop(stream_id, None)
        self._active_algo.pop(stream_id, None)
        self._analyzers.pop(stream_id, None)

    async def stop(self):
        self._running = False
        for task in self._tasks.values():
            task.cancel()

    def set_algorithm(self, stream_id: str, algo_slug: str):
        if algo_slug not in ANALYZER_REGISTRY:
            raise ValueError(f"Unknown algorithm: {algo_slug}")
        self._active_algo[stream_id] = algo_slug
        self._analyzers[stream_id] = ANALYZER_REGISTRY[algo_slug]()
        logger.info("[%s] Algorithm switched to: %s", stream_id, algo_slug)

    def add_video_client(self, stream_id: str, ws):
        self._ws_clients.setdefault(stream_id, set()).add(ws)

    def remove_video_client(self, stream_id: str, ws):
        self._ws_clients.get(stream_id, set()).discard(ws)

    def add_stats_client(self, stream_id: str, ws):
        self._stats_clients.setdefault(stream_id, set()).add(ws)

    def remove_stats_client(self, stream_id: str, ws):
        self._stats_clients.get(stream_id, set()).discard(ws)

    async def _stream_loop(self, stream_id: str):
        """Main processing loop for a single stream."""
        interval = 1.0 / settings.WS_TARGET_FPS
        stats_interval = 0.5  # 2 Hz
        last_stats = 0

        while self._running:
            try:
                t0 = time.time()

                frame, objects = await self.sync_engine.get_synced_frame(stream_id)
                if frame is None:
                    await asyncio.sleep(0.05)
                    continue

                detections = metadata_to_detections(objects)
                analyzer = self._analyzers.get(stream_id)

                if analyzer:
                    zone_params = self.zone_store.get(stream_id, {})
                    active_model = self.model_registry.active_model_name
                    if active_model:
                        try:
                            labels = self.model_registry.get_labels(active_model)
                            zone_params["labels_map"] = {i: name for i, name in enumerate(labels)}
                        except ValueError:
                            zone_params["labels_map"] = {}
                    result = analyzer.process(frame, detections, zone_params)
                    annotated = result.annotated_frame
                    metrics = result.metrics
                else:
                    annotated = frame
                    metrics = {}

                # Broadcast video frame
                if self._ws_clients.get(stream_id):
                    b64 = await asyncio.to_thread(
                        frame_to_base64, annotated, settings.WS_JPEG_QUALITY
                    )
                    dead = set()
                    # Iterate over a copy to avoid "Set changed size during iteration" error
                    # when clients disconnect (remove_video_client is called from another task)
                    for ws in list(self._ws_clients[stream_id]):
                        try:
                            await ws.send_json({"type": "frame", "data": b64})
                        except Exception:
                            dead.add(ws)
                    self._ws_clients[stream_id] -= dead

                # Broadcast stats at 2Hz
                now = time.time()
                if now - last_stats >= stats_interval and self._stats_clients.get(stream_id):
                    last_stats = now
                    dead = set()
                    # Iterate over a copy to avoid "Set changed size during iteration" error
                    for ws in list(self._stats_clients[stream_id]):
                        try:
                            await ws.send_json({"type": "stats", "data": metrics})
                        except Exception:
                            dead.add(ws)
                    self._stats_clients[stream_id] -= dead

                # Rate limit
                elapsed = time.time() - t0
                if elapsed < interval:
                    await asyncio.sleep(interval - elapsed)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("[%s] Stream loop error", stream_id)
                await asyncio.sleep(0.5)
