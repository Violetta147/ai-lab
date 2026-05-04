"""C2 Center — Cameras API (CRUD for camera sources)."""

from fastapi import APIRouter, HTTPException
from services.camera_db import camera_db

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


def get_router(video_reader):
    @router.get("")
    async def list_cameras(enabled_only: bool = False):
        """List all cameras or only enabled ones."""
        cameras = camera_db.list_cameras(enabled_only=enabled_only)
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
            camera = camera_db.add_camera(
                stream_id=body["stream_id"],
                rtsp_url=body["rtsp_url"],
                name=body["name"],
                description=body.get("description", ""),
                enabled=body.get("enabled", True),
            )
            
            # Heartbeat monitor will start the stream when the RTSP path is reachable.
            return {"status": "created", "camera": camera}
        except ValueError as e:
            raise HTTPException(400, str(e))

    @router.get("/{stream_id}")
    async def get_camera(stream_id: str):
        """Get camera details."""
        camera = camera_db.get_camera(stream_id)
        if not camera:
            raise HTTPException(404, f"Camera not found: {stream_id}")
        return camera

    @router.put("/{stream_id}")
    async def update_camera(stream_id: str, body: dict):
        """
        Update camera details.
        
        Body (all fields optional):
        {
            "rtsp_url": "...",
            "name": "...",
            "description": "...",
            "enabled": true/false
        }
        """
        try:
            camera = camera_db.update_camera(stream_id, **body)
            
            # If enabled status changed, remove stream when disabled (heartbeat will add when re-enabled)
            if "enabled" in body:
                if not body["enabled"]:
                    video_reader.remove_stream(stream_id)

            # If RTSP URL changed, remove existing stream to force heartbeat re-check
            if "rtsp_url" in body:
                video_reader.remove_stream(stream_id)

            return {"status": "updated", "camera": camera}
        except ValueError as e:
            raise HTTPException(404, str(e))

    @router.delete("/{stream_id}")
    async def delete_camera(stream_id: str):
        """Delete a camera source."""
        # Stop the video reader first
        video_reader.remove_stream(stream_id)
        
        # Delete from database
        deleted = camera_db.delete_camera(stream_id)
        if not deleted:
            raise HTTPException(404, f"Camera not found: {stream_id}")
        
        return {"status": "deleted", "stream_id": stream_id}

    return router
