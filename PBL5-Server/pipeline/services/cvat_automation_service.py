import os
import time
import io
from PIL import Image
from ..celery_app import app
from ..config import (
    BUCKET_RAW_DATA, BUCKET_PSEUDO_LABELS, BUCKET_ARCHIVED_IMAGES, BUCKET_ARCHIVED_LABELS,
    BUCKET_LABELED_DATA, IMG_DIR, LBL_DIR, IMG_ZIP, WORK_DIR,
    SYNC_BATCH_THRESHOLD, TRAIN_DATA_THRESHOLD,
)
from ..utils.minio_handler import MinioHandler
from ..utils.cvat_handler import CVATHandler
from ..utils.data_processor import DataProcessor
from ..utils.inference_handler import InferenceHandler
from ..utils.db_handler import DBHandler
from ..utils.telegram_handler import TelegramHandler

# ─────────── Lazy Singleton cho Inference Engine ───────────
# Inference model rất nặng (~1GB VRAM), chỉ nên load 1 lần duy nhất
# trong suốt vòng đời của Celery worker process.

_inference_engine = None


def _get_inference_engine():
    global _inference_engine
    if _inference_engine is None:
        _inference_engine = InferenceHandler()
    return _inference_engine


# ═══════════════════════════════════════════════════════════════
# TASK 1: Auto Inference — Tạo pseudo-labels cho ảnh mới
# Flow: NEW → INFERRED
# ═══════════════════════════════════════════════════════════════

@app.task(bind=True, max_retries=2, default_retry_delay=30)
def auto_inference_task(self):
    """Celery task tạo pseudo-labels cho các bản ghi có status 'NEW'.

    Workflow:
        1. Lấy tối đa 20 bản ghi NEW từ DB
        2. Tải ảnh từ MinIO (raw-data)
        3. Chạy YOLO inference để tạo pseudo-label (.txt)
        4. Upload pseudo-label lên MinIO (pseudo-labels)
        5. Cập nhật status: NEW → INFERRED
    """
    db = DBHandler()
    minio = MinioHandler()
    engine = _get_inference_engine()

    # Đảm bảo các bucket tồn tại
    minio.ensure_bucket(BUCKET_RAW_DATA)
    minio.ensure_bucket(BUCKET_PSEUDO_LABELS)

    # 1. Lấy danh sách bản ghi mới từ DB
    records = db.get_new_records(limit=20)
    if not records:
        print("💤 [Inference] No 'NEW' records to process.")
        return "No data"

    processed_count = 0
    error_count = 0

    for rec in records:
        img_name = rec['image_url']
        txt_name = img_name.rsplit('.', 1)[0] + ".txt"

        # Skip nếu pseudo-label đã tồn tại (idempotent)
        if minio.exists(BUCKET_PSEUDO_LABELS, txt_name):
            db.update_status([rec['id']], 'INFERRED')
            continue

        print(f"🧠 [Inference] Processing record {rec['id']}: {img_name}...")
        local_img_path = os.path.join(IMG_DIR, img_name)
        try:
            minio.download_file(BUCKET_RAW_DATA, img_name, local_img_path)
            txt_content = engine.predict(local_img_path)

            if txt_content:
                txt_bytes = txt_content.encode('utf-8')
                minio.upload_file(
                    BUCKET_PSEUDO_LABELS, txt_name,
                    io.BytesIO(txt_bytes), length=len(txt_bytes)
                )

            # Cập nhật trạng thái sang INFERRED (kể cả khi không có detection)
            db.update_status([rec['id']], 'INFERRED')
            print(f"✅ [Inference] Processed {img_name} → INFERRED")
            processed_count += 1

        except Exception as e:
            error_count += 1
            print(f"❌ [Inference] Error on record {rec['id']}: {e}")
        finally:
            # Luôn cleanup file tạm
            if os.path.exists(local_img_path):
                os.remove(local_img_path)

    return f"Inferred {processed_count} records, {error_count} errors"


# ═══════════════════════════════════════════════════════════════
# TASK 2: Sync to CVAT — Gom batch ảnh + pseudo-labels → CVAT
# Flow: INFERRED → IN_CVAT
# ═══════════════════════════════════════════════════════════════

