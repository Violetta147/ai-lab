"""
C2 Center backend configuration (Pydantic Settings).

All settings can be overridden via environment variables (prefix C2_) or a .env file.
"""

from pathlib import Path

from pydantic_settings import BaseSettings

# Resolve repository-relative directories once.
# This file is at: c2_center/backend/app/core/config.py
# parents[0] = core, parents[1] = app, parents[2] = backend, parents[3] = c2_center
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_APP_DIR = Path(__file__).resolve().parents[1]
_C2_CENTER_DIR = _BACKEND_DIR.parent  # c2_center/
_SQLITE_DIR = _APP_DIR / "storage" / "sqlite"


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    # --- Kafka ---
    KAFKA_BOOTSTRAP: str = "localhost:9092"
    KAFKA_TOPIC: str = "c2_metadata"
    KAFKA_GROUP_ID: str = "c2_backend"

    # --- Metadata source ---
    # "kafka" = DeepStream via Kafka (default)
    # "mqtt"  = data_pipeline tracking bridge via MQTT
    METADATA_SOURCE: str = "mqtt"

    # --- MQTT consumer (active when METADATA_SOURCE=mqtt) ---
    MQTT_BROKER: str = "127.0.0.1"
    MQTT_PORT: int = 1883
    MQTT_TOPIC: str = "traffic/tracked"
    MQTT_QOS: int = 1
    MQTT_CLIENT_ID: str = "c2_center_mqtt"

    # --- Models ---
    # Backend scans this directory for model subdirectories.
    # Each subdirectory must contain: weights file (.pt or .onnx) + labels.txt
    MODELS_DIR: Path = _BACKEND_DIR / "ml_models"

    # --- Sync Engine ---
    SYNC_TOLERANCE_MS: float = 100.0
    VIDEO_QUEUE_MAXSIZE: int = 20

    # --- WebSocket ---
    WS_TARGET_FPS: int = 15
    WS_JPEG_QUALITY: int = 75

    # --- Server ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    WS_PORT: int = 8001

    # --- Persistence ---
    CAMERA_DB_PATH: Path = _SQLITE_DIR / "c2_cameras.db"
    ZONE_DB_PATH: Path = _SQLITE_DIR / "zone_store.db"
    STREAM_PROFILES_PATH: Path = _C2_CENTER_DIR / "config" / "stream_profiles.json"

    model_config = {"env_prefix": "C2_", "env_file": ".env", "extra": "ignore"}


# Singleton instance
settings = Settings()
