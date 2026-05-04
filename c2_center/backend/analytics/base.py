"""
C2 Center — Analytics Base Interface

All traffic analysis algorithms implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np
import supervision as sv


@dataclass
class AnalysisResult:
    """Result from an analytics processor."""

    annotated_frame: np.ndarray
    metrics: dict = field(default_factory=dict)


class BaseAnalyzer(ABC):
    """
    Abstract base class for traffic analytics algorithms.

    All analyzers receive:
        - frame: raw video frame (np.ndarray, BGR)
        - detections: sv.Detections from metadata or local inference
        - params: user-configurable parameters (zone coords, thresholds, etc.)

    All analyzers return:
        - AnalysisResult with annotated frame + metrics dict
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable algorithm name."""
        ...

    @property
    @abstractmethod
    def slug(self) -> str:
        """URL-safe identifier."""
        ...

    @abstractmethod
    def process(
        self,
        frame: np.ndarray,
        detections: sv.Detections,
        params: dict,
    ) -> AnalysisResult:
        """Process a single frame and return annotated result + metrics."""
        ...

    def reset(self) -> None:
        """Reset internal state (e.g., sliding windows, accumulators)."""
        pass
