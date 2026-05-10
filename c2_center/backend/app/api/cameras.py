"""C2 Center — Cameras API (CRUD for camera sources)."""

from fastapi import APIRouter, HTTPException

from app.infrastructure.database.camera_repository import camera_repo

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


def get_router(pipeline):
    """Build the cameras router bound to the live pipeline handle."""

    @router.get("")
    async def list_cameras(enabled_only: bool = False):
        cameras = camera_repo.list_cameras(enabled_only=enabled_only)
        return {
            "count": len(cameras),
            "cameras": cameras,
        }

    @router.post("")
    async def add_camera(body: dict):
        """
        Add a new camera source.

        Body:
        {
            "stream_id": "stream_3",
            "rtsp_url": "rtsp://192.168.1.100:554/stream",
            "name": "Parking Lot",
            "description": "Main entrance",
            "enabled": true
        }
        """
        required = ["stream_id", "rtsp_url", "name"]
        for field in required:
            if field not in body:
                raise HTTPException(400, f"Missing required field: {field}")

        try:
            camera = camera_repo.add_camera(
                stream_id=body["stream_id"],
                rtsp_url=body["rtsp_url"],
                name=body["name"],
                description=body.get("description", ""),
                enabled=body.get("enabled", True),
            )
            if camera.get("enabled", True):
                pipeline.add_stream(camera["stream_id"], camera["rtsp_url"])
            return {"status": "created", "camera": camera}
        except ValueError as e:
            raise HTTPException(400, str(e))

    @router.get("/{stream_id}")
    async def get_camera(stream_id: str):
        camera = camera_repo.get_camera(stream_id)
        if not camera:
            raise HTTPException(404, f"Camera not found: {stream_id}")
        return camera

    @router.put("/{stream_id}")
    async def update_camera(stream_id: str, body: dict):
        """Update camera details (any subset of rtsp_url, name, description, enabled)."""
        try:
            camera = camera_repo.update_camera(stream_id, **body)

            if "enabled" in body:
                if not body["enabled"]:
                    pipeline.remove_stream(stream_id)
                else:
                    pipeline.add_stream(stream_id, camera["rtsp_url"])

            if "rtsp_url" in body:
                pipeline.remove_stream(stream_id)
                if camera.get("enabled", True):
                    pipeline.add_stream(stream_id, camera["rtsp_url"])

            return {"status": "updated", "camera": camera}
        except ValueError as e:
            raise HTTPException(404, str(e))

    @router.delete("/{stream_id}")
    async def delete_camera(stream_id: str):
        pipeline.remove_stream(stream_id)
        deleted = camera_repo.delete_camera(stream_id)
        if not deleted:
            raise HTTPException(404, f"Camera not found: {stream_id}")
        return {"status": "deleted", "stream_id": stream_id}

    @router.post("/{stream_id}/reconnect")
    async def reconnect_camera(stream_id: str):
        """Manually trigger connection to a camera stream."""
        camera = camera_repo.get_camera(stream_id)
        if not camera:
            raise HTTPException(404, f"Camera not found: {stream_id}")
        
        # Check if already connected
        if pipeline.video_reader.is_stream_connected(stream_id):
            return {"status": "already_connected"}
        
        if not camera.get("enabled", True):
            return {"status": "camera_disabled"}
            
        success = pipeline.add_stream(stream_id, camera["rtsp_url"])
        return {"status": "reconnected" if success else "failed"}

    return router
