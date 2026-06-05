import os
import time
import zipfile
import shutil
import yaml
from ultralytics import YOLO
from ..config import (
    BUCKET_LABELED_DATA, 
    BUCKET_MODEL_UPDATES, 
    YOLO_CLASSES,
    EDGE_MODEL_PATH
)
from ..utils.minio_handler import MinioHandler
from ..utils.telegram_handler import TelegramHandler
from ..celery_app import app

def prepare_dataset(minio, work_dir="./dataset_train"):
    """
    Tải tất cả các file zip từ bucket labeled-data và giải nén.
    Tạo cấu trúc YOLO dataset và file data.yaml.
    """
    if os.path.exists(work_dir):
        shutil.rmtree(work_dir)
    
    images_dir = os.path.join(work_dir, "images", "train")
    labels_dir = os.path.join(work_dir, "labels", "train")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(labels_dir, exist_ok=True)
    
    zip_files = minio.list_objects(BUCKET_LABELED_DATA)
    if not zip_files:
        return None
        
    print(f"📦 [Trainer] Found {len(zip_files)} labeled dataset zips. Downloading...")
    for zf in zip_files:
        local_zip = os.path.join(work_dir, zf)
        minio.download_file(BUCKET_LABELED_DATA, zf, local_zip)
        
        # Giải nén
        temp_extract = os.path.join(work_dir, "temp_extract")
        os.makedirs(temp_extract, exist_ok=True)
        with zipfile.ZipFile(local_zip, 'r') as zip_ref:
            zip_ref.extractall(temp_extract)
            
        os.remove(local_zip)
        
    # Lọc và di chuyển file
    temp_dir = os.path.join(work_dir, "temp_extract")
    if os.path.exists(temp_dir):
        for root, _, files in os.walk(temp_dir):
            for file in files:
                ext = file.split('.')[-1].lower()
                src_path = os.path.join(root, file)
                if ext in ['jpg', 'png', 'jpeg']:
                    shutil.move(src_path, os.path.join(images_dir, file))
                elif ext == 'txt' and file != "classes.txt":
                    shutil.move(src_path, os.path.join(labels_dir, file))
                    
    # Tạo data.yaml
    data_yaml_path = os.path.join(work_dir, "data.yaml")
    yaml_content = {
        'train': os.path.abspath(images_dir),
        'val': os.path.abspath(images_dir), # Dùng tạm tập train làm val để demo
        'nc': len(YOLO_CLASSES),
        'names': YOLO_CLASSES
    }
    with open(data_yaml_path, 'w') as f:
        yaml.dump(yaml_content, f)
        
    return data_yaml_path

@app.task
def train_and_upload():
    print("🚀 [Trainer] Starting Continuous Training pipeline...")
    minio = MinioHandler()
    minio.ensure_bucket(BUCKET_MODEL_UPDATES)
    
    data_yaml = prepare_dataset(minio)
    if not data_yaml:
        print("💤 [Trainer] No labeled data found to train.")
        return False
        
    print(f"🧠 [Trainer] Loading base model {EDGE_MODEL_PATH}...")
    try:
        model = YOLO(EDGE_MODEL_PATH)
    except Exception as e:
        print(f"⚠️ [Trainer] Failed to load base model: {e}. Using yolov8n.pt instead.")
        model = YOLO('yolov8n.pt')
        
    print("⏳ [Trainer] Training started...")
    # Tên thư mục duy nhất cho mỗi lần chạy để tránh trùng
    run_name = f"auto_train_{int(time.time())}"
    # Chạy train
    results = model.train(
        data=data_yaml,
        epochs=10, # Demo: 10 epochs
        imgsz=640,
        batch=8,
        project="pipeline_runs",
        name=run_name,
        exist_ok=True
    )
    
    # Tìm file weight tốt nhất
    best_weights = os.path.join("pipeline_runs", run_name, "weights", "best.pt")
    if not os.path.exists(best_weights):
        # Fallback thử lấy last.pt nếu best.pt không có
        best_weights = os.path.join("pipeline_runs", run_name, "weights", "last.pt")
        if not os.path.exists(best_weights):
            print("❌ [Trainer] Training failed to produce any weights.")
            return False
        
    # Upload lên MinIO
    version = f"v{int(time.time())}"
    new_model_name = f"yolo_{version}.pt"
    
    print(f"☁️ [Trainer] Uploading new model {new_model_name} to MinIO...")
    minio.upload_file(BUCKET_MODEL_UPDATES, new_model_name, best_weights)
    
    # Telegram alert
    tg = TelegramHandler()
    msg = f"🎉 *[CT Pipeline] Training Completed!*\n\n📦 New model: `{new_model_name}`\n☁️ Uploaded to bucket: `{BUCKET_MODEL_UPDATES}`\n🚀 Ready for deployment to Edge."
    tg.send_message(msg)
    
    # Phân phối OTA qua MQTT
    import paho.mqtt.publish as publish
    import json
    from ..config import MQTT_BROKER, MQTT_PORT
    
    payload = {
        "action": "UPDATE_MODEL",
        "version": version,
        "model_name": new_model_name
    }
    try:
        publish.single(
            "traffic/system/ota_update", 
            payload=json.dumps(payload), 
            hostname=MQTT_BROKER, 
            port=MQTT_PORT
        )
        print("📡 [Trainer] OTA update command published via MQTT.")
    except Exception as e:
        print(f"⚠️ [Trainer] Failed to publish OTA command: {e}")
        
    # Dọn dẹp
    shutil.rmtree("./dataset_train", ignore_errors=True)
    shutil.rmtree(f"./pipeline_runs/{run_name}", ignore_errors=True)
    
    print(f"✅ [Trainer] Pipeline finished successfully. Model: {new_model_name}")
    return new_model_name
