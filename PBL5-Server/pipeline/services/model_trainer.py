import os
import time
import uuid
import zipfile
import shutil
import yaml
from ultralytics import YOLO
from ..config import (
    BUCKET_LABELED_DATA,
    BUCKET_MODEL_UPDATES,
    YOLO_CLASSES,
    EDGE_MODEL_PATH,
)
from ..utils.minio_handler import MinioHandler
from ..utils.telegram_handler import TelegramHandler
from ..celery_app import app


def prepare_dataset(minio: MinioHandler, work_dir: str = "./dataset_train") -> str:
    """Tải tất cả file zip từ bucket labeled-data, giải nén và chuẩn bị YOLO dataset.

    Returns:
        Đường dẫn tới data.yaml, hoặc None nếu không có dữ liệu.
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
        # Đảm bảo thư mục cha tồn tại (zip có thể nằm trong subfolder trên MinIO)
        os.makedirs(os.path.dirname(local_zip), exist_ok=True)
        minio.download_file(BUCKET_LABELED_DATA, zf, local_zip)

        # Dùng unique temp dir cho mỗi zip để tránh trùng file
        unique_id = uuid.uuid4().hex[:8]
        temp_extract = os.path.join(work_dir, f"temp_extract_{unique_id}")
        os.makedirs(temp_extract, exist_ok=True)

        try:
            with zipfile.ZipFile(local_zip, 'r') as zip_ref:
                zip_ref.extractall(temp_extract)
        except zipfile.BadZipFile:
            print(f"⚠️ [Trainer] Corrupted zip file: {zf}, skipping...")
            shutil.rmtree(temp_extract, ignore_errors=True)
            continue
        finally:
            if os.path.exists(local_zip):
                os.remove(local_zip)

        # Lọc và di chuyển file vào thư mục dataset
        for root, _, files in os.walk(temp_extract):
            for file in files:
                ext = file.rsplit('.', 1)[-1].lower() if '.' in file else ''
                src_path = os.path.join(root, file)
                if ext in ('jpg', 'png', 'jpeg'):
                    dest = os.path.join(images_dir, file)
                    # Tránh ghi đè file trùng tên
                    if os.path.exists(dest):
                        base, fext = file.rsplit('.', 1)
                        file = f"{base}_{unique_id}.{fext}"
                        dest = os.path.join(images_dir, file)
                    shutil.move(src_path, dest)
                elif ext == 'txt' and file != "classes.txt":
                    dest = os.path.join(labels_dir, file)
                    if os.path.exists(dest):
                        base, fext = file.rsplit('.', 1)
                        file = f"{base}_{unique_id}.{fext}"
                        dest = os.path.join(labels_dir, file)
                    shutil.move(src_path, dest)

        shutil.rmtree(temp_extract, ignore_errors=True)

    # Kiểm tra có đủ dữ liệu không
    image_count = len(os.listdir(images_dir))
    label_count = len(os.listdir(labels_dir))
    print(f"📊 [Trainer] Dataset: {image_count} images, {label_count} labels")

    if image_count == 0:
        print("⚠️ [Trainer] No images found after extraction!")
        return None

    # Tạo data.yaml
    data_yaml_path = os.path.join(work_dir, "data.yaml")
    yaml_content = {
        'train': os.path.abspath(images_dir),
        'val': os.path.abspath(images_dir),  # Dùng tạm train làm val (demo)
        'nc': len(YOLO_CLASSES),
        'names': YOLO_CLASSES,
    }
    with open(data_yaml_path, 'w') as f:
        yaml.dump(yaml_content, f)

    return data_yaml_path


@app.task(bind=True, max_retries=0)
def train_and_upload(self):
    """Celery task: Train YOLO model và upload lên MinIO + phát OTA qua MQTT.

    Workflow:
        1. Tải + giải nén labeled data từ MinIO
        2. Train YOLO model (fine-tune từ edge model)
        3. Upload best weights lên MinIO (model-updates)
        4. Gửi OTA update command qua MQTT
        5. Cleanup
    """
    print("🚀 [Trainer] Starting Continuous Training pipeline...")
    minio = MinioHandler()
    minio.ensure_bucket(BUCKET_MODEL_UPDATES)

    work_dir = f"./dataset_train_{int(time.time())}"
    run_name = f"auto_train_{int(time.time())}"

    try:
        data_yaml = prepare_dataset(minio, work_dir=work_dir)
        if not data_yaml:
            print("💤 [Trainer] No labeled data found to train.")
            return None

        # Load base model
        print(f"🧠 [Trainer] Loading base model {EDGE_MODEL_PATH}...")
        try:
            model = YOLO(EDGE_MODEL_PATH)
        except Exception as e:
            print(f"⚠️ [Trainer] Failed to load base model: {e}. Using yolov8n.pt instead.")
            model = YOLO('yolov8n.pt')

        # Train
        print("⏳ [Trainer] Training started...")
        model.train(
            data=data_yaml,
            epochs=10,
            imgsz=640,
            batch=8,
            project="pipeline_runs",
            name=run_name,
            exist_ok=True,
        )

        # Tìm file weight tốt nhất
        best_weights = os.path.join("pipeline_runs", run_name, "weights", "best.pt")
        if not os.path.exists(best_weights):
            best_weights = os.path.join("pipeline_runs", run_name, "weights", "last.pt")
            if not os.path.exists(best_weights):
                print("❌ [Trainer] Training failed to produce any weights.")
                return None

        # Upload lên MinIO
        version = f"v{int(time.time())}"
        new_model_name = f"yolo_{version}.pt"

        print(f"☁️ [Trainer] Uploading new model {new_model_name} to MinIO...")
        minio.upload_file(BUCKET_MODEL_UPDATES, new_model_name, best_weights)

        # Telegram alert
        tg = TelegramHandler()
        msg = (
            f"🎉 *[CT Pipeline] Training Completed!*\n\n"
            f"📦 New model: `{new_model_name}`\n"
            f"☁️ Uploaded to bucket: `{BUCKET_MODEL_UPDATES}`\n"
            f"🚀 Ready for deployment to Edge."
        )
        tg.send_message(msg)

        # Phân phối OTA qua MQTT
        _publish_ota_update(version, new_model_name)

        print(f"✅ [Trainer] Pipeline finished successfully. Model: {new_model_name}")
        return new_model_name

    finally:
        # Cleanup (luôn chạy dù thành công hay thất bại)
        shutil.rmtree(work_dir, ignore_errors=True)
        shutil.rmtree(os.path.join("pipeline_runs", run_name), ignore_errors=True)


def _publish_ota_update(version: str, model_name: str):
    """Gửi lệnh OTA update cho Edge device qua MQTT."""
    import json
    import paho.mqtt.publish as publish
    from ..config import MQTT_BROKER, MQTT_PORT

    payload = {
        "action": "UPDATE_MODEL",
        "version": version,
        "model_name": model_name,
    }
    try:
        publish.single(
            "traffic/system/ota_update",
            payload=json.dumps(payload),
            hostname=MQTT_BROKER,
            port=MQTT_PORT,
        )
        print("📡 [Trainer] OTA update command published via MQTT.")
    except Exception as e:
        print(f"⚠️ [Trainer] Failed to publish OTA command: {e}")
