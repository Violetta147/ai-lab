import os
import time
import io
from PIL import Image
from ..celery_app import app
from ..config import (
    BUCKET_RAW_DATA, BUCKET_PSEUDO_LABELS, BUCKET_ARCHIVED_IMAGES, BUCKET_ARCHIVED_LABELS,
    BUCKET_LABELED_DATA, IMG_DIR, LBL_DIR, IMG_ZIP, ANN_ZIP, WORK_DIR
)
from ..utils.minio_handler import MinioHandler
from ..utils.cvat_handler import CVATHandler
from ..utils.data_processor import DataProcessor
from ..utils.inference_handler import InferenceHandler
from ..utils.db_handler import DBHandler
from ..utils.telegram_handler import TelegramHandler
from ..config import SYNC_BATCH_THRESHOLD, TRAIN_DATA_THRESHOLD, DB_TABLE

# Initialize handlers
inference_engine = None

def get_inference_engine():
    global inference_engine
    if inference_engine is None:
        inference_engine = InferenceHandler()
    return inference_engine

@app.task
def auto_inference_task():
    """Celery task to generate pseudo-labels for records with status 'NEW'."""
    db = DBHandler()
    minio = MinioHandler()
    engine = get_inference_engine()
    
    # Đảm bảo các bucket tồn tại
    minio.ensure_bucket(BUCKET_RAW_DATA)
    minio.ensure_bucket(BUCKET_PSEUDO_LABELS)
    
    # 1. Lấy danh sách bản ghi mới từ DB
    records = db.get_new_records(limit=20)
    if not records:
        print("💤 [Inference] No 'NEW' records to process.")
        return "No data"

    processed_count = 0
    for rec in records:
        img_name = rec['image_url']
        txt_name = img_name.rsplit('.', 1)[0] + ".txt"
        
        if minio.exists(BUCKET_PSEUDO_LABELS, txt_name):
            continue
            
        print(f"🧠 [Inference] Processing record {rec['id']}: {img_name}...")
        local_img_path = os.path.join(IMG_DIR, img_name)
        try:
            minio.download_file(BUCKET_RAW_DATA, img_name, local_img_path)
            txt_content = engine.predict(local_img_path)
            
            if txt_content:
                txt_bytes = io.BytesIO(txt_content.encode('utf-8'))
                minio.upload_file(BUCKET_PSEUDO_LABELS, txt_name, txt_bytes, length=len(txt_content.encode('utf-8')))
                
                # Cập nhật trạng thái sang INFERRED
                db.update_status([rec['id']], 'INFERRED')
                print(f"✅ [Inference] Generated pseudo-label for {img_name} and marked as INFERRED")
                processed_count += 1
        except Exception as e:
            print(f"❌ [Inference] Error on record {rec['id']}: {e}")
        finally:
            if os.path.exists(local_img_path):
                os.remove(local_img_path)
                
    return f"Inferred {processed_count} records"

