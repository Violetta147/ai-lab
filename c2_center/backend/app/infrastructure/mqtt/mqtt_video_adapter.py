import asyncio
import base64
import json
import logging
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
        
        # Buffer to store the latest frame for each stream: {stream_id: (frame, timestamp)}
        self._latest_frames: dict[str, tuple[Any, float]] = {}

    def connect(self):
        self.client.connect_async(self.broker, self.port)
        self.client.loop_start()

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

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
        try:
            payload = json.loads(msg.payload.decode())
            camera_id = payload["camera_id"]
            timestamp = payload["timestamp"]
            b64_img = payload["frame"]
            
            # Decode b64 to cv2 MatLike
            img_bytes = base64.b64decode(b64_img)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                self._latest_frames[camera_id] = (frame, timestamp)
        except Exception as e:
            logger.error(f"Error parsing MQTT video msg: {e}")

    def get_closest_frame(self, stream_id: str, timestamp: float, max_latency: float = 1.0) -> tuple[Any, float] | None:
        """Protocol match: returns the exact frame matching the timestamp (or closest)."""
        latest = self._latest_frames.get(stream_id)
        if not latest:
            return None
        frame, frame_ts = latest
        
        # In live streaming over MQTT, we might just return the latest frame if it's recent enough
        diff = abs(frame_ts - timestamp)
        if diff <= max_latency:
            return (frame, frame_ts)
        return None

    def get_stream_ids(self) -> list[str]:
        return list(self._latest_frames.keys())

    def is_stream_connected(self, stream_id: str) -> bool:
        return self._connected and stream_id in self._latest_frames
