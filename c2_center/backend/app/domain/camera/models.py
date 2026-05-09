"""Camera domain types."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Camera:
    """A configured RTSP camera source."""

    stream_id: str
    rtsp_url: str
    name: str
    description: str
    enabled: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: tuple) -> "Camera":
        """Build Camera from a sqlite row of the cameras table."""
        return cls(
            stream_id=row[0],
            rtsp_url=row[1],
            name=row[2],
            description=row[3],
            enabled=bool(row[4]),
            created_at=row[5],
            updated_at=row[6],
        )

    def to_dict(self) -> dict:
        """Serialize to API-facing dict."""
        return {
            "stream_id": self.stream_id,
            "rtsp_url": self.rtsp_url,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
