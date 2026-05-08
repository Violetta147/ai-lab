"""Zone DB — lightweight SQLite-backed storage for ROI/lines.

Provides a dict-like `zone_store` object used by `api.zones` and `ws.streamer`.
"""
import json
import sqlite3
import threading
from typing import Optional

from config import settings


class ZoneDB:
    def __init__(self, path: str | None = None):
        self.path = str(path or settings.ZONE_DB_PATH)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS zones (
                stream_id TEXT PRIMARY KEY,
                json TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def get(self, stream_id: str, default: Optional[dict] = None) -> dict:
        with self._lock:
            cur = self._conn.execute("SELECT json FROM zones WHERE stream_id = ?", (stream_id,))
            row = cur.fetchone()
            if not row:
                return default or {}
            try:
                return json.loads(row[0])
            except Exception:
                return default or {}

    def set(self, stream_id: str, data: dict) -> dict:
        text = json.dumps(data)
        with self._lock:
            self._conn.execute(
                "REPLACE INTO zones (stream_id, json) VALUES (?, ?)", (stream_id, text)
            )
            self._conn.commit()
        return data

    def delete(self, stream_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM zones WHERE stream_id = ?", (stream_id,))
            self._conn.commit()

    # dict-like helpers used by existing code
    def __getitem__(self, stream_id: str) -> dict:
        return self.get(stream_id, {})

    def __setitem__(self, stream_id: str, value: dict) -> None:
        self.set(stream_id, value)

    def pop(self, stream_id: str, default: Optional[dict] = None) -> dict:
        val = self.get(stream_id, default)
        self.delete(stream_id)
        return val


# Singleton instance used by API and streamer
zone_store = ZoneDB()
