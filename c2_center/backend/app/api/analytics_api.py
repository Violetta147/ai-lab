"""C2 Center — Analytics API (algorithm switching + listing)."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.analytics.registry import registry

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def get_router(pipeline):
    """Build the analytics router bound to the live pipeline handle."""

    @router.get("/algorithms")
    async def list_algorithms(
        mode: Literal["live", "offline"] | None = Query(
            default=None,
            description="Filter analyzers by mode. 'live' = safe for RTSP pipeline; "
                        "'offline' = needs calibration, run via playground.",
        ),
    ):
        """List registered analyzers, optionally filtered by mode."""
        return [meta.to_dict() for meta in registry.list_all(mode=mode)]

    @router.put("/algorithm/{stream_id}")
    async def set_algorithm(stream_id: str, body: dict):
        """Attach an analyzer to a live stream.

        Refuses to attach analyzers tagged `offline` to live streams — those
        require calibration and must be run via the playground endpoint.
        """
        algo = body.get("algorithm")
        if not algo or not registry.has(algo):
            raise HTTPException(
                400,
                f"Invalid algorithm. Choose from: {registry.slugs()}",
            )

        algo_mode = registry.get_mode(algo)
        if algo_mode == "offline":
            live_slugs = [m.slug for m in registry.list_all(mode="live")]
            raise HTTPException(
                400,
                f"Algorithm '{algo}' is offline-only (requires calibration). "
                f"Use POST /api/playground/analyze instead. "
                f"Live-compatible algorithms: {live_slugs}",
            )

        try:
            pipeline.analytics_dispatcher.set_algorithm(stream_id, algo)
        except KeyError as e:
            raise HTTPException(400, str(e))
        return {"status": "ok", "stream_id": stream_id, "algorithm": algo}

    @router.get("/algorithm/{stream_id}")
    async def get_algorithm(stream_id: str):
        """Return the currently active algorithm for a stream."""
        slug = pipeline.analytics_dispatcher.get_active_slug(stream_id)
        return {"stream_id": stream_id, "algorithm": slug or "heatmap"}

    return router
