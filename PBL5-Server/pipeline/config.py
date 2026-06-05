import os
import re

# ================= CELERY CONFIG =================
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# ================= MINIO CONFIG =================
MINIO_URL = os.getenv("MINIO_URL", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadminpassword")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# Buckets
BUCKET_RAW_DATA = "raw-data"
BUCKET_PSEUDO_LABELS = "pseudo-labels"
BUCKET_ARCHIVED_IMAGES = "archived-images"
BUCKET_ARCHIVED_LABELS = "archived-labels"
BUCKET_LABELED_DATA = "labeled-data"
BUCKET_MODEL_UPDATES = "model-updates"

# ================= CVAT CONFIG =================
CVAT_URL = os.getenv("CVAT_URL", "http://host.docker.internal:8080")
CVAT_USER = os.getenv("CVAT_USER", "django")
CVAT_PASS = os.getenv("CVAT_PASS", "changeme")
CVAT_PROJECT_ID = os.getenv("CVAT_PROJECT_ID", "1")

# ================= TELEGRAM ALERT =================
# Tất cả secrets phải được cấu hình qua env var, KHÔNG hardcode
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
BOT_NAME = os.getenv("BOT_NAME", "TraffiJetsonAlertBot")

# ================= AUTOMATION THRESHOLDS =================
SYNC_BATCH_THRESHOLD = int(os.getenv("SYNC_BATCH_THRESHOLD", "20"))
TRAIN_DATA_THRESHOLD = int(os.getenv("TRAIN_DATA_THRESHOLD", "100"))

# ================= MQTT CONFIG =================
MQTT_BROKER = os.getenv("MQTT_BROKER", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "traffic/detections")
MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))
MQTT_CLIENT_ID = f"server_subscriber_{os.getpid()}"

# ================= DB CONFIG =================
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "traffic_db")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password123")
DB_RETRY_MAX_ATTEMPTS = int(os.getenv("DB_RETRY_MAX_ATTEMPTS", "5"))
DB_RETRY_BASE_SECONDS = float(os.getenv("DB_RETRY_BASE_SECONDS", "1.0"))

# Validate tên bảng DB (chống SQL injection qua env var)
_raw_table = os.getenv("DB_TABLE", "detections")
if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', _raw_table):
    raise ValueError(f"DB_TABLE chứa ký tự không hợp lệ: {_raw_table!r}")
DB_TABLE = _raw_table

# ================= VALID STATUS VALUES =================
VALID_STATUSES = frozenset({"NEW", "INFERRED", "IN_CVAT", "LABELED", "TRAINED"})

# ================= PROJECT CONFIG =================
YOLO_CLASSES = ["Bus", "Car", "Motor", "Truck"]
MODEL_PATH = os.getenv("MODEL_PATH", "pipeline/model/yolo26x.pt")
EDGE_MODEL_PATH = os.getenv("EDGE_MODEL_PATH", "pipeline/model/best_v8n_pruned.pt")

WORK_DIR = os.getenv("WORK_DIR", "./cvat_temp")
IMG_DIR = os.path.join(WORK_DIR, "images")
LBL_DIR = os.path.join(WORK_DIR, "labels")

IMG_ZIP = os.path.join(WORK_DIR, "images.zip")
ANN_ZIP = os.path.join(WORK_DIR, "annotations.zip")

# Ensure directories exist
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(LBL_DIR, exist_ok=True)
