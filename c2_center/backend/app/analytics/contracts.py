"""Analytics plugin contracts — metadata describing each registered analyzer."""

from dataclasses import dataclass
from typing import Literal

# "live"    — appropriate for the live RTSP pipeline (no heavy calibration)
# "offline" — must run in playground (requires user calibration / dense state)
# "both"    — runs anywhere
AnalyzerMode = Literal["live", "offline", "both"]


@dataclass(frozen=True)
class AnalyzerMetadata:
    """Static metadata about a registered analyzer plugin."""

    slug: str
    name: str
    requires_tracker: bool
    requires_zones: bool
    mode: AnalyzerMode
    geometry_type: Literal["polygon", "line", "dual_line", "none"] = "none"
    example_params: dict | None = None

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "requires_tracker": self.requires_tracker,
            "requires_zones": self.requires_zones,
            "mode": self.mode,
            "geometry_type": self.geometry_type,
            "example_params": self.example_params,
        }
