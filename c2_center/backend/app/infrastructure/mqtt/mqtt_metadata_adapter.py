import asyncio
import json
import logging
from collections import deque

from paho.mqtt import client as mqtt_client

logger = logging.getLogger(__name__)

class MqttMetadataAdapter:
    def __init__(self, broker: str, port: int, topic: str):
        self.broker = broker
        self.port = port
        self.topic = topic
        self._connected = False
        self.client = mqtt_client.Client()
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        # Buffer to store metadata per stream
        self._queues: dict[str, deque] = {}

    def connect(self):
        self.client.connect_async(self.broker, self.port)
        self.client.loop_start()

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("MqttMetadataAdapter connected")
            self._connected = True
            client.subscribe(self.topic)
        else:
            logger.error(f"MqttMetadataAdapter connection failed: rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        logger.warning("MqttMetadataAdapter disconnected")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            camera_id = payload.get("camera_id")
            if camera_id:
                if camera_id not in self._queues:
                    self._queues[camera_id] = deque(maxlen=50)
                self._queues[camera_id].append(payload)
        except Exception as e:
            logger.error(f"Error parsing MQTT metadata msg: {e}")

    async def pop_latest(self, stream_id: str) -> dict | None:
        """Protocol match: returns the oldest available metadata in the queue for this tick."""
        if stream_id in self._queues and self._queues[stream_id]:
            return self._queues[stream_id].popleft()
        return None

    @property
    def is_connected(self) -> bool:
        return self._connected
