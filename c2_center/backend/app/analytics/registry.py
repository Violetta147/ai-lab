"""
Analytics plugin registry.

Discovers BaseAnalyzer subclasses under a package and exposes them by slug.
"""

import importlib
import inspect
import logging
import pkgutil

from app.analytics.base import BaseAnalyzer
from app.analytics.contracts import AnalyzerMetadata

logger = logging.getLogger(__name__)

# Heuristic mapping from analyzer slug to its zone/tracker requirements.
# Kept here (not in plugin code) to avoid forcing every plugin to declare
# extra metadata; this list is small and easy to maintain.
_KNOWN_REQUIREMENTS: dict[str, tuple[bool, bool]] = {
    # slug -> (requires_tracker, requires_zones)
    "absolute_count": (False, True),
    "area_occupancy": (False, True),
    "pce_density": (False, True),
    "fundamental_equation": (True, True),
    "heatmap": (False, False),
    "line_crossing": (True, True),
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

    def list_all(self) -> list[AnalyzerMetadata]:
        """Return metadata for every registered analyzer."""
        out: list[AnalyzerMetadata] = []
        for slug, cls in self._classes.items():
            instance = cls()
            req_tracker, req_zones = _KNOWN_REQUIREMENTS.get(slug, (False, False))
            out.append(
                AnalyzerMetadata(
                    slug=slug,
                    name=instance.name,
                    requires_tracker=req_tracker,
                    requires_zones=req_zones,
                )
            )
        return out

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
