"""Analytics plugin contracts — metadata describing each registered analyzer."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalyzerMetadata:
    """Static metadata about a registered analyzer plugin."""

    slug: str
    name: str
    requires_tracker: bool
    requires_zones: bool

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "requires_tracker": self.requires_tracker,
            "requires_zones": self.requires_zones,
        }
