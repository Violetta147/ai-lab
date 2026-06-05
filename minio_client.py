from __future__ import annotations

import urllib3
from minio import Minio

from .config import (
    MINIO_ACCESS_KEY,
    MINIO_BUCKET,
    MINIO_CONNECT_TIMEOUT_SECONDS,
    MINIO_READ_TIMEOUT_SECONDS,
    MINIO_SECRET_KEY,
    MINIO_URL,
)
from .logger import log


def create_minio_client() -> Minio:
    log("Connecting to MinIO...")
    http_client = urllib3.PoolManager(
        timeout=urllib3.Timeout(
            connect=MINIO_CONNECT_TIMEOUT_SECONDS,
            read=MINIO_READ_TIMEOUT_SECONDS,
        ),
        retries=False,
    )
    client = Minio(
        MINIO_URL,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
        http_client=http_client,
    )
    if not client.bucket_exists(MINIO_BUCKET):
        log(f"Bucket '{MINIO_BUCKET}' not found, creating it.")
        client.make_bucket(MINIO_BUCKET)
    log("MinIO is ready.")
    return client