@app.task(bind=True, max_retries=1, default_retry_delay=60)
def sync_cvat_task(self):
    """Celery task gom batch ảnh INFERRED và đẩy lên CVAT.

    Workflow:
        1. Lấy bản ghi INFERRED từ DB (chờ đủ SYNC_BATCH_THRESHOLD)
        2. Tải ảnh + pseudo-labels từ MinIO
        3. Tạo task CVAT với ảnh + annotations
        4. Cập nhật status: INFERRED → IN_CVAT
        5. Archive ảnh/labels gốc sang bucket riêng
        6. Gửi Telegram alert
    """
    db = DBHandler()
    minio = MinioHandler()
    cvat = CVATHandler()
    processor = DataProcessor()

    minio.ensure_bucket(BUCKET_ARCHIVED_IMAGES)
    minio.ensure_bucket(BUCKET_ARCHIVED_LABELS)

    # 1. Lấy danh sách bản ghi đã qua Inference
    records = db.get_records_by_status('INFERRED', limit=100)

    # Guard: xử lý None và chưa đủ batch
    if not records or len(records) < SYNC_BATCH_THRESHOLD:
        count = len(records) if records else 0
        print(f"💤 [Sync] Only {count} records ready. Waiting for {SYNC_BATCH_THRESHOLD}...")
        return f"Waiting for batch (current: {count})"

    # Sắp xếp theo tên file để khớp với thứ tự Frame của CVAT
    records = sorted(records, key=lambda x: x['image_url'])

    record_ids = [r['id'] for r in records]
    img_files = [r['image_url'] for r in records]

    print(f"🔄 [Sync] Syncing {len(records)} records to CVAT...")

    # 2. Tải ảnh và nhãn giả từ MinIO
    img_paths = []
    shapes = []
    label_map = cvat.get_label_mapping()
    frame_idx = 0

    for rec in records:
        img_name = rec["image_url"]
        local_path = os.path.join(IMG_DIR, img_name)
        # Tải ảnh (thử raw-data trước, fallback sang archived-images)
        try:
            minio.download_file(BUCKET_RAW_DATA, img_name, local_path)
        except Exception:
            print(f"⚠️ [Sync] {img_name} not in {BUCKET_RAW_DATA}, trying {BUCKET_ARCHIVED_IMAGES}...")
            try:
                minio.download_file(BUCKET_ARCHIVED_IMAGES, img_name, local_path)
            except Exception as e:
                print(f"❌ [Sync] Cannot download {img_name} from any bucket: {e}")
                continue

        img_paths.append(local_path)

        # Lấy kích thước ảnh thực tế
        try:
            with Image.open(local_path) as im:
                img_size = im.size
        except Exception as e:
            print(f"⚠️ [Sync] Cannot read image size for {img_name}: {e}")
            img_size = (1920, 1080)  # Fallback

        # Nạp pseudo-label
        txt_name = img_name.rsplit('.', 1)[0] + ".txt"
        if minio.exists(BUCKET_PSEUDO_LABELS, txt_name):
            txt_content = minio.download_file_as_str(BUCKET_PSEUDO_LABELS, txt_name)
            new_shapes = processor.parse_yolo_to_cvat(txt_content, frame_idx, label_map, img_size)
            shapes.extend(new_shapes)

        frame_idx += 1

    # Guard: nếu không tải được ảnh nào
    if not img_paths:
        print("❌ [Sync] No images could be downloaded. Aborting.")
        return "No images available"

    # 3. Tạo file Zip để upload
    processor.create_zip(img_paths, IMG_ZIP)

    # 4. CVAT Operations
    task_id = None
    try:
        task_name = f"AutoTask_{int(time.time())}"
        task_id = cvat.create_task(task_name, IMG_ZIP)

        # Upload annotations
        if shapes:
            cvat.upload_annotations(task_id, shapes)
            print(f"📝 [Sync] Uploaded {len(shapes)} shapes to CVAT.")

        # 5. Cập nhật Database
        db.update_status(record_ids, 'IN_CVAT', cvat_task_id=int(task_id))
        print(f"✅ [Sync] Task {task_id} created successfully.")

        # 6. Telegram alert
        tg = TelegramHandler()
        tg.alert_new_task(task_id, len(records))

        # 7. Archive MinIO objects
        for img_name in img_files:
            try:
                minio.move_object(BUCKET_RAW_DATA, img_name, BUCKET_ARCHIVED_IMAGES)
                txt_name = img_name.rsplit('.', 1)[0] + ".txt"
                if minio.exists(BUCKET_PSEUDO_LABELS, txt_name):
                    minio.move_object(BUCKET_PSEUDO_LABELS, txt_name, BUCKET_ARCHIVED_LABELS)
            except Exception as e:
                print(f"⚠️ [Sync] Archive error for {img_name}: {e}")

    except Exception as e:
        print(f"❌ [Sync] Critical error: {e}")
        raise
    finally:
        # Cleanup temp files (luôn chạy dù thành công hay thất bại)
        for f in os.listdir(IMG_DIR):
            try:
                os.remove(os.path.join(IMG_DIR, f))
            except OSError:
                pass
        if os.path.exists(IMG_ZIP):
            os.remove(IMG_ZIP)

    return f"Synced {len(records)} records to CVAT task {task_id}"


