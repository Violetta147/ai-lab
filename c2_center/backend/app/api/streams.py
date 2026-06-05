"""C2 Center — Streams API (health check + stream discovery)."""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/api", tags=["streams"])


def get_router(stream_manager, kafka_consumer=None):
    @router.get("/health")
    async def health():
        streams = {}
        for sid in stream_manager.all_streams():
            streams[sid] = {"stream_id": sid, "state": "active"}
        kafka_connected = False
        if kafka_consumer is not None:
            try:
                kafka_connected = bool(kafka_consumer.is_connected)
            except Exception:
                kafka_connected = False
        return {
            "status": "ok",
            "streams": streams,
            "kafka_connected": kafka_connected,  # backward compat
            "metadata_connected": kafka_connected,  # generic alias
            "metadata_source": settings.METADATA_SOURCE,
        }

    @router.get("/streams")
    async def list_streams():
        result = []
        for sid in stream_manager.all_streams():
            result.append({"stream_id": sid, "state": "active"})
        return result

    return router
