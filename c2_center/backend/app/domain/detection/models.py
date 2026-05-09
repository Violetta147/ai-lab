"""Detection domain types — Kafka payload schema for a single tracked object."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BoundingBox:
    """Pixel-space bounding box."""

    x: float
    y: float
    w: float
    h: float

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h


@dataclass(frozen=True)
class DetectionObject:
    """One tracked object emitted by DeepStream into Kafka."""

    tracking_id: int
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox

    @classmethod
    def from_payload(cls, payload: dict) -> "DetectionObject":
        bbox = payload.get("bbox", {})
        return cls(
            tracking_id=int(payload.get("tracking_id", -1)),
            class_id=int(payload.get("class_id", 0)),
            class_name=str(payload.get("class_name", "")),
            confidence=float(payload.get("confidence", 0.0)),
            bbox=BoundingBox(
                x=float(bbox.get("x", 0)),
                y=float(bbox.get("y", 0)),
                w=float(bbox.get("w", 0)),
                h=float(bbox.get("h", 0)),
            ),
        )
