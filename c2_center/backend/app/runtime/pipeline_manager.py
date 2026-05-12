"""
Pipeline manager — owns the per-stream asyncio processing loop.

For every active stream, runs an asyncio task that:
  1. pulls a synchronized (frame, detections) pair from SyncEngine,
  2. dispatches it to the AnalyticsDispatcher,
  3. emits the resulting (annotated_frame, metrics) to subscribers.

Subscribers (e.g. the WebSocket transport) register callbacks via
`on_frame()` and `on_stats()` — they receive results without the
pipeline knowing how they are delivered.
"""

import asyncio
import logging
import time
from typing import Awaitable, Callable

import numpy as np

from app.core.config import settings
from app.domain.detection.converters import metadata_to_detections
from app.runtime.analytics_dispatcher import AnalyticsDispatcher
from app.runtime.sync_engine import SyncEngine

logger = logging.getLogger(__name__)


# Subscriber callback signatures.
FrameSubscriber = Callable[[str, np.ndarray, dict], Awaitable[None]]
StatsSubscriber = Callable[[str, dict], Awaitable[None]]


class PipelineManager:
    """Owns one asyncio task per stream that drives the live processing loop."""

    def __init__(
        self,
        sync_engine: SyncEngine,
        dispatcher: AnalyticsDispatcher,
        zone_repo,
        model_registry,
    ) -> None:
        self._sync = sync_engine
        self._dispatcher = dispatcher
        self._zone_repo = zone_repo
        self._model_registry = model_registry

        self._tasks: dict[str, asyncio.Task] = {}
        self._frame_subs: list[FrameSubscriber] = []
        self._stats_subs: list[StatsSubscriber] = []
        self._running = False
        self._stats_interval_sec = 0.5  # 2 Hz
        self._log_interval_sec = 5.0  # Debug log every 5s
        self._last_log_at: dict[str, float] = {}
        self._sync_counts: dict[str, int] = {}  # objects synced per stream

    def on_frame(self, callback: FrameSubscriber) -> None:
        """Subscribe to annotated-frame events."""
        self._frame_subs.append(callback)

    def on_stats(self, callback: StatsSubscriber) -> None:
        """Subscribe to metrics events."""
        self._stats_subs.append(callback)

    def start(self) -> None:
        """Mark pipelines as running. Tasks are launched per stream by `start_stream`."""
        self._running = True
        logger.info("Pipeline manager running")

    async def stop(self) -> None:
        """Cancel every per-stream task."""
        self._running = False
        for task in list(self._tasks.values()):
            task.cancel()
        for task in list(self._tasks.values()):
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks.clear()
        logger.info("Pipeline manager stopped")

    def start_stream(self, stream_id: str) -> None:
        """Launch the processing task for `stream_id` if not already running."""
        if stream_id in self._tasks:
            return
        if not self._running:
            logger.warning("Pipeline manager not started; deferring stream %s", stream_id)
            return
        self._dispatcher.attach_stream(stream_id)
        task = asyncio.create_task(self._loop(stream_id), name=f"pipeline-{stream_id}")
        self._tasks[stream_id] = task
        logger.info("[%s] Pipeline task started", stream_id)

    def stop_stream(self, stream_id: str) -> None:
        """Cancel the processing task for `stream_id`."""
        task = self._tasks.pop(stream_id, None)
        if task:
            task.cancel()
        self._dispatcher.detach_stream(stream_id)

    async def _loop(self, stream_id: str) -> None:
        """Main processing loop for a single stream."""
        interval = 1.0 / max(1, settings.WS_TARGET_FPS)
        last_stats_at = 0.0

        while self._running:
            try:
                t0 = time.time()

                # Pacing: Ensure we don't run faster than the target FPS to avoid metadata reuse
                loop_start = time.time()
                target_fps = 25.0
                frame_time = 1.0 / target_fps

                frame, objects = await self._sync.get_synced_frame(stream_id)
                if frame is None:
                    await asyncio.sleep(0.01)
                    continue

                detections = metadata_to_detections(objects)

                # ==================== DIAGNOSTIC LOGGING ====================
                frame_h, frame_w = frame.shape[:2]
                
                # Log raw Kafka bbox BEFORE any scaling (first 3 objects)
                if objects and not hasattr(self, '_diag_logged'):
                    raw_sample = objects[:3]
                    logger.warning(
                        "[DIAG][%s] FRAME_RES=%dx%d | RAW Kafka objects(%d): %s",
                        stream_id, frame_w, frame_h, len(objects),
                        str([{k: v for k, v in o.items() if k in ('tracking_id', 'bbox')} for o in raw_sample]),
                    )
                    if len(detections) > 0:
                        logger.warning(
                            "[DIAG][%s] PRE-SCALE xyxy[0]: %s",
                            stream_id, detections.xyxy[0].tolist(),
                        )

                # FIX: Scale bbox from inference resolution (640x640) to frame resolution.
                # DeepStream's streammux resizes input to 640x640 for YOLO inference.
                # The Kafka metadata contains bbox coords in that inference space.
                # But the RTSP video frame is at camera native res (e.g. 1920x1080).
                # Without scaling, boxes appear tiny/misplaced ("ghost boxes").
                if len(detections) > 0:
                    inf_w, inf_h = 640, 640  # streammux width/height in setup_c2_roi.sh
                    if frame_w != inf_w or frame_h != inf_h:
                        scale_x = frame_w / inf_w
                        scale_y = frame_h / inf_h
                        detections.xyxy[:, [0, 2]] *= scale_x
                        detections.xyxy[:, [1, 3]] *= scale_y

                # Log POST-SCALE bbox (once)
                if objects and not hasattr(self, '_diag_logged'):
                    if len(detections) > 0:
                        logger.warning(
                            "[DIAG][%s] POST-SCALE xyxy[0]: %s | scale=%.2fx%.2f",
                            stream_id, detections.xyxy[0].tolist(),
                            frame_w / 640, frame_h / 640,
                        )
                    self._diag_logged = True
                # ============================================================

                if not objects:
                    # Skip analytics if no objects, but keep emitting stats to avoid WS timeout
                    await self._emit_stats(stream_id, {"status": "running", "synced_objects": 0})
                    # FPS Pacing Sleep still needed here
                    loop_elapsed = time.time() - loop_start
                    sleep_time = max(0, frame_time - loop_elapsed)
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)
                    continue

                params = self._build_params(stream_id, detections, frame=frame)

                # Periodic debug logging
                self._sync_counts[stream_id] = self._sync_counts.get(stream_id, 0) + len(objects)
                now_log = time.time()
                last_log = self._last_log_at.get(stream_id, 0)
                if now_log - last_log >= self._log_interval_sec:
                    algo = self._dispatcher.get_active_slug(stream_id) or "none"
                    logger.info(
                        "[%s] algo=%s | synced_objects=%d | detections=%d",
                        stream_id, algo, self._sync_counts[stream_id], len(detections),
                    )
                    self._sync_counts[stream_id] = 0
                    self._last_log_at[stream_id] = now_log

                result = self._dispatcher.run(stream_id, frame, detections, params)

                await self._emit_frame(stream_id, result.annotated_frame, result.metrics)

                now = time.time()
                if now - last_stats_at >= self._stats_interval_sec:
                    last_stats_at = now
                    # Inject active algorithm so frontend can render dynamic metrics
                    result.metrics["algorithm"] = self._dispatcher.get_active_slug(stream_id) or "heatmap"
                    await self._emit_stats(stream_id, result.metrics)

                # FPS Pacing Sleep
                loop_elapsed = time.time() - loop_start
                sleep_time = max(0, frame_time - loop_elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("[%s] Pipeline loop error", stream_id)
                await asyncio.sleep(0.5)

        logger.info("[%s] Pipeline task exited", stream_id)

    def _build_params(self, stream_id: str, detections, frame: np.ndarray | None = None) -> dict:
        """Assemble the params dict that the active analyzer expects."""
        params = dict(self._zone_repo.get(stream_id, {}))

        # Scale roi_polygon from config resolution to actual frame resolution
        if "roi_polygon" in params and frame is not None:
            config_res = params.pop("roi_config_resolution", None)
            if config_res:
                from app.infrastructure.config.stream_profiles import scale_polygon
                frame_h, frame_w = frame.shape[:2]
                params["roi_polygon"] = scale_polygon(
                    params["roi_polygon"],
                    src_res=tuple(config_res),
                    dst_res=(frame_w, frame_h),
                )

        try:
            tracker_present = (
                hasattr(detections, "tracker_id")
                and detections.tracker_id.size > 0
                and int(detections.tracker_id.max()) != -1
            )
        except Exception:
            tracker_present = False
        params["tracker_present"] = tracker_present

        active_model = self._model_registry.active_model_name
        if active_model:
            try:
                labels = self._model_registry.get_labels(active_model)
                params["labels_map"] = {i: name for i, name in enumerate(labels)}
            except ValueError:
                params["labels_map"] = {}
        return params

    async def _emit_frame(self, stream_id: str, frame: np.ndarray, metrics: dict) -> None:
        for sub in list(self._frame_subs):
            try:
                await sub(stream_id, frame, metrics)
            except Exception:
                logger.exception("Frame subscriber failed for stream %s", stream_id)

    async def _emit_stats(self, stream_id: str, metrics: dict) -> None:
        for sub in list(self._stats_subs):
            try:
                await sub(stream_id, metrics)
            except Exception:
                logger.exception("Stats subscriber failed for stream %s", stream_id)
