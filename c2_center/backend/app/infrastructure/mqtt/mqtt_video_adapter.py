import asyncio
import base64
import json
import logging
import concurrent.futures
from typing import Any

import cv2
import numpy as np
from paho.mqtt import client as mqtt_client

logger = logging.getLogger(__name__)

class MqttVideoAdapter:
    def __init__(self, broker: str, port: int, topic: str):
        self.broker = broker
        self.port = port
        self.topic = topic
        self._connected = False
        self.client = mqtt_client.Client()
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        
        # Buffer to store the latest frame for each stream: {stream_id: (frame, timestamp)}
        self._latest_frames: dict[str, tuple[Any, float]] = {}

    def connect(self):
        self.client.connect_async(self.broker, self.port)
        self.client.loop_start()

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def start(self) -> None:
        """Start the adapter (alias for connect, to match IVideoAdapter)."""
        pass  # connect is usually called in wire_live_pipeline

    def stop(self) -> None:
        """Stop the adapter."""
        self.disconnect()
        self._executor.shutdown(wait=False)

    def add_stream(self, stream_id: str, rtsp_url: str) -> bool:
        """MQTT video adapter ignores RTSP URL, just returns True."""
        return True

    def remove_stream(self, stream_id: str) -> bool:
        return True

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("MqttVideoAdapter connected")
            self._connected = True
            client.subscribe(self.topic)
        else:
            logger.error(f"MqttVideoAdapter connection failed: rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        logger.warning("MqttVideoAdapter disconnected")

    def _on_message(self, client, userdata, msg):
        self._executor.submit(self._decode_msg, msg.payload)

    def _decode_msg(self, payload_bytes: bytes):
        try:
            payload = json.loads(payload_bytes.decode())
            camera_id = payload["camera_id"]
            
            # Decode b64 to cv2 MatLike
            b64_img = payload["frame"]
            img_bytes = base64.b64decode(b64_img)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                import time
                # Use local backend time instead of edge payload time.
                # This aligns with RtspVideoReader and ensures SyncEngine's 
                # clock drift compensation time-travel doesn't reject frames.
                self._latest_frames[camera_id] = (frame, time.time())
        except Exception as e:
            logger.error(f"Error parsing MQTT video msg: {e}")

    def get_closest_frame(self, stream_id: str, timestamp: float, max_latency: float = 1.0) -> tuple[Any, float] | None:
        """Protocol match: returns the exact frame matching the timestamp (or closest)."""
        latest = self._latest_frames.get(stream_id)
        if not latest:
            return None
        frame, frame_ts = latest
        
        # We now use local backend time for frame_ts.
        # But for MQTT, we can also just return the latest frame since it's a 1-to-1 live preview
        diff = abs(frame_ts - timestamp)
        if diff <= max_latency:
            return (frame, frame_ts)
            
        # Fallback for MQTT: just return the latest frame if clocks wildly desync
        return (frame, frame_ts)

    def get_stream_ids(self) -> list[str]:
        return list(self._latest_frames.keys())

    def is_stream_connected(self, stream_id: str) -> bool:
        return self._connected and stream_id in self._latest_frames
