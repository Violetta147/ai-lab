"""C2 Center — Zones API (CRUD for polygon/line coordinates)."""

from fastapi import APIRouter

from app.infrastructure.database.zone_repository import zone_repo

router = APIRouter(prefix="/api/zones", tags=["zones"])


@router.get("/{stream_id}")
async def get_zones(stream_id: str):
    return zone_repo.get(stream_id, {})


@router.put("/{stream_id}")
async def set_zones(stream_id: str, data: dict):
    """
    Expected body (all optional):
    {
        "roi_polygon": [[x1,y1],[x2,y2],...],
        "entry_line": [[x1,y1],[x2,y2]],
        "exit_line": [[x1,y1],[x2,y2]],
        "road_length_km": 0.1,
        "line_distance_km": 0.02
    }
    """
    current = zone_repo.get(stream_id, {})
    current.update(data)
    zone_repo.set(stream_id, current)
    return {"status": "ok", "stream_id": stream_id, "zones": current}


@router.delete("/{stream_id}")
async def clear_zones(stream_id: str):
    zone_repo.delete(stream_id)
    return {"status": "cleared", "stream_id": stream_id}
