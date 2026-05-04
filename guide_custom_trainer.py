# %% [markdown]
# # Customizing the Ultralytics Trainer
# Source: https://docs.ultralytics.com/guides/custom-trainer/
#
# The Ultralytics training pipeline is built around `BaseTrainer` and
# task-specific trainers like `DetectionTrainer`. When you need more control
# — tracking custom metrics, adjusting loss weighting, or implementing
# custom LR schedules — you subclass the trainer and override specific methods.
#
# ## How Custom Trainers Work
# The `YOLO` model accepts a `trainer` parameter in `train()`.
# Your custom trainer inherits all functionality from `DetectionTrainer`,
# so you only override the methods you need.
#
# ## Overridable Methods
# | Method | Purpose |
# |--------|---------|
# | `validate()` | Run validation and return metrics |
# | `build_optimizer()` | Construct the optimizer |
# | `save_model()` | Save training checkpoints |
# | `get_model()` | Return the model instance |
# | `get_validator()` | Return the validator instance |
# | `get_dataloader()` | Build the dataloader |
# | `preprocess_batch()` | Preprocess input batch |
# | `label_loss_items()` | Format loss items for logging |

# %% Installation
import subprocess
import sys

def _install(packages: list[str]) -> None:
    for pkg in packages:
        print(f"[SETUP] Installing {pkg}...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-U", pkg],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
    print("[SETUP] All packages installed.")

_install(["ultralytics"])

# %% [markdown]
# ## 1. Logging Custom Metrics (F1 Score)
#
# Override `validate()` to compute and log per-class F1 scores
# at the end of each epoch.

# %% Custom Metrics Trainer
import numpy as np

from ultralytics import YOLO
from ultralytics.models.yolo.detect import DetectionTrainer
from ultralytics.utils import LOGGER


class MetricsTrainer(DetectionTrainer):
    """Computes and logs F1 score at the end of each epoch."""

    def validate(self):
        metrics, fitness = super().validate()
        if metrics is None:
            return metrics, fitness

        if hasattr(self.validator, "metrics") and hasattr(self.validator.metrics, "box"):
            box = self.validator.metrics.box
            f1_per_class = box.f1
            class_indices = box.ap_class_index
            names = self.validator.names

            valid_f1 = f1_per_class[f1_per_class > 0]
            mean_f1: float = float(np.mean(valid_f1)) if len(valid_f1) > 0 else 0.0

            LOGGER.info(f"Mean F1 Score: {mean_f1:.4f}")
            per_class_str: list[str] = [
                f"{names[i]}: {f1_per_class[j]:.3f}"
                for j, i in enumerate(class_indices) if f1_per_class[j] > 0
            ]
            LOGGER.info(f"Per-class F1: {per_class_str}")

        return metrics, fitness


print("[DEBUG] MetricsTrainer defined — logs F1 score per epoch")

# %% [markdown]
# ## 2. Adding Class Weights for Imbalanced Data
#
# Upweight underrepresented classes in the loss function by subclassing
# the loss, model, and trainer. This makes the model penalize
# misclassifications on rare classes more heavily.

# %% Class-Weighted Trainer
import torch
from torch import nn

from ultralytics.models.yolo.detect import DetectionTrainer as DT2
from ultralytics.nn.tasks import DetectionModel
from ultralytics.utils import RANK
from ultralytics.utils.loss import E2ELoss, v8DetectionLoss


class WeightedDetectionLoss(v8DetectionLoss):
    """Detection loss with per-class weights on BCE classification loss."""

    def __init__(self, model, class_weights=None, tal_topk: int = 10, tal_topk2=None):
        super().__init__(model, tal_topk=tal_topk, tal_topk2=tal_topk2)
        if class_weights is not None:
            self.bce = nn.BCEWithLogitsLoss(
                pos_weight=class_weights.to(self.device),
                reduction="none",
            )


class WeightedE2ELoss(E2ELoss):
    """E2E loss with class weights for YOLO26."""

    def __init__(self, model, class_weights=None):
        def weighted_loss_fn(model, tal_topk: int = 10, tal_topk2=None):
            return WeightedDetectionLoss(
                model, class_weights=class_weights, tal_topk=tal_topk, tal_topk2=tal_topk2
            )
        super().__init__(model, loss_fn=weighted_loss_fn)


