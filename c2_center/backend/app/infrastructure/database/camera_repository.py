"""
Camera repository — SQLite persistence for camera sources.

Each row maps to an `app.domain.camera.Camera` value object.
"""

import logging
import sqlite3
from datetime import datetime  # noqa: F401  (used implicitly via CURRENT_TIMESTAMP defaults)
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.domain.camera import Camera

logger = logging.getLogger(__name__)


class CameraRepository:
    """SQLite-backed repository for camera sources."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else settings.CAMERA_DB_PATH
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema if it doesn't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cameras (
                stream_id TEXT PRIMARY KEY,
                rtsp_url TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                enabled INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        conn.close()
        logger.info("Camera database initialized: %s", self.db_path)

    def add_camera(
        self,
        stream_id: str,
        rtsp_url: str,
        name: str,
        description: str = "",
        enabled: bool = True,
    ) -> dict:
        """Add a new camera source. Returns the created camera as a dict."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO cameras (stream_id, rtsp_url, name, description, enabled)
                VALUES (?, ?, ?, ?, ?)
                """,
                (stream_id, rtsp_url, name, description, 1 if enabled else 0),
            )
            conn.commit()
            logger.info("Camera added: %s (%s)", stream_id, rtsp_url)
            return self.get_camera(stream_id)
        except sqlite3.IntegrityError:
            raise ValueError(f"Camera with stream_id '{stream_id}' already exists")
        finally:
            conn.close()

    def get_camera(self, stream_id: str) -> Optional[dict]:
        """Get a camera by stream_id."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cameras WHERE stream_id = ?", (stream_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None
        return Camera.from_row(row).to_dict()

    def list_cameras(self, enabled_only: bool = False) -> list[dict]:
        """List all cameras (optionally only enabled ones)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        if enabled_only:
            cursor.execute("SELECT * FROM cameras WHERE enabled = 1 ORDER BY created_at")
        else:
            cursor.execute("SELECT * FROM cameras ORDER BY created_at")
        rows = cursor.fetchall()
        conn.close()
        return [Camera.from_row(row).to_dict() for row in rows]

    def update_camera(self, stream_id: str, **kwargs) -> dict:
        """Update camera fields (rtsp_url, name, description, enabled)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM cameras WHERE stream_id = ?", (stream_id,))
        if not cursor.fetchone():
            conn.close()
            raise ValueError(f"Camera '{stream_id}' not found")

        allowed_fields = {"rtsp_url", "name", "description", "enabled"}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            conn.close()
            return self.get_camera(stream_id)

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        query = f"UPDATE cameras SET {set_clause} WHERE stream_id = ?"
        values = list(updates.values()) + [stream_id]

        cursor.execute(query, values)
        conn.commit()
        conn.close()

        logger.info("Camera updated: %s", stream_id)
        return self.get_camera(stream_id)

    def delete_camera(self, stream_id: str) -> bool:
        """Delete a camera by stream_id. Returns True if a row was removed."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cameras WHERE stream_id = ?", (stream_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        if deleted:
            logger.info("Camera deleted: %s", stream_id)
        return deleted


# Singleton instance — used by API layer and runtime composition.
camera_repo = CameraRepository()
