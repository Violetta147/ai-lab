"""Zone domain types — user-drawn polygons and lines on the video plane."""

from dataclasses import dataclass

# Polygon = ordered list of (x, y) integer pixel points.
Polygon = list[tuple[int, int]]


@dataclass(frozen=True)
class LineSegment:
    """A line zone defined by two endpoints (pixels)."""

    p1: tuple[int, int]
    p2: tuple[int, int]

    @classmethod
    def from_pair(cls, pair: list) -> "LineSegment":
        """Build from [[x1,y1],[x2,y2]] payload coming from the frontend."""
        (x1, y1), (x2, y2) = pair[0], pair[1]
        return cls(p1=(int(x1), int(y1)), p2=(int(x2), int(y2)))
