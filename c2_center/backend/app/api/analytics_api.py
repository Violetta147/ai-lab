"""C2 Center — Analytics API (algorithm switching + listing)."""

from fastapi import APIRouter, HTTPException

from app.analytics.registry import registry

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def get_router(pipeline):
    """Build the analytics router bound to the live pipeline handle."""

    @router.get("/algorithms")
    async def list_algorithms():
        return [meta.to_dict() for meta in registry.list_all()]

    @router.put("/algorithm/{stream_id}")
    async def set_algorithm(stream_id: str, body: dict):
        algo = body.get("algorithm")
        if not algo or not registry.has(algo):
            raise HTTPException(
                400,
                f"Invalid algorithm. Choose from: {registry.slugs()}",
            )
        try:
            pipeline.analytics_dispatcher.set_algorithm(stream_id, algo)
        except KeyError as e:
            raise HTTPException(400, str(e))
        return {"status": "ok", "stream_id": stream_id, "algorithm": algo}

    return router
