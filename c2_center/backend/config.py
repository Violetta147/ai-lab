"""
C2 Center Backend — Configuration (Pydantic Settings)

All settings can be overridden via environment variables or a .env file.
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    # --- Kafka ---
    KAFKA_BOOTSTRAP: str = "localhost:9092"
    KAFKA_TOPIC: str = "c2_metadata"
    KAFKA_GROUP_ID: str = "c2_backend"

    # --- RTSP Streams ---
    # RTSP streams are managed dynamically via the camera database.
    # Legacy static `RTSP_STREAMS` configuration has been removed.

    # --- Models ---
    # Backend scans this directory for model subdirectories
    # Each subdirectory must contain: weights file (.pt or .onnx) + labels.txt
    MODELS_DIR: Path = Path(__file__).parent / "models"

    # --- Sync Engine ---
    SYNC_TOLERANCE_MS: float = 50.0
    VIDEO_QUEUE_MAXSIZE: int = 30

    # --- WebSocket ---
    WS_TARGET_FPS: int = 15
    WS_JPEG_QUALITY: int = 75

    # --- Server ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    WS_PORT: int = 8001

    # (No additional behavior flags)

    model_config = {"env_prefix": "C2_", "env_file": ".env", "extra": "ignore"}


# Singleton instance
settings = Settings()