class WeightedDetectionModel(DetectionModel):
    """Detection model using class-weighted loss."""

    def init_criterion(self):
        class_weights = torch.ones(self.nc)
        class_weights[0] = 2.0  # upweight class 0
        class_weights[1] = 3.0  # upweight rare class 1
        return WeightedE2ELoss(self, class_weights=class_weights)


class WeightedTrainer(DT2):
    """Trainer that returns a WeightedDetectionModel."""

    def get_model(self, cfg=None, weights=None, verbose: bool = True):
        model = WeightedDetectionModel(cfg, nc=self.data["nc"], verbose=verbose and RANK == -1)
        if weights:
            model.load(weights)
        return model


print("[DEBUG] WeightedTrainer defined — class weights [0]=2.0, [1]=3.0")

# %% [markdown]
# ## 3. Saving Best Model by Custom Metric
#
# Override `validate()` to use mAP@0.5 (instead of default fitness)
# for best model selection.

# %% Custom Save Trainer
from ultralytics.models.yolo.detect import DetectionTrainer as DT3


class CustomSaveTrainer(DT3):
    """Saves the best model based on mAP@0.5 instead of default fitness."""

    def validate(self):
        metrics, fitness = super().validate()
        if metrics:
            fitness = metrics.get("metrics/mAP50(B)", fitness)
            if self.best_fitness is None or fitness > self.best_fitness:
                self.best_fitness = fitness
        return metrics, fitness


print("[DEBUG] CustomSaveTrainer defined — best model by mAP@0.5")

# %% [markdown]
# ## 4. Freezing and Unfreezing the Backbone
#
# Freeze pretrained backbone for the first N epochs, letting the
# detection head adapt before fine-tuning the entire network.

# %% Freezing Trainer with Callback
from ultralytics.models.yolo.detect import DetectionTrainer as DT4

FREEZE_EPOCHS: int = 5


def unfreeze_backbone(trainer) -> None:
    """Callback: unfreeze all layers after FREEZE_EPOCHS."""
    if trainer.epoch == FREEZE_EPOCHS:
        LOGGER.info(f"Epoch {trainer.epoch}: Unfreezing all layers")
        for name, param in trainer.model.named_parameters():
            if not param.requires_grad:
                param.requires_grad = True
                LOGGER.info(f"  Unfroze: {name}")
        trainer.freeze_layer_names = [".dfl"]


class FreezingTrainer(DT4):
    """Trainer with backbone freezing for first N epochs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_callback("on_train_epoch_start", unfreeze_backbone)


print(f"[DEBUG] FreezingTrainer defined — freeze backbone for {FREEZE_EPOCHS} epochs")

# %% [markdown]
# ## 5. Per-Layer Learning Rates
#
# Lower LR for pretrained backbone to preserve learned features;
# higher LR for detection head to adapt faster.

# %% Per-Layer LR Trainer
from ultralytics.models.yolo.detect import DetectionTrainer as DT5
from ultralytics.utils.torch_utils import unwrap_model


class PerLayerLRTrainer(DT5):
    """Trainer with different learning rates for backbone and head."""

    def build_optimizer(self, model, name: str = "auto", lr: float = 0.001,
                        momentum: float = 0.9, decay: float = 1e-5, iterations: float = 1e5):
        backbone_params: list = []
        head_params: list = []

        for k, v in unwrap_model(model).named_parameters():
            if not v.requires_grad:
                continue
            is_backbone: bool = any(k.startswith(f"model.{i}.") for i in range(10))
            if is_backbone:
                backbone_params.append(v)
            else:
                head_params.append(v)

        backbone_lr: float = lr * 0.1

        optimizer = torch.optim.AdamW([
            {"params": backbone_params, "lr": backbone_lr, "weight_decay": decay},
            {"params": head_params, "lr": lr, "weight_decay": decay},
        ])

        LOGGER.info(
            f"PerLayerLR: backbone ({len(backbone_params)} params, lr={backbone_lr}) "
            f"| head ({len(head_params)} params, lr={lr})"
        )
        return optimizer


print("[DEBUG] PerLayerLRTrainer defined — backbone lr=0.1x, head lr=1x")

# %% [markdown]
# ## Usage Example
#
# Pass any custom trainer to `model.train()`:
# ```python
# model = YOLO("yolo26n.pt")
# model.train(data="coco8.yaml", epochs=10, trainer=MetricsTrainer)
# ```
#
# These customizations can be combined into a single trainer class
# by overriding multiple methods and adding callbacks as needed.
