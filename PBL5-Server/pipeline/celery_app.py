from celery import Celery
from .config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

app = Celery(
    'pipeline_tasks',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        'pipeline.services.cvat_automation_service',
        'pipeline.services.model_trainer',
    ]
)

# ─────────── Worker Configuration ───────────
app.conf.update(
    timezone='UTC',
    # Task không bị mất khi worker crash giữa chừng
    task_acks_late=True,
    # Mỗi worker chỉ nhận 1 task tại 1 thời điểm (tránh OOM với GPU tasks)
    worker_prefetch_multiplier=1,
    # Tự động gỡ kết quả task sau 1 giờ (tiết kiệm Redis memory)
    result_expires=3600,
    # Serializer
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
)

# ─────────── Periodic Tasks (Celery Beat) ───────────
app.conf.beat_schedule = {
    'auto-inference-every-30-seconds': {
        'task': 'pipeline.services.cvat_automation_service.auto_inference_task',
        'schedule': 30.0,
    },
    'sync-cvat-every-60-seconds': {
        'task': 'pipeline.services.cvat_automation_service.sync_cvat_task',
        'schedule': 60.0,
    },
    'export-labeled-data-every-30-seconds': {
        'task': 'pipeline.services.cvat_automation_service.export_labeled_data_task',
        'schedule': 30.0,
    },
}

if __name__ == '__main__':
    app.start()