@app.task
def sync_cvat_task():
    """Celery task to sync 'NEW' records to CVAT and update status."""
    db = DBHandler()
    minio = MinioHandler()
    cvat = CVATHandler()
    processor = DataProcessor()

    minio.ensure_bucket(BUCKET_ARCHIVED_IMAGES)
    minio.ensure_bucket(BUCKET_ARCHIVED_LABELS)

    # 1. Lấy danh sách bản ghi đã qua bước Inference (status = 'INFERRED')
    records = db.get_records_by_status('INFERRED', limit=100)
    
    if not records or len(records) < SYNC_BATCH_THRESHOLD:
        print(f"💤 [Sync] Only {len(records)} records ready. Waiting for {SYNC_BATCH_THRESHOLD}...")
        return f"Waiting for batch (current: {len(records)})"

    # QUAN TRỌNG: Sắp xếp theo tên file để khớp với thứ tự Frame của CVAT
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
        # 3. Tải ảnh (Thử ở raw-data, nếu không thấy thì thử ở archived-images)
        try:
            minio.download_file(BUCKET_RAW_DATA, img_name, local_path)
        except Exception:
            print(f"⚠️ [Sync] {img_name} not found in {BUCKET_RAW_DATA}, checking {BUCKET_ARCHIVED_IMAGES}...")
            minio.download_file(BUCKET_ARCHIVED_IMAGES, img_name, local_path)
        img_paths.append(local_path)

        # Lấy kích thước ảnh thực tế
        with Image.open(local_path) as im:
            img_size = im.size

        # Kiểm tra và nạp nhãn giả
        txt_name = img_name.rsplit('.', 1)[0] + ".txt"
        if minio.exists(BUCKET_PSEUDO_LABELS, txt_name):
            txt_content = minio.download_file_as_str(BUCKET_PSEUDO_LABELS, txt_name)
            new_shapes = processor.parse_yolo_to_cvat(txt_content, frame_idx, label_map, img_size)
            shapes.extend(new_shapes)
        
        frame_idx += 1

    # 3. Tạo file Zip để upload
    processor.create_zip(img_paths, IMG_ZIP)

    # 4. CVAT Operations
    try:
        task_name = f"AutoTask_{int(time.time())}"
        task_id = cvat.create_task(task_name, IMG_ZIP)
        
        # Upload danh sách nhãn đã tích lũy được
        if shapes:
            cvat.upload_annotations(task_id, shapes)
            print(f"📝 [Sync] Uploaded {len(shapes)} shapes to CVAT.")
        
        # 5. Cập nhật Database và thông báo
        db.update_status(record_ids, 'IN_CVAT', cvat_task_id=int(task_id))
        print(f"✅ [Sync] Task {task_id} created successfully.")

        tg = TelegramHandler()
        tg.alert_new_task(task_id, len(records))

        # 6. Archive MinIO objects
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
        raise e
    finally:
        # Cleanup temp files
        for f in os.listdir(IMG_DIR):
            try: os.remove(os.path.join(IMG_DIR, f))
            except: pass
        if os.path.exists(IMG_ZIP): os.remove(IMG_ZIP)

    return f"Synced {len(records)} records to CVAT task {task_id}"

@app.task
def export_labeled_data_task():
    """Quét các task hoàn thành trên CVAT để tải nhãn về MinIO."""
    db = DBHandler()
    minio = MinioHandler()
    cvat = CVATHandler()
    
    minio.ensure_bucket(BUCKET_LABELED_DATA)

    # 1. Lấy danh sách các CVAT Task ID đang chờ (status = 'IN_CVAT')
    # Lấy danh sách các task_id duy nhất
    active_tasks = db.get_active_cvat_tasks()
    
    for task_id in active_tasks:
        try:
            if cvat.is_task_ready_for_export(task_id):
                print(f"📥 [Export] Task {task_id} is completed! Archiving dataset...")
                
                zip_content = cvat.export_task_annotations(task_id)
                zip_name = f"labeled_task_{task_id}.zip"
                
                # Upload lên MinIO
                minio.upload_file(
                    BUCKET_LABELED_DATA, 
                    zip_name, 
                    io.BytesIO(zip_content), 
                    length=len(zip_content)
                )
                
                # Cập nhật DB: IN_CVAT -> LABELED
                db.update_status_by_task(task_id, "LABELED")
                print(f"✅ [Export] Task {task_id} archived to MinIO.")

                # 4. Gửi Telegram Alert
                tg = TelegramHandler()
                tg.alert_task_archived(task_id)

                # 5. Kiểm tra ngưỡng Train (Đếm số lượng ảnh chính xác từ DB)
                # Lấy tổng số bản ghi có trạng thái 'LABELED'
                sql_count = f"SELECT COUNT(*) FROM {DB_TABLE} WHERE status = 'LABELED'"
                with db.connection.cursor() as cur:
                    cur.execute(sql_count)
                    total_labeled_images = cur.fetchone()[0]
                
                if total_labeled_images >= TRAIN_DATA_THRESHOLD:
                    tg.alert_training_ready(total_labeled_images)
                    
                    # Trigger tự động Train Model
                    print(f"🚀 [Export] Triggering model training (Threshold reached: {total_labeled_images}/{TRAIN_DATA_THRESHOLD})")
                    from .model_trainer import train_and_upload
                    train_and_upload.delay()
                    
                    # Đánh dấu các ảnh đã được gom đi Train để reset lại bộ đếm cho vòng lặp sau
                    sql_update_trained = f"UPDATE {DB_TABLE} SET status = 'TRAINED' WHERE status = 'LABELED'"
                    with db.connection.cursor() as cur:
                        cur.execute(sql_update_trained)
                    print("✅ [Export] Reset counter for new labeled data.")
        except Exception as e:
            print(f"❌ [Export] Error for task {task_id}: {e}")
