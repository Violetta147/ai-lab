"""C2 Center — Models API (list available models, switch active)."""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/models", tags=["models"])


def get_router(model_registry):
    @router.get("")
    async def list_models():
        models = model_registry.list_models()
        return {
            "active": model_registry.active_model_name,
            "models": [
                {
                    "name": m.name,
                    "num_classes": m.num_classes,
                    "labels": m.labels,
                    "file_size_mb": round(m.file_size_mb, 1),
                }
                for m in models
            ],
        }

    @router.put("/active")
    async def set_active(body: dict):
        name = body.get("name")
        if not name:
            raise HTTPException(400, "Missing 'name' field")
        try:
            model_registry.active_model_name = name
        except ValueError as e:
            raise HTTPException(404, str(e))
        return {"status": "ok", "active": name}

    return router
