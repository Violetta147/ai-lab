import time
import requests
from ..config import CVAT_URL, CVAT_USER, CVAT_PASS, CVAT_PROJECT_ID

# ─────────── Custom Exceptions ───────────


class CVATExportTimeoutError(Exception):
    """Raised khi export annotations từ CVAT vượt quá thời gian chờ."""
    pass


class CVATTaskCreationError(Exception):
    """Raised khi không thể tạo task trên CVAT."""
    pass


# ─────────── Constants ───────────

_DEFAULT_TIMEOUT = 30       # Timeout mặc định cho mỗi HTTP request (giây)
_EXPORT_POLL_INTERVAL = 5   # Khoảng cách giữa các lần poll export status (giây)
_EXPORT_MAX_POLLS = 24      # Tối đa số lần poll (24 × 5s = 2 phút)
_TASK_READY_TIMEOUT = 60    # Thời gian chờ task chuyển sang trạng thái sẵn sàng


class CVATHandler:
    def __init__(self):
        self.url = CVAT_URL.rstrip('/')
        self.auth = (CVAT_USER, CVAT_PASS)
        self.project_id = int(CVAT_PROJECT_ID)
        self.headers = {"Host": "localhost"}

    # ─────────── Label Mapping ───────────

    def get_label_mapping(self) -> dict:
        """Lấy danh sách label từ API labels. Trả về dict {name: id}."""
        endpoint = f"{self.url}/api/labels"
        params = {"project_id": self.project_id}
        resp = requests.get(
            endpoint, params=params, auth=self.auth,
            headers=self.headers, timeout=_DEFAULT_TIMEOUT
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return {label["name"]: label["id"] for label in results}

    # ─────────── Task Creation ───────────

    def create_task(self, name: str, image_zip_path: str) -> int:
        """Tạo task mới và upload ảnh. Trả về task_id."""
        endpoint = f"{self.url}/api/tasks"
        data = {
            "name": name,
            "project_id": self.project_id,
            "image_quality": 85,
        }
        resp = requests.post(
            endpoint, json=data, auth=self.auth,
            headers=self.headers, timeout=_DEFAULT_TIMEOUT
        )
        resp.raise_for_status()
        task_id = resp.json()["id"]

        # Upload images
        try:
            with open(image_zip_path, 'rb') as f:
                files = {'client_files[0]': f}
                upload_resp = requests.post(
                    f"{endpoint}/{task_id}/data",
                    files=files,
                    data={"image_quality": 85, "storage": "local"},
                    auth=self.auth,
                    headers=self.headers,
                    timeout=120,  # Upload file lớn cần timeout dài hơn
                )
                upload_resp.raise_for_status()
        except Exception as e:
            raise CVATTaskCreationError(
                f"Failed to upload images to task {task_id}: {e}"
            ) from e

        self._wait_for_task_status(task_id)
        return task_id

    # ─────────── Annotations ───────────

    def upload_annotations(self, task_id: int, shapes: list):
        """Upload nhãn giả lên task."""
        endpoint = f"{self.url}/api/tasks/{task_id}/annotations"
        data = {"shapes": shapes, "tracks": [], "tags": []}
        resp = requests.put(
            endpoint, json=data, auth=self.auth,
            headers=self.headers, timeout=_DEFAULT_TIMEOUT
        )
        resp.raise_for_status()

    def export_task_annotations(self, task_id: int) -> bytes:
        """Xuất nhãn từ CVAT dưới dạng YOLO format.
        
        Returns:
            bytes: Nội dung file zip chứa annotations.
            
        Raises:
            CVATExportTimeoutError: Nếu export vượt quá thời gian chờ.
        """
        # Bước 1: Trigger export (save_images=false để chỉ lấy nhãn)
        trigger_url = f"{self.url}/api/tasks/{task_id}/dataset/export"
        params = {"format": "YOLO 1.1", "save_images": "false"}

        print(f"📦 [CVAT] Step 1: Triggering export via POST (annotations only)...")
        resp = requests.post(
            trigger_url, params=params, auth=self.auth,
            headers=self.headers, timeout=_DEFAULT_TIMEOUT
        )
        resp.raise_for_status()

        request_id = resp.json().get("id") or resp.json().get("rq_id")
        print(f"📡 [CVAT] Export requested. Request ID: {request_id}")

        # Bước 2: Poll status cho đến khi finished
        poll_url = f"{self.url}/api/requests/{request_id}"
        download_url = None

        for i in range(_EXPORT_MAX_POLLS):
            time.sleep(_EXPORT_POLL_INTERVAL)
            p_resp = requests.get(
                poll_url, auth=self.auth,
                headers=self.headers, timeout=_DEFAULT_TIMEOUT
            )
            p_resp.raise_for_status()
            status = p_resp.json().get("status")
            print(f"🔄 [CVAT] Request status ({i + 1}/{_EXPORT_MAX_POLLS}): {status}")

            if status == "finished":
                print(f"✅ [CVAT] Export finished!")
                # Lấy result_url và thay đổi host để phù hợp với Docker
                download_url = p_resp.json().get("result_url")
                if download_url:
                    download_url = download_url.replace("http://localhost", self.url)
                break
            elif status == "failed":
                error_msg = p_resp.json().get("message", "Unknown error")
                raise CVATExportTimeoutError(
                    f"CVAT export failed for task {task_id}: {error_msg}"
                )
        else:
            raise CVATExportTimeoutError(
                f"CVAT export timed out after {_EXPORT_MAX_POLLS * _EXPORT_POLL_INTERVAL}s "
                f"for task {task_id}"
            )

        if not download_url:
            raise CVATExportTimeoutError(
                f"CVAT export returned no download URL for task {task_id}"
            )

        # Bước 3: Download file
        print(f"✨ [CVAT] Step 3: Downloading from {download_url}...")
        d_resp = requests.get(
            download_url, auth=self.auth,
            headers=self.headers, timeout=120
        )
        d_resp.raise_for_status()

        return d_resp.content

    # ─────────── Task Status ───────────

    def is_task_ready_for_export(self, task_id: int) -> bool:
        """Kiểm tra tất cả jobs trong task đã hoàn thành chưa."""
        endpoint = f"{self.url}/api/jobs"
        try:
            resp = requests.get(
                endpoint, params={"task_id": task_id},
                auth=self.auth, headers=self.headers,
                timeout=_DEFAULT_TIMEOUT
            )
            if resp.status_code == 404:
                # Fallback cho CVAT phiên bản cũ
                endpoint = f"{self.url}/api/tasks/{task_id}/jobs"
                resp = requests.get(
                    endpoint, auth=self.auth,
                    headers=self.headers, timeout=_DEFAULT_TIMEOUT
                )

            resp.raise_for_status()
            jobs = resp.json().get("results", [])
            if not jobs:
                return False
            return all(j.get("state") == "completed" for j in jobs)
        except requests.RequestException as e:
            print(f"⚠️ [CVAT] Error checking task {task_id} status: {e}")
            return False

    def _wait_for_task_status(self, task_id: int, timeout: int = _TASK_READY_TIMEOUT) -> bool:
        """Chờ task chuyển sang trạng thái sẵn sàng sau khi upload ảnh."""
        start_time = time.time()
        endpoint = f"{self.url}/api/tasks/{task_id}"
        while time.time() - start_time < timeout:
            try:
                resp = requests.get(
                    endpoint, auth=self.auth,
                    headers=self.headers, timeout=_DEFAULT_TIMEOUT
                )
                resp.raise_for_status()
                task_status = resp.json().get("status", "")
                if task_status in ("Completed", "Finished", "validation"):
                    return True
            except requests.RequestException:
                pass  # Retry silently
            time.sleep(2)
        return False
