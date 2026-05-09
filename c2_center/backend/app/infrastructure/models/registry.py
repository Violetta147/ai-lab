"""
Dynamic ML model registry.

Scans MODELS_DIR for subdirectories containing weight files (.pt/.onnx) plus
labels.txt and lazy-loads YOLO instances on demand.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from ultralytics import YOLO

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Metadata about a discovered model."""

    name: str
    weights_path: Path
    labels: list[str] = field(default_factory=list)
    num_classes: int = 0
    file_size_mb: float = 0.0


class ModelRegistry:
    """
    Scan models/ directory, discover models, load on-demand.

    Directory structure expected:
        ml_models/
        ├── my_model/
        │   ├── best.pt        (or .onnx)
        │   └── labels.txt     (one class name per line)
        └── another_model/
            ├── model.onnx
            └── labels.txt
    """

    def __init__(self, models_dir: Path | None = None) -> None:
        self.models_dir = models_dir or settings.MODELS_DIR
        self._cache: dict[str, YOLO] = {}
        self._registry: dict[str, ModelInfo] = {}
        self._active_model_name: str | None = None

    def scan(self) -> list[ModelInfo]:
        """Scan models/ directory and register all valid models."""
        self._registry.clear()

        if not self.models_dir.exists():
            logger.warning("Models directory not found: %s", self.models_dir)
            self.models_dir.mkdir(parents=True, exist_ok=True)
            return []

        for subdir in sorted(self.models_dir.iterdir()):
            if not subdir.is_dir():
                continue

            weights = list(subdir.glob("*.pt")) + list(subdir.glob("*.onnx"))
            labels_file = subdir / "labels.txt"

            if not weights:
                logger.debug("Skipping %s: no .pt or .onnx file", subdir.name)
                continue

            if not labels_file.exists():
                logger.debug("Skipping %s: no labels.txt", subdir.name)
                continue

            labels = [
                line.strip()
                for line in labels_file.read_text(encoding="utf-8").strip().splitlines()
                if line.strip()
            ]

            weight_file = weights[0]
            info = ModelInfo(
                name=subdir.name,
                weights_path=weight_file,
                labels=labels,
                num_classes=len(labels),
                file_size_mb=weight_file.stat().st_size / (1024 * 1024),
            )
            self._registry[subdir.name] = info
            logger.info(
                "Registered model: %s (%d classes, %.1f MB)",
                info.name,
                info.num_classes,
                info.file_size_mb,
            )

        if self._active_model_name is None and self._registry:
            self._active_model_name = next(iter(self._registry))

        return list(self._registry.values())

    def list_models(self) -> list[ModelInfo]:
        """Return list of registered models."""
        return list(self._registry.values())

    def get_model_info(self, name: str) -> ModelInfo | None:
        """Get metadata for a specific model."""
        return self._registry.get(name)

    def get_model(self, name: str) -> YOLO:
        """Lazy-load and cache a YOLO model by name."""
        if name not in self._registry:
            raise ValueError(f"Model not found: {name}")

        if name not in self._cache:
            info = self._registry[name]
            logger.info("Loading model: %s from %s", name, info.weights_path)
            self._cache[name] = YOLO(str(info.weights_path))
            logger.info("Model loaded: %s", name)

        return self._cache[name]

    def get_labels(self, name: str) -> list[str]:
        """Get class labels for a model."""
        info = self._registry.get(name)
        if info is None:
            raise ValueError(f"Model not found: {name}")
        return info.labels

    @property
    def active_model_name(self) -> str | None:
        """Currently active model for playground inference."""
        return self._active_model_name

    @active_model_name.setter
    def active_model_name(self, name: str) -> None:
        if name not in self._registry:
            raise ValueError(f"Model not found: {name}")
        self._active_model_name = name
        logger.info("Active model set to: %s", name)

    def get_active_model(self) -> YOLO | None:
        """Get the currently active YOLO model instance."""
        if self._active_model_name is None:
            return None
        return self.get_model(self._active_model_name)
