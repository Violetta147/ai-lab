"""
Heartbeat monitor: periodically checks DB-configured cameras for RTSP reachability
and only calls `video_reader.add_stream()` when the camera is reachable. Keeps logic
minimal and focused: try quick connect, add stream on success, remove streams that
are disabled in DB.
"""

import logging
import threading
import time

import cv2

from services.camera_db import camera_db

logger = logging.getLogger(__name__)


class HeartbeatMonitor:
    def __init__(self, video_reader, poll_interval: float = 5.0, connect_timeout: float = 3.0):
        self.video_reader = video_reader
        self.poll_interval = poll_interval
        self.connect_timeout = connect_timeout
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="heartbeat-monitor")

    def start(self):
        logger.info("Starting HeartbeatMonitor")
        self._stop_event.clear()
        if not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, daemon=True, name="heartbeat-monitor")
            self._thread.start()

    def stop(self):
        logger.info("Stopping HeartbeatMonitor")
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _try_connect(self, rtsp_url: str) -> bool:
        """Attempt a quick RTSP open + one frame read. Non-blocking-ish (bounded by timeout)."""
        try:
            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
            start = time.time()
            while time.time() - start < self.connect_timeout:
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        cap.release()
                        return True
                time.sleep(0.2)
            if cap:
                cap.release()
        except Exception:
            logger.exception("Heartbeat connect check failed for %s", rtsp_url)
        return False

    def _run(self):
        while not self._stop_event.is_set():
            try:
                # Add streams: enabled in DB but not yet in video_reader
                cams = camera_db.list_cameras(enabled_only=True)
                desired_ids = {c["stream_id"] for c in cams}
                current_ids = set(self.video_reader.get_stream_ids())

                for cam in cams:
                    sid = cam["stream_id"]
                    url = cam["rtsp_url"]
                    if sid in current_ids:
                        continue

                    logger.debug("Heartbeat: trying %s -> %s", sid, url)
                    if self._try_connect(url):
                        added = self.video_reader.add_stream(sid, url)
                        if added:
                            logger.info("Heartbeat: stream added: %s", sid)

                # Remove streams that are running but disabled in DB
                for sid in list(current_ids):
                    if sid not in desired_ids:
                        logger.info("Heartbeat: removing stream not enabled in DB: %s", sid)
                        self.video_reader.remove_stream(sid)

            except Exception:
                logger.exception("Heartbeat monitor error")

            # Sleep until next poll
            self._stop_event.wait(self.poll_interval)
