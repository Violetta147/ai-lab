from __future__ import annotations

import queue
import threading
import time

from minio import Minio
from paho.mqtt import client as mqtt_client

from .buffer_store import (
    build_buffer_file_path,
    save_frame_to_buffer,
    save_metadata_to_buffer,
    sync_buffer_to_server,
)
from .config import CAMERA_ID, LOCAL_DISK_SAFETY_LIMIT_MB
from .logger import log


def _check_disk_space() -> bool:
    import shutil
    try:
        total, used, free = shutil.disk_usage("./buffer")
        free_mb = free / (1024 * 1024)
        if free_mb < LOCAL_DISK_SAFETY_LIMIT_MB:
            return False
        return True
    except Exception:
        return True


def disk_writer_worker(ram_queue: queue.Queue) -> None:
    log("🚀 Disk Writer Thread started.")
    while True:
        try:
            item = ram_queue.get(block=True, timeout=1.0)
            frame = item["frame"]
            metadata = item["metadata"]
            image_name = metadata["image_url"]

            if not _check_disk_space():
                log("⚠️ LOCAL DISK FULL! Dropping AL frame to protect system.")
                ram_queue.task_done()
                continue

            # Save frame and metadata
            save_frame_to_buffer(frame, image_name)
            save_metadata_to_buffer(CAMERA_ID, metadata)
            
            # Explicit GC since frame might be large
            del frame
            import gc
            gc.collect()

            ram_queue.task_done()
            # Yield CPU slightly
            time.sleep(0.01)

        except queue.Empty:
            continue
        except Exception as e:
            log(f"❌ Disk Writer Thread Error: {e}")
            time.sleep(1.0)


def background_sync_worker(
    minio_client: Minio,
    mqtt_client_instance: mqtt_client.Client,
) -> None:
    log("☁️ Background Sync Thread started.")
    while True:
        try:
            sync_buffer_to_server(
                minio_client=minio_client,
                mqtt_client_instance=mqtt_client_instance,
                camera_id=CAMERA_ID,
            )
            # Sleep longer to yield CPU to AI inference
            time.sleep(2.0)
        except Exception as e:
            log(f"❌ Background Sync Thread Error: {e}")
            time.sleep(5.0)

def start_threads(
    ram_queue: queue.Queue,
    minio_client: Minio,
    mqtt_client_instance: mqtt_client.Client,
) -> list[threading.Thread]:
    writer_thread = threading.Thread(
        target=disk_writer_worker, args=(ram_queue,), daemon=True, name="DiskWriterThread"
    )
    sync_thread = threading.Thread(
        target=background_sync_worker, args=(minio_client, mqtt_client_instance), daemon=True, name="BackgroundSyncThread"
    )

    writer_thread.start()
    sync_thread.start()

    return [writer_thread, sync_thread]
