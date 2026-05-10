"""
Stream profiles loader — reads the shared ROI/zone config from stream_profiles.json.

This file is the schema contract between the Jetson DeepStream edge pipeline
and the C2 backend.  Both sides reference the same polygon coordinates
defined at a canonical resolution (e.g. 1920×1080).
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_stream_profiles(path: str | Path) -> dict[str, dict[str, Any]]:
    """Load stream_profiles.json and return the ``streams`` mapping.

    Returns an empty dict if the file is missing or unparseable.
    """
    p = Path(path)
    if not p.exists():
        logger.warning("stream_profiles.json not found at %s", p)
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("streams", {})
    except Exception:
        logger.exception("Failed to parse stream_profiles.json")
        return {}


def scale_polygon(
    polygon: list[list[float]],
    src_res: tuple[int, int],
    dst_res: tuple[int, int],
) -> list[list[float]]:
    """Scale a polygon from ``src_res`` (w, h) to ``dst_res`` (w, h).

    Returns integer-rounded coordinates when the result is close to whole
    numbers, otherwise floats.
    """
    if src_res == dst_res:
        return polygon

    sx = dst_res[0] / src_res[0]
    sy = dst_res[1] / src_res[1]
    return [[pt[0] * sx, pt[1] * sy] for pt in polygon]
