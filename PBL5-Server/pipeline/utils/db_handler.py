import time
import json
import psycopg2
from typing import List, Optional
from ..config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_TABLE,
    DB_RETRY_MAX_ATTEMPTS, DB_RETRY_BASE_SECONDS, VALID_STATUSES
)


class DBHandler:
    def __init__(self):
        self.connection = None

    # ─────────── Connection Management ───────────

    def _ensure_connection(self):
        """Đảm bảo connection tồn tại và đang mở. Tự động reconnect nếu cần."""
        if self.connection and not self.connection.closed:
            return
        self.connect()

    def connect(self):
        print(f"[DB] Connecting to {DB_NAME} at {DB_HOST}:{DB_PORT}...")
        try:
            self.connection = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                connect_timeout=10,
            )
            self.connection.autocommit = True
            print("[DB] Connected.")
        except Exception as exc:
            self.connection = None
            raise ConnectionError(f"Failed to connect PostgreSQL: {exc}") from exc

    def close(self):
        """Đóng connection an toàn."""
        if self.connection and not self.connection.closed:
            self.connection.close()
            self.connection = None

    # ─────────── Validation ───────────

    @staticmethod
    def _validate_status(status: str):
        """Kiểm tra status hợp lệ trước khi dùng trong SQL."""
        if status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}"
            )

    # ─────────── Read Operations ───────────

    def get_records_by_status(self, status: str, limit: int = 10) -> list:
        """Lấy các bản ghi theo trạng thái."""
        self._validate_status(status)
        sql = f"SELECT * FROM {DB_TABLE} WHERE status = %s ORDER BY timestamp ASC LIMIT %s"
        try:
            self._ensure_connection()
            with self.connection.cursor() as cur:
                cur.execute(sql, (status, limit))
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
        except Exception as e:
            print(f"[DB] Error fetching records by status {status}: {e}")
            self.connection = None  # Reset cho lần sau reconnect
            return []

    def get_new_records(self, limit: int = 10) -> list:
        """Lấy các bản ghi mới (Tương thích ngược)."""
        return self.get_records_by_status('NEW', limit)

    def get_active_cvat_tasks(self) -> List[int]:
        """Lấy danh sách các task_id đang ở trạng thái IN_CVAT."""
        sql = (
            f"SELECT DISTINCT cvat_task_id FROM {DB_TABLE} "
            f"WHERE status = 'IN_CVAT' AND cvat_task_id IS NOT NULL"
        )
        try:
            self._ensure_connection()
            with self.connection.cursor() as cur:
                cur.execute(sql)
                return [row[0] for row in cur.fetchall()]
        except Exception as e:
            print(f"[DB] Error fetching active tasks: {e}")
            self.connection = None
            return []

    def count_by_status(self, status: str) -> int:
        """Đếm số bản ghi theo trạng thái. Dùng thay vì raw SQL rải rác."""
        self._validate_status(status)
        sql = f"SELECT COUNT(*) FROM {DB_TABLE} WHERE status = %s"
        try:
            self._ensure_connection()
            with self.connection.cursor() as cur:
                cur.execute(sql, (status,))
                return cur.fetchone()[0]
        except Exception as e:
            print(f"[DB] Error counting records by status {status}: {e}")
            self.connection = None
            return 0

    # ─────────── Write Operations ───────────

    def update_status(self, record_ids: List[int], new_status: str,
                      cvat_task_id: Optional[int] = None):
        """Cập nhật trạng thái và cvat_task_id cho danh sách bản ghi."""
        if not record_ids:
            return
        self._validate_status(new_status)

        if cvat_task_id is not None:
            sql = f"UPDATE {DB_TABLE} SET status = %s, cvat_task_id = %s WHERE id IN %s"
            params = (new_status, cvat_task_id, tuple(record_ids))
        else:
            sql = f"UPDATE {DB_TABLE} SET status = %s WHERE id IN %s"
            params = (new_status, tuple(record_ids))

        try:
            self._ensure_connection()
            with self.connection.cursor() as cur:
                cur.execute(sql, params)
        except Exception as e:
            print(f"[DB] Error updating status: {e}")
            self.connection = None

    def update_status_by_task(self, cvat_task_id: int, status: str):
        """Cập nhật trạng thái cho tất cả bản ghi thuộc 1 task."""
        self._validate_status(status)
        sql = f"UPDATE {DB_TABLE} SET status = %s WHERE cvat_task_id = %s"
        try:
            self._ensure_connection()
            with self.connection.cursor() as cur:
                cur.execute(sql, (status, cvat_task_id))
        except Exception as e:
            print(f"[DB] Error updating status by task: {e}")
            self.connection = None

    def batch_update_status(self, from_status: str, to_status: str) -> int:
        """Chuyển hàng loạt bản ghi từ trạng thái này sang trạng thái khác.
        
        Trả về số bản ghi đã cập nhật. Dùng thay vì raw SQL rải rác.
        """
        self._validate_status(from_status)
        self._validate_status(to_status)
        sql = f"UPDATE {DB_TABLE} SET status = %s WHERE status = %s"
        try:
            self._ensure_connection()
            with self.connection.cursor() as cur:
                cur.execute(sql, (to_status, from_status))
                return cur.rowcount
        except Exception as e:
            print(f"[DB] Error batch updating {from_status} → {to_status}: {e}")
            self.connection = None
            return 0

    def insert_record(self, data: dict):
        """Thêm bản ghi mới từ MQTT (Kèm nhãn từ Jetson)."""
        sql = f"""
            INSERT INTO {DB_TABLE} (camera_id, image_url, timestamp, trigger_reason, status, edge_predictions)
            VALUES (%s, %s, TO_TIMESTAMP(%s), %s, 'NEW', %s)
        """
        params = (
            data["camera_id"],
            data["image_url"],
            data["timestamp"],
            data["trigger_reason"],
            json.dumps(data["edge_predictions"])
        )
        try:
            self._ensure_connection()
            with self.connection.cursor() as cur:
                cur.execute(sql, params)
        except Exception as e:
            print(f"[DB] Error inserting record: {e}")
            self.connection = None
            raise

    def insert_with_retry(self, data: dict):
        """Thêm bản ghi với cơ chế retry (exponential backoff)."""
        last_error = None
        for attempt in range(DB_RETRY_MAX_ATTEMPTS):
            try:
                self.insert_record(data)
                return
            except Exception as e:
                last_error = e
                wait = DB_RETRY_BASE_SECONDS * (2 ** attempt)
                print(f"[DB] Insert attempt {attempt + 1}/{DB_RETRY_MAX_ATTEMPTS} failed: {e}. "
                      f"Retrying in {wait:.1f}s...")
                time.sleep(wait)
        raise ConnectionError(
            f"Failed to insert record after {DB_RETRY_MAX_ATTEMPTS} attempts: {last_error}"
        )
