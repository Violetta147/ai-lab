"""C2 Center — Zones API (CRUD for polygon/line coordinates)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/zones", tags=["zones"])

# In-memory zone store: stream_id -> {roi_polygon, entry_line, exit_line, ...}
zone_store: dict[str, dict] = {}


@router.get("/{stream_id}")
async def get_zones(stream_id: str):
    return zone_store.get(stream_id, {})


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
    current = zone_store.get(stream_id, {})
    current.update(data)
    zone_store[stream_id] = current
    return {"status": "ok", "stream_id": stream_id, "zones": current}


@router.delete("/{stream_id}")
async def clear_zones(stream_id: str):
    zone_store.pop(stream_id, None)
    return {"status": "cleared", "stream_id": stream_id}
