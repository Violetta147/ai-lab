"""
C2 Center Backend — Camera Database Service

Manages persistent camera configurations using SQLite.
Each camera has: stream_id, rtsp_url, name, description, enabled, created_at
"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Database location (backend root)
DB_PATH = Path(__file__).parent / "c2_cameras.db"


class CameraDatabase:
    """SQLite database for managing camera sources."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create cameras table
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
        """Add a new camera source."""
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

        return self._row_to_dict(row)

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

        return [self._row_to_dict(row) for row in rows]

    def update_camera(self, stream_id: str, **kwargs) -> dict:
        """Update camera fields (rtsp_url, name, description, enabled)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Validate that the camera exists
        cursor.execute("SELECT * FROM cameras WHERE stream_id = ?", (stream_id,))
        if not cursor.fetchone():
            conn.close()
            raise ValueError(f"Camera '{stream_id}' not found")

        # Build update query
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
        """Delete a camera by stream_id."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM cameras WHERE stream_id = ?", (stream_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()

        if deleted:
            logger.info("Camera deleted: %s", stream_id)
        return deleted

    def _row_to_dict(self, row: tuple) -> dict:
        """Convert a database row to a dictionary."""
        return {
            "stream_id": row[0],
            "rtsp_url": row[1],
            "name": row[2],
            "description": row[3],
            "enabled": bool(row[4]),
            "created_at": row[5],
            "updated_at": row[6],
        }

    # Note: DB seeding has been removed. Cameras should be created via
    # the Cameras API or the `manage_cameras.ps1` helper.


# Singleton instance
camera_db = CameraDatabase()
