"""
Stream lifecycle owner.

Tracks which stream IDs are currently active in the system and exposes
hooks so the pipeline manager can react to add/remove events. This module
deliberately knows nothing about analytics or transport — it only owns
"does stream X exist right now?" plus the registration callbacks.
"""

import logging
from typing import Callable

logger = logging.getLogger(__name__)

StreamLifecycleListener = Callable[[str], None]


class StreamManager:
    """Owns the canonical set of active stream IDs."""

    def __init__(self) -> None:
        self._streams: set[str] = set()
        self._on_add: list[StreamLifecycleListener] = []
        self._on_remove: list[StreamLifecycleListener] = []

    def on_add(self, listener: StreamLifecycleListener) -> None:
        """Register a callback fired after a new stream is added."""
        self._on_add.append(listener)

    def on_remove(self, listener: StreamLifecycleListener) -> None:
        """Register a callback fired after a stream is removed."""
        self._on_remove.append(listener)

    def add_stream(self, stream_id: str) -> bool:
        """Register a new stream. Returns False if it was already registered."""
        if stream_id in self._streams:
            return False
        self._streams.add(stream_id)
        logger.info("Stream registered: %s", stream_id)
        for listener in self._on_add:
            try:
                listener(stream_id)
            except Exception:
                logger.exception("on_add listener failed for stream %s", stream_id)
        return True

    def remove_stream(self, stream_id: str) -> bool:
        """Unregister a stream. Returns False if it was not registered."""
        if stream_id not in self._streams:
            return False
        self._streams.discard(stream_id)
        logger.info("Stream unregistered: %s", stream_id)
        for listener in self._on_remove:
            try:
                listener(stream_id)
            except Exception:
                logger.exception("on_remove listener failed for stream %s", stream_id)
        return True

    def has(self, stream_id: str) -> bool:
        return stream_id in self._streams

    def all_streams(self) -> list[str]:
        return sorted(self._streams)
