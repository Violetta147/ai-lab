import time
import requests
from ..config import CVAT_URL, CVAT_USER, CVAT_PASS, CVAT_PROJECT_ID

class CVATHandler:
    def __init__(self):
        self.url = CVAT_URL.rstrip('/')
        self.auth = (CVAT_USER, CVAT_PASS)
        self.project_id = int(CVAT_PROJECT_ID)
        self.headers = {"Host": "localhost"}

    def get_label_mapping(self):
        """Lấy danh sách label từ API labels."""
        endpoint = f"{self.url}/api/labels"
        params = {"project_id": self.project_id}
        resp = requests.get(endpoint, params=params, auth=self.auth, headers=self.headers)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return {l["name"]: l["id"] for l in results}

    def create_task(self, name, image_zip_path):
        """Tạo task mới và upload ảnh."""
        endpoint = f"{self.url}/api/tasks"
        data = {"name": name, "project_id": self.project_id, "image_quality": 85}
        resp = requests.post(endpoint, json=data, auth=self.auth, headers=self.headers)
        resp.raise_for_status()
        task_id = resp.json()["id"]

        with open(image_zip_path, 'rb') as f:
            files = {'client_files[0]': f}
            requests.post(
                f"{endpoint}/{task_id}/data",
                files=files,
                data={"image_quality": 85, "storage": "local"},
                auth=self.auth,
                headers=self.headers
            ).raise_for_status()
        
        self._wait_for_task_status(task_id)
        return task_id

    def upload_annotations(self, task_id, shapes):
        """Upload nhãn giả lên task."""
        endpoint = f"{self.url}/api/tasks/{task_id}/annotations"
        data = {"shapes": shapes, "tracks": [], "tags": []}
        requests.put(endpoint, json=data, auth=self.auth, headers=self.headers).raise_for_status()

    def export_task_annotations(self, task_id):
        """Xuất nhãn từ CVAT: Dùng POST để kích hoạt (chuẩn API)."""
        # Bước 1: Request export (save_images=false để chỉ lấy nhãn)
        trigger_url = f"{self.url}/api/tasks/{task_id}/dataset/export"
        params = {"format": "YOLO 1.1", "save_images": "false"}
        
        print(f"📦 [CVAT] Step 1: Triggering export via POST (annotations only)...")
        resp = requests.post(trigger_url, params=params, auth=self.auth, headers=self.headers, timeout=10)
        resp.raise_for_status()
        
        request_id = resp.json().get("id") or resp.json().get("rq_id")
        print(f"📡 [CVAT] Export requested. Request ID: {request_id}")

        # Bước 2: Poll status
        poll_url = f"{self.url}/api/requests/{request_id}"
        for i in range(20):
            time.sleep(5)
            p_resp = requests.get(poll_url, auth=self.auth, headers=self.headers, timeout=10)
            status = p_resp.json().get("status")
            print(f"🔄 [CVAT] Request status ({i+1}/20): {status}")
            if status == "finished":
                print(f"✅ [CVAT] Export finished!")
                # Lấy result_url và thay đổi host để phù hợp với Docker
                download_url = p_resp.json().get("result_url")
                if download_url:
                    download_url = download_url.replace("http://localhost", self.url)
                break
        else: raise Exception("Export timeout")

        # Bước 3: Download dùng URL chuẩn từ CVAT
        print(f"✨ [CVAT] Step 3: Downloading from {download_url}...")
        d_resp = requests.get(download_url, auth=self.auth, headers=self.headers, timeout=60)
        d_resp.raise_for_status()
        
        return d_resp.content

    def is_task_ready_for_export(self, task_id):
        """Kiểm tra job status."""
        endpoint = f"{self.url}/api/jobs"
        resp = requests.get(endpoint, params={"task_id": task_id}, auth=self.auth, headers=self.headers)
        if resp.status_code == 404:
            endpoint = f"{self.url}/api/tasks/{task_id}/jobs"
            resp = requests.get(endpoint, auth=self.auth, headers=self.headers)
            
        resp.raise_for_status()
        jobs = resp.json().get("results", [])
        if not jobs: return False
        return all(j.get("state") == "completed" for j in jobs)

    def _wait_for_task_status(self, task_id, timeout=60):
        start_time = time.time()
        endpoint = f"{self.url}/api/tasks/{task_id}"
        while time.time() - start_time < timeout:
            resp = requests.get(endpoint, auth=self.auth, headers=self.headers)
            if resp.json().get("status") in ["Completed", "Finished", "validation"]: return True
            time.sleep(2)
        return False
