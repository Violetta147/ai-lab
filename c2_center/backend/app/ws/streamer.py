"""
WebSocket transport for live frames and stats.

Listens for `(stream_id, frame, metrics)` events from the pipeline manager
and broadcasts them to subscribed WebSocket clients. This module is
transport-only: no analytics, no synchronization, no video decoding.
"""

import asyncio
import logging

import numpy as np

from app.core.config import settings
from app.infrastructure.encoding.jpeg import frame_to_base64

logger = logging.getLogger(__name__)


class WsStreamer:
    """Maintains per-stream WebSocket client sets and fans out events to them."""

    def __init__(self) -> None:
        self._video_clients: dict[str, set] = {}
        self._stats_clients: dict[str, set] = {}

    def register_stream(self, stream_id: str) -> None:
        """Ensure client sets exist for this stream."""
        self._video_clients.setdefault(stream_id, set())
        self._stats_clients.setdefault(stream_id, set())

    def unregister_stream(self, stream_id: str) -> None:
        """Drop all client tracking for a removed stream."""
        self._video_clients.pop(stream_id, None)
        self._stats_clients.pop(stream_id, None)

    def add_video_client(self, stream_id: str, ws) -> None:
        self._video_clients.setdefault(stream_id, set()).add(ws)

    def remove_video_client(self, stream_id: str, ws) -> None:
        self._video_clients.get(stream_id, set()).discard(ws)

    def add_stats_client(self, stream_id: str, ws) -> None:
        self._stats_clients.setdefault(stream_id, set()).add(ws)

    def remove_stats_client(self, stream_id: str, ws) -> None:
        self._stats_clients.get(stream_id, set()).discard(ws)

    async def on_frame(self, stream_id: str, frame: np.ndarray, _metrics: dict) -> None:
        """PipelineManager subscriber — broadcast a JPEG-encoded frame."""
        clients = self._video_clients.get(stream_id)
        if not clients:
            return
        b64 = await asyncio.to_thread(frame_to_base64, frame, settings.WS_JPEG_QUALITY)
        await self._broadcast(clients, {"type": "frame", "data": b64})

    async def on_stats(self, stream_id: str, metrics: dict) -> None:
        """PipelineManager subscriber — broadcast a metrics snapshot."""
        clients = self._stats_clients.get(stream_id)
        if not clients:
            return
        await self._broadcast(clients, {"type": "stats", "data": metrics})

    @staticmethod
    async def _broadcast(clients: set, payload: dict) -> None:
        """Send `payload` to every client; drop the ones that fail."""
        dead: set = set()
        # Iterate over a copy to tolerate concurrent disconnects.
        for ws in list(clients):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)
        if dead:
            clients -= dead
