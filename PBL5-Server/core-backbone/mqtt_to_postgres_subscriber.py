import json
import os
import re
import time
from typing import TypedDict, List
import psycopg2
from paho.mqtt import client as mqtt_client

# ================= CONFIG (Ưu tiên Docker Env) =================
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt")  # Mặc định là 'mqtt' trong docker
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "traffic/detections")
MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", f"subscriber_{int(time.time())}")

DB_HOST = os.getenv("DB_HOST", "db")  # Mặc định là 'db' trong docker
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "traffic_db")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password123")

# Validate tên bảng (chống SQL injection qua env var)
_raw_table = os.getenv("DB_TABLE", "detections")
if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', _raw_table):
    raise ValueError(f"DB_TABLE chứa ký tự không hợp lệ: {_raw_table!r}")
DB_TABLE = _raw_table

DB_MAX_RETRIES = 10
DB_RETRY_WAIT = 3  # giây

# ================= DATA TYPES =================
class DetectionPayload(TypedDict):
    camera_id: str
    image_url: str
    timestamp: float
    trigger_reason: str
    edge_predictions: List[dict]

# ================= DATABASE HANDLER =================
class DBHandler:
    def __init__(self):
        self.conn = None

    def connect(self):
        """Kết nối (hoặc reconnect) tới PostgreSQL."""
        print(f"🐘 [DB] Connecting to {DB_NAME} at {DB_HOST}:{DB_PORT}...")
        try:
            self.conn = psycopg2.connect(
                host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
                user=DB_USER, password=DB_PASSWORD,
                connect_timeout=10,
            )
            self.conn.autocommit = True
            print("✅ [DB] Connected successfully.")
        except Exception as e:
            self.conn = None
            print(f"❌ [DB] Connection failed: {e}")
            raise

    def _ensure_connection(self):
        """Đảm bảo connection sống. Auto-reconnect nếu cần."""
        if self.conn and not self.conn.closed:
            return
        self.connect()

    def insert(self, p: DetectionPayload):
        sql = f"""
        INSERT INTO {DB_TABLE} (
            camera_id, image_url, "timestamp", trigger_reason, status, edge_predictions
        ) VALUES (%s, %s, to_timestamp(%s), %s, 'NEW', %s)
        """
        try:
            self._ensure_connection()
            with self.conn.cursor() as cur:
                cur.execute(sql, (
                    p["camera_id"], p["image_url"], p["timestamp"],
                    p["trigger_reason"], json.dumps(p["edge_predictions"])
                ))
        except Exception as e:
            print(f"❌ [DB] Insert error: {e}")
            self.conn = None  # Reset connection cho lần retry tiếp

# ================= MQTT HANDLER =================
class MQTTHandler:
    def __init__(self, db: DBHandler):
        self.db = db
        # Tương thích paho-mqtt 2.0
        try:
            self.client = mqtt_client.Client(
                mqtt_client.CallbackAPIVersion.VERSION1, MQTT_CLIENT_ID
            )
        except AttributeError:
            self.client = mqtt_client.Client(MQTT_CLIENT_ID)

        self.client.reconnect_delay_set(min_delay=1, max_delay=60)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"📡 [MQTT] Connected to broker at {MQTT_BROKER}:{MQTT_PORT}")
            client.subscribe(MQTT_TOPIC, qos=MQTT_QOS)
            print(f"📥 [MQTT] Subscribed to {MQTT_TOPIC}")
        else:
            print(f"❌ [MQTT] Connection failed with code {rc}")

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print(f"⚠️ [MQTT] Unexpected disconnect (rc={rc}). Auto-reconnecting...")
        else:
            print("🔌 [MQTT] Disconnected cleanly.")

    def on_message(self, client, userdata, msg):
        try:
            payload_str = msg.payload.decode("utf-8")
        except UnicodeDecodeError as e:
            print(f"❌ [MQTT] Cannot decode payload: {e}")
            return

        # Chỉ xử lý topic chúng ta cần
        if msg.topic != MQTT_TOPIC:
            return

        try:
            data = json.loads(payload_str)

            # Validate trường bắt buộc
            image_url = str(data.get("image_url", ""))
            if not image_url:
                print("⚠️ [MQTT] Skipping message: missing 'image_url'")
                return

            payload: DetectionPayload = {
                "camera_id": str(data.get("camera_id", "unknown")),
                "image_url": image_url,
                "timestamp": float(data.get("timestamp", time.time())),
                "trigger_reason": str(data.get("trigger_reason", "")),
                "edge_predictions": data.get("detections", []),
            }
            self.db.insert(payload)
            print(f"📝 [DB] Recorded 1 detection from {payload['camera_id']}")

        except json.JSONDecodeError as e:
            print(f"⚠️ [MQTT] Invalid JSON payload: {e}")
        except Exception as e:
            print(f"⚠️ [MQTT] Message processing error: {e}")

    def run(self):
        import socket
        try:
            mqtt_ip = socket.gethostbyname(MQTT_BROKER)
            print(f"🔍 [DNS] '{MQTT_BROKER}' resolved to IP: {mqtt_ip}")
        except Exception as e:
            print(f"⚠️ [DNS] Could not resolve '{MQTT_BROKER}': {e}")

        print(f"🚀 [MQTT] Attempting to connect to {MQTT_BROKER}...")
        self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        self.client.loop_forever()

# ================= MAIN =================
if __name__ == "__main__":
    db = DBHandler()

    # Retry kết nối DB (chờ Docker container sẵn sàng)
    for i in range(DB_MAX_RETRIES):
        try:
            db.connect()
            break
        except Exception:
            wait = DB_RETRY_WAIT * (i + 1)
            print(f"⏳ Waiting for DB... (attempt {i + 1}/{DB_MAX_RETRIES}, retry in {wait}s)")
            time.sleep(wait)
    else:
        print(f"❌ Could not connect to DB after {DB_MAX_RETRIES} attempts. Exiting.")
        exit(1)

    mqtt = MQTTHandler(db)
    mqtt.run()
