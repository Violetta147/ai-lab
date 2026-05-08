"""C2 Center — Streams API (health check + stream discovery)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["streams"])


def get_router(sync_engine, kafka_consumer=None):
    @router.get("/health")
    async def health():
        streams = {}
        for sid in sync_engine.get_stream_ids():
            streams[sid] = sync_engine.get_stream_status(sid)
        kafka_connected = False
        if kafka_consumer is not None:
            try:
                kafka_connected = bool(kafka_consumer.is_connected)
            except Exception:
                kafka_connected = False
        return {"status": "ok", "streams": streams, "kafka_connected": kafka_connected}

    @router.get("/streams")
    async def list_streams():
        result = []
        for sid in sync_engine.get_stream_ids():
            status = sync_engine.get_stream_status(sid)
            result.append(status)
        return result

    return router
