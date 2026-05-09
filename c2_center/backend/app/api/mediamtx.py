"""MediaMTX API: preview and deploy mediamtx.yml from backend camera records.

- GET  /api/mediamtx/preview -> return generated config (no write)
- POST /api/mediamtx/deploy  -> write mediamtx.yml to infrastructure folder
"""

from fastapi import APIRouter

from app.infrastructure.mediamtx.client import deploy_config

router = APIRouter(prefix="/api/mediamtx", tags=["mediamtx"])


@router.get("/preview")
async def preview_mediamtx():
    """Return generated mediamtx.yml content without writing."""
    status = deploy_config(write=False)
    return {"status": "preview", "count": status.get("count", 0), "config": status.get("preview", "")}


@router.post("/deploy")
async def deploy_mediamtx():
    """Generate and write mediamtx.yml using the current camera database."""
    status = deploy_config(write=True)
    return {"status": "deployed", "path": status.get("path"), "count": status.get("count", 0)}
