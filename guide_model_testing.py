# %% [markdown]
# # Model Testing Guide with YOLO26
# Source: https://docs.ultralytics.com/guides/model-testing/
#
# After training a model, rigorous testing is essential to ensure it performs
# well on unseen data. This guide covers model testing methodology, detecting
# overfitting/underfitting, preventing data leakage, and using YOLO26
# validation and prediction modes for thorough evaluation.
#
# ## Model Testing vs. Model Evaluation
#
# | Aspect | Model Evaluation | Model Testing |
# |--------|-----------------|---------------|
# | **Data Used** | Validation set (during training) | Separate, unseen test set |
# | **Purpose** | Tune hyperparameters, prevent overfitting | Assess real-world performance |
# | **When** | After each epoch during training | After all training and tuning is done |
# | **Key Metrics** | mAP50, mAP50-95, Precision, Recall | Same metrics on truly unseen data |
#
# Key: **evaluation** guides training; **testing** confirms the model is ready for deployment.

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
# ## Preparing Test Data
#
# Your test set must:
# 1. **Be unseen** — never used during training or hyperparameter tuning
# 2. **Be representative** — reflect the diversity of real-world scenarios
# 3. **Be properly annotated** — high-quality labels in the same format
#
# ### Data Split Guidelines
# - **Training**: 70% of total data
# - **Validation**: 15% — used during training for early stopping / HP tuning
# - **Test**: 15% — held out until final testing
#
# ### Annotated YAML Format
# ```yaml
# # dataset.yaml
# path: /path/to/dataset
# train: images/train
# val: images/val
# test: images/test
#
# names:
#   0: class_a
#   1: class_b
# ```

# %% Load YOLO26 Model
from ultralytics import YOLO

MODEL_PATH: str = "yolo26n.pt"
model = YOLO(MODEL_PATH)
print(f"[DEBUG] Loaded model: {MODEL_PATH}")
print(f"[DEBUG] Model task: {model.task}")
print(f"[DEBUG] Model classes: {model.names}")

# %% [markdown]
# ## Validation Mode
#
# Validation computes precision, recall, mAP50, and mAP50-95 across the
# entire test/validation set. This is the most rigorous quantitative check.
#
# Parameters:
# - `data`: path to dataset YAML with a `test:` split
# - `split`: which split to evaluate — use `"test"` for final testing
# - `imgsz`: image size (must match training config)
# - `batch`: batch size (use `16` for safe GPU usage)
# - `conf`: confidence threshold for predictions
# - `iou`: IoU threshold for NMS

# %% Run Validation on Test Split
DATASET_YAML: str = "path/to/dataset.yaml"  # UPDATE THIS to your dataset YAML
IMAGE_SIZE: int = 640
BATCH_SIZE: int = 16
CONF_THRESHOLD: float = 0.001
IOU_THRESHOLD: float = 0.6

print(f"[DEBUG] Running validation on test split...")
print(f"[DEBUG] Dataset: {DATASET_YAML}")
print(f"[DEBUG] Image size: {IMAGE_SIZE}, Batch: {BATCH_SIZE}")
print(f"[DEBUG] Conf threshold: {CONF_THRESHOLD}, IoU threshold: {IOU_THRESHOLD}")

metrics = model.val(
    data=DATASET_YAML,
    split="test",
    imgsz=IMAGE_SIZE,
    batch=BATCH_SIZE,
    conf=CONF_THRESHOLD,
    iou=IOU_THRESHOLD,
    plots=True,
    save_json=True,
)

# %% Inspect Validation Metrics
print(f"[DEBUG] === Test Set Metrics ===")
print(f"  mAP50:     {metrics.box.map50:.4f}")
print(f"  mAP50-95:  {metrics.box.map:.4f}")
print(f"  Precision:  {metrics.box.mp:.4f}")
print(f"  Recall:     {metrics.box.mr:.4f}")

print(f"\n[DEBUG] Per-class mAP50:")
for i, class_name in model.names.items():
    ap50: float = metrics.box.ap50[i] if i < len(metrics.box.ap50) else 0.0
    print(f"  {class_name}: {ap50:.4f}")

# %% [markdown]
# ## Prediction Mode
#
# Use prediction mode to run the model on individual test images and
# visually inspect detections. Useful for qualitative assessment
# beyond aggregate metrics.

# %% Predict on Test Images
import os
from pathlib import Path

