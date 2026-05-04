# %% [markdown]
# # Model Training Tips and Best Practices
# Source: https://docs.ultralytics.com/guides/model-training-tips/
#
# Best practices for training computer vision models efficiently:
# batch size, GPU utilization, mixed precision, pretrained weights,
# early stopping, optimizer selection, and more.
#
# ## How Training Works
# 1. Model makes predictions on training images
# 2. Errors computed against ground truth labels
# 3. **Backpropagation** adjusts weights to reduce errors
# 4. Repeat for many epochs until convergence

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
# ## Batch Size and GPU Utilization
#
# - **Maximize batch size** within GPU memory for full utilization
# - If OOM errors occur, reduce incrementally
# - `batch=-1` in YOLO26 auto-determines optimal batch size
#
# ## Subset Training
# - Train on a fraction of data for rapid prototyping
# - `fraction=0.1` uses 10% of data
# - Useful for early experiments before full training

# %% Demo — Auto Batch Size
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
print("[DEBUG] Model loaded: yolo26n.pt")

DATASET: str = "coco8.yaml"  # UPDATE for your dataset

print("[DEBUG] Training with auto batch size (batch=-1)...")
results = model.train(
    data=DATASET,
    epochs=3,
    imgsz=640,
    batch=-1,
    project="runs/training_tips",
    name="auto_batch",
)
print("[DEBUG] Auto-batch training complete")

# %% [markdown]
# ## Multi-Scale Training
#
# Train on images of varying sizes to improve generalization across
# different object scales and distances.
#
# Two approaches in YOLO26:
# - `scale=0.5`: randomly zooms images by factor 0.5–1.5, pads/crops to `imgsz`
# - `multi_scale=0.25`: changes `imgsz` itself each batch (e.g., 480–800 for imgsz=640)

# %% Multi-Scale Training Demo
print("[DEBUG] Training with multi-scale (scale=0.5)...")
model_ms = YOLO("yolo26n.pt")
results_ms = model_ms.train(
    data=DATASET,
    epochs=3,
    imgsz=640,
    scale=0.5,
    project="runs/training_tips",
    name="multi_scale",
)
print("[DEBUG] Multi-scale training complete")

# %% [markdown]
# ## Caching
#
# Store preprocessed images in memory to reduce disk I/O bottlenecks:
# - `cache=True`: store in RAM (fastest, high memory)
# - `cache='disk'`: store on disk (moderate speed)
# - `cache=False`: no caching (slowest, default)
#
# ## Mixed Precision Training (AMP)
#
# Uses FP16 for computation and FP32 for weight updates:
# - Faster training (reduced compute)
# - Lower memory usage (smaller activations)
# - No significant accuracy loss
# - Enable with `amp=True` (default in YOLO26)
#
# ## Pretrained Weights (Transfer Learning)
#
# Start from weights trained on large datasets (COCO, ImageNet):
# - Faster convergence
# - Better accuracy with less data
# - `pretrained=True` uses default YOLO26 COCO weights
# - Can specify custom pretrained model path

# %% Transfer Learning Demo
print("[DEBUG] Training with pretrained weights (transfer learning)...")
model_tl = YOLO("yolo26n.pt")
results_tl = model_tl.train(
    data=DATASET,
    epochs=3,
    imgsz=640,
    batch=16,
    amp=True,
    cache=True,
    project="runs/training_tips",
    name="transfer_learning",
)
print("[DEBUG] Transfer learning training complete")

# %% [markdown]
# ## Number of Epochs
#
# - Start with **300 epochs** as baseline
# - If overfitting early → reduce epochs
# - If not overfitting at 300 → extend to 600, 1200, or more
# - Larger datasets may need more epochs
# - Monitor validation loss to decide
#
# ## Early Stopping
#
# Halt training when validation metrics stop improving:
# - `patience=5`: stop after 5 epochs without improvement
# - Saves compute resources
# - Prevents overfitting
# - Built into YOLO26 training

# %% Early Stopping Demo
print("[DEBUG] Training with early stopping (patience=5)...")
model_es = YOLO("yolo26n.pt")
results_es = model_es.train(
    data=DATASET,
    epochs=50,
    imgsz=640,
    batch=16,
    patience=5,
    project="runs/training_tips",
    name="early_stopping",
)
print("[DEBUG] Early stopping training complete")

# %% [markdown]
# ## Choosing an Optimizer
#
# | Optimizer | Description | Best For |
# |-----------|-------------|----------|
# | **SGD** | Classic gradient descent with momentum | Generalization, simple tasks |
# | **Adam** | Adaptive LR per parameter | Noisy data, sparse gradients |
# | **AdamW** | Adam with decoupled weight decay | Default choice for YOLO26 |
# | **MuSGD** | Muon + SGD hybrid for stability | Large-scale training |
# | **NAdam** | Adam with Nesterov momentum | Faster convergence |
# | **RMSProp** | Adaptive LR, running gradient average | RNNs, vanishing gradients |
# | **auto** | Automatic selection based on model | When unsure |
#
# YOLO26 supports all these via the `optimizer` parameter.

# %% Optimizer Comparison Setup
OPTIMIZERS: list[str] = ["SGD", "AdamW"]

for opt in OPTIMIZERS:
    print(f"[DEBUG] Training with optimizer={opt}...")
    m = YOLO("yolo26n.pt")
    m.train(
        data=DATASET,
        epochs=3,
        imgsz=640,
        batch=16,
        optimizer=opt,
        project="runs/training_tips",
        name=f"optimizer_{opt}",
    )
    print(f"[DEBUG] Training with {opt} complete")

# %% [markdown]
# ## Cloud vs Local Training
#
# | Factor | Cloud | Local |
# |--------|-------|-------|
# | Scalability | High (on-demand GPUs) | Limited by hardware |
# | Cost | Pay-per-use (can be expensive) | One-time hardware cost |
# | Data Privacy | Data leaves premises | Data stays local |
# | Setup | Managed services | Manual maintenance |
# | Latency | Network transfer overhead | Direct access |
#
# ## Summary
# - Maximize batch size within GPU memory (`batch=-1`)
# - Use mixed precision (`amp=True`) for speed
# - Start with pretrained weights for transfer learning
# - Begin with 300 epochs, use early stopping (`patience=5`)
# - Try `optimizer="auto"` or compare SGD vs AdamW
# - Use multi-scale training for robustness
# - Cache data in RAM for faster I/O
