"""Converters between Kafka detection payloads and supervision data structures."""

import logging

import numpy as np
import supervision as sv

logger = logging.getLogger(__name__)

# Process-wide flag: warn at most once when DeepStream metadata lacks tracker IDs.
_missing_tracker_warned = False


def metadata_to_detections(objects: list[dict]) -> sv.Detections:
    """Convert a list of Kafka payload objects into a supervision Detections.

    A bbox is expected to be {"x", "y", "w", "h"} in pixels. Missing
    tracking_id surfaces as -1 and triggers a single warning per process.
    """
    global _missing_tracker_warned

    if not objects:
        return sv.Detections.empty()

    xyxy: list[list[float]] = []
    confs: list[float] = []
    class_ids: list[int] = []
    tracker_ids: list[int] = []

    for obj in objects:
        bbox = obj.get("bbox")
        if isinstance(bbox, list) and len(bbox) == 4:
            # Format: [x1, y1, x2, y2]
            xyxy.append([float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])])
        elif isinstance(bbox, dict):
            # Format: {"x": ..., "y": ..., "w": ..., "h": ...}
            x = float(bbox.get("x", 0))
            y = float(bbox.get("y", 0))
            w = float(bbox.get("w", 0))
            h = float(bbox.get("h", 0))
            xyxy.append([x, y, x + w, y + h])
        else:
            xyxy.append([0.0, 0.0, 0.0, 0.0])
        confs.append(float(obj.get("confidence", 0.5)))
        class_ids.append(int(obj.get("class_id", 0)))

        t_id = int(obj.get("tracking_id", -1))
        if t_id == -1 and not _missing_tracker_warned:
            logger.warning(
                "Missing tracking_id in Kafka metadata; analytics relying on tracking may fail."
            )
            _missing_tracker_warned = True
        tracker_ids.append(t_id)

    kwargs = {
        "xyxy": np.array(xyxy, dtype=np.float32),
        "confidence": np.array(confs, dtype=np.float32),
        "class_id": np.array(class_ids, dtype=int),
    }
    
    if any(t_id != -1 for t_id in tracker_ids):
        kwargs["tracker_id"] = np.array(tracker_ids, dtype=int)

    return sv.Detections(**kwargs)