TEST_IMAGES_DIR: str = "path/to/test/images"  # UPDATE THIS

print(f"[DEBUG] Running predictions on test images from: {TEST_IMAGES_DIR}")

results = model.predict(
    source=TEST_IMAGES_DIR,
    imgsz=IMAGE_SIZE,
    conf=0.25,
    save=True,
    save_txt=True,
    save_conf=True,
    project="runs/test_predictions",
    name="yolo26n_test",
)

print(f"[DEBUG] Predicted on {len(results)} images")

for result in results[:5]:
    boxes = result.boxes
    print(f"[DEBUG] Image: {Path(result.path).name}")
    print(f"  Detections: {len(boxes)}")
    if len(boxes) > 0:
        classes_detected: list[str] = [model.names[int(c)] for c in boxes.cls.cpu().numpy()]
        confs: list[float] = boxes.conf.cpu().numpy().tolist()
        for cls_name, conf in zip(classes_detected, confs):
            print(f"    {cls_name}: {conf:.3f}")

# %% [markdown]
# ## Running Pretrained Model Without Custom Training
#
# YOLO26 pretrained on COCO can be tested directly on any image set
# to establish baseline performance before fine-tuning.

# %% Pretrained Model Predictions
pretrained = YOLO("yolo26n.pt")
print("[DEBUG] Running pretrained COCO model on sample images...")

pretrained_results = pretrained.predict(
    source="https://ultralytics.com/images/bus.jpg",
    imgsz=640,
    conf=0.25,
    save=True,
    project="runs/pretrained_test",
    name="coco_baseline",
)

for r in pretrained_results:
    print(f"[DEBUG] Pretrained detections: {len(r.boxes)}")
    for box in r.boxes:
        cls_id: int = int(box.cls.item())
        conf_val: float = float(box.conf.item())
        print(f"  {pretrained.names[cls_id]}: {conf_val:.3f}")

# %% [markdown]
# ## Overfitting and Underfitting
#
# ### Overfitting Signs
# - **High training accuracy, low test accuracy** — the model memorized training data
# - **Training loss decreasing, validation loss increasing** — gap grows over epochs
# - **Near-perfect mAP on train set but much lower on test set**
#
# ### Overfitting Strategies
# - **More data**: increase dataset size or use augmentation
# - **Regularization**: increase `weight_decay`, use dropout
# - **Early stopping**: stop training when validation metrics plateau
# - **Reduce model complexity**: use a smaller model variant (e.g., `yolo26n` vs `yolo26x`)
#
# ### Underfitting Signs
# - **Low accuracy on both training and test sets**
# - **Training loss not decreasing** — model cannot learn patterns
# - **Low mAP across all classes**
#
# ### Underfitting Strategies
# - **Increase model capacity**: use a larger variant
# - **Train longer**: increase epochs
# - **Tune learning rate**: try higher initial LR or different schedulers
# - **Check data quality**: ensure labels are correct and data is not corrupted

# %% [markdown]
# ## Data Leakage
#
# Data leakage occurs when information from the test/validation set
# "leaks" into training, producing misleadingly optimistic metrics.
#
# ### Common Causes
# - **Duplicate images** across train/test splits
# - **Overlapping video frames** — consecutive frames in different splits
# - **Pre-processing on full dataset** — e.g., computing normalization stats on all data
# - **Augmented copies** — augmented version in train, original in test
#
# ### Detection
# - Suspiciously high test metrics (mAP50 > 0.95 on a hard task)
# - Train and test metrics nearly identical
# - Performance drops dramatically on truly new data
#
# ### Prevention
# - Split data BEFORE any augmentation or preprocessing
# - Check for duplicate filenames / image hashes across splits
# - For video data, split by video clip (not individual frames)
# - Compute normalization stats only on the training set

# %% [markdown]
# ## Post-Testing Next Steps
#
# 1. **Document results**: record metrics, save confusion matrices, PR curves
# 2. **Compare baselines**: compare against pretrained and previous model versions
# 3. **Error analysis**: examine false positives and false negatives
# 4. **Deploy or iterate**: if metrics meet requirements, export and deploy;
#    otherwise, iterate on data or hyperparameters
#
# ### Export for Deployment
# ```python
# model.export(format="onnx", imgsz=640)
# model.export(format="engine", imgsz=640)  # TensorRT
# ```
