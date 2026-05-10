"""
RTSP video reader.

Maintains one daemon thread per stream pulling frames via cv2.VideoCapture
and pushing (frame, timestamp) into bounded per-stream queues. Each thread
auto-reconnects with exponential backoff on failure.
"""

import logging
import queue
import threading
import time

import cv2
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class RtspVideoReader:
    """
    Multi-stream RTSP video reader.

    One daemon thread per stream. Each thread pulls frames from RTSP
    and pushes them into a bounded queue. Auto-reconnects on failure.
    """

    def __init__(self) -> None:
        # stream_id -> Queue of (frame: np.ndarray, timestamp: float)
        self.queues: dict[str, queue.Queue] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._running = False

    def start(self) -> None:
        """Mark service running. Streams are added later via `add_stream()`."""
        self._running = True
        logger.info("RTSP video reader started (waiting for streams)")

    def stop(self) -> None:
        """Signal all reader threads to stop on their next loop iteration."""
        self._running = False
        logger.info("RTSP video reader stopping...")

    def _reader_loop(
        self, stream_id: str, rtsp_url: str, q: queue.Queue
    ) -> None:
        """Reader loop for a single stream — runs in its own thread."""
        cap = None
        reconnect_delay = 1.0
        retry_count = 0

        while self._running:
            if stream_id not in self.queues:
                logger.info("[%s] Stream removed, stopping reader loop", stream_id)
                break

            if retry_count >= 3:
                logger.error("[%s] Max connection retries reached (3). Stopping reader thread.", stream_id)
                self.queues.pop(stream_id, None)
                self._threads.pop(stream_id, None)
                break

            try:
                if cap is None or not cap.isOpened():
                    logger.info("[%s] Connecting to %s...", stream_id, rtsp_url)
                    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
                    if not cap.isOpened():
                        retry_count += 1
                        logger.warning(
                            "[%s] Cannot open %s, retrying in %.0fs (Attempt %d/3)",
                            stream_id,
                            rtsp_url,
                            reconnect_delay,
                            retry_count
                        )
                        time.sleep(reconnect_delay)
                        reconnect_delay = min(reconnect_delay * 2, 10.0)
                        continue

                    logger.info("[%s] Connected.", stream_id)
                    reconnect_delay = 1.0
                    retry_count = 0

                ret, frame = cap.read()
                if not ret or frame is None:
                    retry_count += 1
                    logger.warning("[%s] Read failed, reconnecting... (Attempt %d/3)", stream_id, retry_count)
                    cap.release()
                    cap = None
                    time.sleep(0.5)
                    continue
                
                retry_count = 0

                timestamp = time.time()

                try:
                    q.put_nowait((frame, timestamp))
                except queue.Full:
                    try:
                        q.get_nowait()  # drop oldest
                    except queue.Empty:
                        pass
                    q.put_nowait((frame, timestamp))

            except Exception:
                retry_count += 1
                logger.exception("[%s] Reader loop error (Attempt %d/3)", stream_id, retry_count)
                if cap is not None:
                    cap.release()
                    cap = None
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 10.0)

        if cap is not None:
            cap.release()
        logger.info("[%s] Reader thread exited.", stream_id)

    def get_frame(
        self, stream_id: str, timeout: float = 1.0
    ) -> tuple[np.ndarray, float] | None:
        """Get the latest frame from a stream's queue."""
        q = self.queues.get(stream_id)
        if q is None:
            return None
        try:
            return q.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_stream_ids(self) -> list[str]:
        """Return list of configured stream IDs."""
        return list(self.queues.keys())

    def is_stream_connected(self, stream_id: str) -> bool:
        """Check if a stream's thread is alive."""
        thread = self._threads.get(stream_id)
        return thread is not None and thread.is_alive()

    def add_stream(self, stream_id: str, rtsp_url: str) -> bool:
        """Dynamically add a new stream without restarting."""
        if stream_id in self.queues:
            logger.warning("Stream %s already exists", stream_id)
            return False

        if not self._running:
            logger.warning("RTSP reader not running")
            return False

        q = queue.Queue(maxsize=settings.VIDEO_QUEUE_MAXSIZE)
        self.queues[stream_id] = q

        thread = threading.Thread(
            target=self._reader_loop,
            args=(stream_id, rtsp_url, q),
            daemon=True,
            name=f"video-{stream_id}",
        )
        thread.start()
        self._threads[stream_id] = thread
        logger.info("Stream added dynamically: %s -> %s", stream_id, rtsp_url)
        return True

    def remove_stream(self, stream_id: str) -> bool:
        """Dynamically remove a stream — its reader thread exits next cycle."""
        if stream_id not in self.queues:
            logger.warning("Stream %s not found", stream_id)
            return False

        self.queues.pop(stream_id, None)
        self._threads.pop(stream_id, None)
        logger.info("Stream marked for removal: %s (will stop on next cycle)", stream_id)
        return True
