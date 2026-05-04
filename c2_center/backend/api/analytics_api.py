"""C2 Center — Analytics API (algorithm switching)."""

from fastapi import APIRouter, HTTPException
from analytics import ANALYZER_REGISTRY

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def get_router(stream_processor):
    @router.get("/algorithms")
    async def list_algorithms():
        return [
            {"slug": slug, "name": cls().name}
            for slug, cls in ANALYZER_REGISTRY.items()
        ]

    @router.put("/algorithm/{stream_id}")
    async def set_algorithm(stream_id: str, body: dict):
        algo = body.get("algorithm")
        if not algo or algo not in ANALYZER_REGISTRY:
            raise HTTPException(400, f"Invalid algorithm. Choose from: {list(ANALYZER_REGISTRY.keys())}")
        stream_processor.set_algorithm(stream_id, algo)
        return {"status": "ok", "stream_id": stream_id, "algorithm": algo}

    return router
