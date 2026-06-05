import os

# ================= CELERY CONFIG =================
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# ================= MINIO CONFIG =================
MINIO_URL = os.getenv("MINIO_URL", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadminpassword")
MINIO_SECURE = False

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
CVAT_PASS = os.getenv("CVAT_PASS", "Rmr2612+")
CVAT_PROJECT_ID = os.getenv("CVAT_PROJECT_ID", "1")

# ================= TELEGRAM ALERT =================
TELEGRAM_TOKEN = "8657283198:AAFc2P75rdlPPBEm9ID-N0jV25YMXX487jY"
TELEGRAM_CHAT_ID = "5994574529"
BOT_NAME = "TraffiJetsonAlertBot"

# ================= AUTOMATION THRESHOLDS =================
SYNC_BATCH_THRESHOLD = 20  # Gom đủ 20 ảnh mới tạo Task CVAT
TRAIN_DATA_THRESHOLD = 100 # Cảnh báo nếu số file nhãn vượt 100

# ================= MQTT CONFIG =================
MQTT_BROKER = os.getenv("MQTT_BROKER", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "traffic/detections")
MQTT_QOS = 1
MQTT_CLIENT_ID = f"server_subscriber_{os.getpid()}"

# ================= DB CONFIG =================
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "traffic_db")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password123")
DB_TABLE = os.getenv("DB_TABLE", "detections")
DB_RETRY_MAX_ATTEMPTS = 5
DB_RETRY_BASE_SECONDS = 1.0

# ================= PROJECT CONFIG =================
YOLO_CLASSES = ["Bus", "Car", "Motor", "Truck"]
MODEL_PATH = "pipeline/model/yolo26x.pt"
EDGE_MODEL_PATH = "pipeline/model/best_v8n_pruned.pt"

WORK_DIR = "./cvat_temp"
IMG_DIR = os.path.join(WORK_DIR, "images")
LBL_DIR = os.path.join(WORK_DIR, "labels")

IMG_ZIP = os.path.join(WORK_DIR, "images.zip")
ANN_ZIP = os.path.join(WORK_DIR, "annotations.zip")

# Ensure directories exist
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(LBL_DIR, exist_ok=True)
