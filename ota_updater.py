import os
import shutil
from .config import MODEL_PATH
from .logger import log
from .minio_client import create_minio_client

class OTAUpdater:
    def __init__(self):
        self.model_needs_reload = False
        self.minio_client = create_minio_client()
        self.bucket_name = "model-updates"
        self.active_model_path = MODEL_PATH

    def handle_update(self, model_name: str) -> None:
        """Tải model mới từ MinIO và thiết lập cờ để reload."""
        log(f"OTA Updater: Starting download for {model_name}...")
        
        temp_path = MODEL_PATH + ".download"
        backup_path = MODEL_PATH + ".backup"
        
        try:
            # 1. Tải file về thư mục tạm
            self.minio_client.fget_object(self.bucket_name, model_name, temp_path)
            log(f"OTA Updater: Successfully downloaded {model_name}.")
            
            # 2. Backup model hiện tại (nếu có)
            if os.path.exists(MODEL_PATH):
                shutil.copy(MODEL_PATH, backup_path)
                log(f"OTA Updater: Backed up current model to {backup_path}.")
                
            # 3. Lưu file model chính thức (Đảm bảo đúng đuôi .pt)
            target_path = MODEL_PATH.rsplit('.', 1)[0] + ".pt"
            shutil.move(temp_path, target_path)
            log(f"OTA Updater: Replaced active model with {model_name} at {target_path}.")
            
            # 4. Tự động biên dịch sang TensorRT (.engine) ngay trên Edge
            log(f"OTA Updater: Compiling {target_path} to TensorRT. This will take a few minutes...")
            try:
                from ultralytics import YOLO
                temp_model = YOLO(target_path)
                # Biên dịch sang .engine (FP16 để tối ưu Jetson)
                temp_model.export(format="engine", half=True)
                
                engine_path = target_path.replace(".pt", ".engine")
                if os.path.exists(engine_path):
                    self.active_model_path = engine_path
                    log(f"OTA Updater: Compilation success. Active model is {engine_path}.")
                else:
                    self.active_model_path = target_path
                    log("OTA Updater: Engine file not found after export, falling back to .pt.")
            except Exception as export_err:
                self.active_model_path = target_path
                log(f"OTA Updater: Engine export failed ({export_err}), falling back to .pt.")
            
            # 5. Bật cờ cho luồng chính reload
            self.model_needs_reload = True
            
        except Exception as e:
            log(f"OTA Updater: Error during update - {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)

# Khởi tạo một đối tượng toàn cục để main.py và mqtt_client.py dùng chung
ota_manager = OTAUpdater()
