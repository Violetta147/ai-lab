import json
import time
from paho.mqtt import client as mqtt_client
from pipeline.config import MQTT_BROKER, MQTT_PORT, MQTT_TOPIC, MQTT_QOS, MQTT_CLIENT_ID
from pipeline.utils.db_handler import DBHandler


class MQTTHandler:
    def __init__(self, db_handler: DBHandler):
        self.db_handler = db_handler
        # clean_session=True: Không giữ lại message cũ, tránh xử lý lại dữ liệu
        # khi service restart
        self.client = mqtt_client.Client(client_id=MQTT_CLIENT_ID, clean_session=True)
        self.client.reconnect_delay_set(min_delay=1, max_delay=60)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            print(f"❌ [MQTT] Connection failed rc={rc}")
            return
        print(f"✅ [MQTT] Connected to {MQTT_BROKER}:{MQTT_PORT}")
        # Subscribe lại mỗi khi reconnect (quan trọng!)
        client.subscribe(MQTT_TOPIC, qos=MQTT_QOS)
        print(f"📥 [MQTT] Subscribed to {MQTT_TOPIC}")

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print(f"⚠️ [MQTT] Unexpected disconnect (rc={rc}). Auto-reconnecting...")
        else:
            print(f"🔌 [MQTT] Disconnected cleanly.")

    def _on_message(self, client, userdata, message):
        try:
            raw_text = message.payload.decode("utf-8")
        except UnicodeDecodeError as e:
            print(f"❌ [MQTT] Failed to decode message payload: {e}")
            return

        print(f"📩 [MQTT] Got message on topic: {message.topic}")
        try:
            data = json.loads(raw_text)

            # Validate các trường bắt buộc
            image_url = str(data.get("image_url", ""))
            if not image_url:
                print("⚠️ [MQTT] Skipping message: missing 'image_url'")
                return

            payload = {
                "camera_id": str(data.get("camera_id", "unknown")),
                "image_url": image_url,
                "timestamp": float(data.get("timestamp", time.time())),
                "trigger_reason": str(data.get("trigger_reason", "")),
                "edge_predictions": data.get("detections", []),
            }

            self.db_handler.insert_with_retry(payload)
            print(
                f"📝 [DB] Recorded 1 detection from {payload['camera_id']} "
                f"with {len(payload['edge_predictions'])} objects."
            )
        except json.JSONDecodeError as e:
            print(f"❌ [MQTT] Invalid JSON payload: {e}")
        except Exception as exc:
            print(f"❌ [MQTT] Error processing message: {exc}")

    def run(self):
        print(f"🚀 [MQTT] Attempting to connect to {MQTT_BROKER}:{MQTT_PORT}...")
        self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        self.client.loop_forever()
