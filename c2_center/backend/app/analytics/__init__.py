"""Analytics package: base contract, registry, plugins.

Plugins are discovered at runtime by `registry.discover('app.analytics.plugins')`.
The legacy ``ANALYZER_REGISTRY`` dict is kept as a backwards-compatibility view
into the same registry storage so older callers still work.
"""

from app.analytics.base import AnalysisResult, BaseAnalyzer
from app.analytics.contracts import AnalyzerMetadata
from app.analytics.registry import AnalyticsRegistry, registry

# Backwards-compat: dict view {slug: class} backed by the registry singleton.
ANALYZER_REGISTRY: dict[str, type[BaseAnalyzer]] = registry._classes  # noqa: SLF001

__all__ = [
    "ANALYZER_REGISTRY",
    "AnalysisResult",
    "AnalyticsRegistry",
    "AnalyzerMetadata",
    "BaseAnalyzer",
    "registry",
]
