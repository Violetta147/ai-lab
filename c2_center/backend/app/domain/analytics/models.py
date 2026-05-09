"""Analytics domain types — outputs produced by analyzers."""

from dataclasses import dataclass, field

import numpy as np


@dataclass
class AnalysisResult:
    """Result returned by every BaseAnalyzer.process() call."""

    annotated_frame: np.ndarray
    metrics: dict = field(default_factory=dict)
