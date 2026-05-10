"""
Analytics plugin registry.

Discovers BaseAnalyzer subclasses under a package and exposes them by slug.
"""

import importlib
import inspect
import logging
import pkgutil

from app.analytics.base import BaseAnalyzer
from app.analytics.contracts import AnalyzerMetadata, AnalyzerMode

logger = logging.getLogger(__name__)

# Heuristic mapping from analyzer slug to its zone/tracker/mode requirements.
# Kept here (not in plugin code) to avoid forcing every plugin to declare
# extra metadata; this list is small and easy to maintain.
#
# mode semantics (Option D — Hybrid):
#   "live"    — safe to run on the live RTSP pipeline (no calibration needed
#               beyond simple polygon/line drawing on the UI)
#   "offline" — must only run in playground/offline analysis because it
#               requires real-world calibration (m², BEV, distance constants)
#   "both"    — runs anywhere
_KNOWN_REQUIREMENTS: dict[str, tuple[bool, bool, AnalyzerMode]] = {
    # slug -> (requires_tracker, requires_zones, mode)
    "heatmap":               (False, False, "live"),
    "absolute_count":        (False, True,  "live"),
    "line_crossing":         (True,  True,  "live"),
    "pce_density":           (False, True,  "offline"),
    "area_occupancy":        (False, True,  "offline"),
    "fundamental_equation":  (True,  True,  "offline"),
}


class AnalyticsRegistry:
    """In-memory registry of analyzer plugin classes keyed by slug."""

    def __init__(self) -> None:
        self._classes: dict[str, type[BaseAnalyzer]] = {}

    def register(self, analyzer_cls: type[BaseAnalyzer]) -> None:
        """Register an analyzer class. Slug must be unique."""
        try:
            slug = analyzer_cls().slug
        except Exception:
            logger.exception("Cannot instantiate analyzer %s for slug discovery", analyzer_cls.__name__)
            return

        if slug in self._classes:
            existing = self._classes[slug].__name__
            logger.warning("Analyzer slug '%s' already registered as %s; overriding with %s", slug, existing, analyzer_cls.__name__)
        self._classes[slug] = analyzer_cls
        logger.info("Registered analyzer: %s -> %s", slug, analyzer_cls.__name__)

    def get(self, slug: str) -> type[BaseAnalyzer]:
        """Return the analyzer class registered under slug."""
        if slug not in self._classes:
            raise KeyError(f"Analyzer not registered: {slug}")
        return self._classes[slug]

    def has(self, slug: str) -> bool:
        return slug in self._classes

    def slugs(self) -> list[str]:
        return list(self._classes.keys())

    def list_all(self, mode: AnalyzerMode | None = None) -> list[AnalyzerMetadata]:
        """Return metadata for every registered analyzer.

        If `mode` is provided, only return analyzers whose declared mode matches
        (analyzers tagged as "both" always pass through any filter).
        """
        out: list[AnalyzerMetadata] = []
        for slug, cls in self._classes.items():
            instance = cls()
            req_tracker, req_zones, declared_mode = _KNOWN_REQUIREMENTS.get(
                slug, (False, False, "both")
            )
            if mode is not None and declared_mode not in (mode, "both"):
                continue
            out.append(
                AnalyzerMetadata(
                    slug=slug,
                    name=instance.name,
                    requires_tracker=req_tracker,
                    requires_zones=req_zones,
                    mode=declared_mode,
                )
            )
        return out

    def get_mode(self, slug: str) -> AnalyzerMode:
        """Return the declared mode for an analyzer (defaults to 'both')."""
        _, _, mode = _KNOWN_REQUIREMENTS.get(slug, (False, False, "both"))
        return mode

    def discover(self, package_name: str) -> int:
        """
        Walk a package and register every concrete BaseAnalyzer subclass found.

        Returns the number of analyzers newly registered.
        """
        package = importlib.import_module(package_name)
        before = len(self._classes)

        for module_info in pkgutil.iter_modules(package.__path__):
            module_name = f"{package_name}.{module_info.name}"
            try:
                module = importlib.import_module(module_name)
            except Exception:
                logger.exception("Failed to import analyzer module: %s", module_name)
                continue

            for _, obj in inspect.getmembers(module, inspect.isclass):
                if obj is BaseAnalyzer:
                    continue
                if not issubclass(obj, BaseAnalyzer):
                    continue
                if inspect.isabstract(obj):
                    continue
                if obj.__module__ != module_name:
                    continue
                self.register(obj)

        return len(self._classes) - before


# Module-level singleton — import this from main.py and api/analytics_api.py
registry = AnalyticsRegistry()
