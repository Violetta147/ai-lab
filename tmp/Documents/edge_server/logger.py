from __future__ import annotations

from .config import CAMERA_ID


def log(message: str) -> None:
    # Centralized log prefix to keep messages consistent.
    print(f"[EDGE][{CAMERA_ID}] {message}")

