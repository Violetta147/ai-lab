"""Analytics package — register all analyzers here."""

from analytics.absolute_count import AbsoluteCountAnalyzer
from analytics.area_occupancy import AreaOccupancyAnalyzer
from analytics.base import BaseAnalyzer
from analytics.fundamental_equation import FundamentalEquationAnalyzer
from analytics.heatmap import HeatmapAnalyzer
from analytics.line_crossing import LineCrossingAnalyzer
from analytics.pce_density import PCEDensityAnalyzer

# Registry: slug -> class
ANALYZER_REGISTRY: dict[str, type[BaseAnalyzer]] = {
    "absolute_count": AbsoluteCountAnalyzer,
    "area_occupancy": AreaOccupancyAnalyzer,
    "pce_density": PCEDensityAnalyzer,
    "fundamental_equation": FundamentalEquationAnalyzer,
    "heatmap": HeatmapAnalyzer,
    "line_crossing": LineCrossingAnalyzer,
}

__all__ = ["ANALYZER_REGISTRY", "BaseAnalyzer"]
