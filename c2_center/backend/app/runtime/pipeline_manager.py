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

                frame, objects = await self._sync.get_synced_frame(stream_id)
                if frame is None:
                    await asyncio.sleep(0.05)
                    continue

                detections = metadata_to_detections(objects)
                params = self._build_params(stream_id, detections)
                result = self._dispatcher.run(stream_id, frame, detections, params)

                await self._emit_frame(stream_id, result.annotated_frame, result.metrics)

                now = time.time()
                if now - last_stats_at >= self._stats_interval_sec:
                    last_stats_at = now
                    await self._emit_stats(stream_id, result.metrics)

                elapsed = time.time() - t0
                if elapsed < interval:
                    await asyncio.sleep(interval - elapsed)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("[%s] Pipeline loop error", stream_id)
                await asyncio.sleep(0.5)

        logger.info("[%s] Pipeline task exited", stream_id)

    def _build_params(self, stream_id: str, detections) -> dict:
        """Assemble the params dict that the active analyzer expects."""
        params = dict(self._zone_repo.get(stream_id, {}))

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