# ═══════════════════════════════════════════════════════════════
# TASK 3: Export Labeled Data — Tải nhãn từ CVAT về MinIO
# Flow: IN_CVAT → LABELED → (trigger train) → TRAINED
# ═══════════════════════════════════════════════════════════════

@app.task(bind=True, max_retries=1, default_retry_delay=60)
def export_labeled_data_task(self):
    """Quét các task hoàn thành trên CVAT, tải nhãn về MinIO.

    Workflow:
        1. Lấy danh sách task IN_CVAT từ DB
        2. Kiểm tra từng task đã completed trên CVAT chưa
        3. Export annotations dạng YOLO 1.1
        4. Upload zip lên MinIO (labeled-data)
        5. Cập nhật status: IN_CVAT → LABELED
        6. Nếu đủ ngưỡng TRAIN_DATA_THRESHOLD → trigger training
    """
    db = DBHandler()
    minio = MinioHandler()
    cvat = CVATHandler()

    minio.ensure_bucket(BUCKET_LABELED_DATA)

    # 1. Lấy danh sách các CVAT Task ID đang chờ
    active_tasks = db.get_active_cvat_tasks()
    if not active_tasks:
        return "No active CVAT tasks"

    for task_id in active_tasks:
        try:
            if not cvat.is_task_ready_for_export(task_id):
                continue

            print(f"📥 [Export] Task {task_id} is completed! Archiving dataset...")

            zip_content = cvat.export_task_annotations(task_id)
            zip_name = f"labeled_task_{task_id}.zip"

            # Upload lên MinIO
            minio.upload_file(
                BUCKET_LABELED_DATA,
                zip_name,
                io.BytesIO(zip_content),
                length=len(zip_content),
            )

            # Cập nhật DB: IN_CVAT → LABELED
            db.update_status_by_task(task_id, "LABELED")
            print(f"✅ [Export] Task {task_id} archived to MinIO.")

            # 4. Gửi Telegram Alert
            tg = TelegramHandler()
            tg.alert_task_archived(task_id)

            # 5. Kiểm tra ngưỡng Train (dùng DBHandler method thay vì raw SQL)
            total_labeled = db.count_by_status("LABELED")

            if total_labeled >= TRAIN_DATA_THRESHOLD:
                tg.alert_training_ready(total_labeled)

                # Trigger tự động Train Model
                print(
                    f"🚀 [Export] Triggering model training "
                    f"(Threshold reached: {total_labeled}/{TRAIN_DATA_THRESHOLD})"
                )
                from .model_trainer import train_and_upload
                train_and_upload.delay()

                # Đánh dấu ảnh đã gom đi Train (dùng DBHandler method)
                updated = db.batch_update_status("LABELED", "TRAINED")
                print(f"✅ [Export] Marked {updated} records as TRAINED.")

        except Exception as e:
            print(f"❌ [Export] Error for task {task_id}: {e}")
