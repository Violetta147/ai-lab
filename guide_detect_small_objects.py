# %% [markdown]
# # Detecting Small Objects — Inference & Pre-Processing Strategies
# Source: https://blog.roboflow.com/detect-small-objects/
#
# Small objects are notoriously difficult for detection models.
# COCO defines a "small" object as smaller than 32x32 pixels. These objects
# produce weak feature representations in deep layers and are easily
# overwhelmed by larger objects in the same scene.
#
# ## Why Small Object Detection Is Hard
# - **Low resolution**: small objects have very few pixels, limiting feature richness
# - **Downsampling loss**: CNN backbones progressively reduce spatial resolution
# - **Imbalanced anchors**: default anchor sizes are designed for medium/large objects
# - **NMS suppression**: nearby small detections can be incorrectly suppressed
# - **Annotation noise**: a 1-pixel labeling error on a 10x10 object is 10% IoU shift
#
# This guide covers two categories of optimizations:
# 1. **Inference-time**: tiling / slicing strategies (InferenceSlicer, SAHI)
# 2. **Pre-processing**: data preparation, augmentation, and model configuration

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

_install(["ultralytics", "supervision", "inference"])

# %% [markdown]
# ---
# # Part 1: Inference Optimizations
#
# ## InferenceSlicer (Supervision)
#
# `supervision.InferenceSlicer` divides a large image into overlapping tiles,
# runs detection on each tile, and merges the results back onto the original
# image using configurable overlap filtering.
#
# ### How It Works
# 1. The image is sliced into a grid (e.g., 2x2, 3x3)
# 2. Each tile is independently passed through the detector
# 3. Detections are mapped back to original image coordinates
# 4. Overlap filtering removes duplicate boxes from tile boundaries

# %% InferenceSlicer — Basic Usage
import cv2
import numpy as np
import supervision as sv

SOURCE_IMAGE_PATH: str = "path/to/your/image.jpg"  # UPDATE THIS


def slicer_callback(image_slice: np.ndarray) -> sv.Detections:
    """Callback function for InferenceSlicer. Runs YOLO on each slice."""
    from ultralytics import YOLO
    model = YOLO("yolo26n.pt")
    results = model(image_slice, verbose=False)[0]
    return sv.Detections.from_ultralytics(results)


slicer = sv.InferenceSlicer(
    callback=slicer_callback,
    slice_wh=(320, 320),
    overlap_ratio_wh=(0.2, 0.2),
    overlap_filter_strategy=sv.OverlapFilter.NON_MAX_SUPPRESSION,
    iou_threshold=0.5,
)

print("[DEBUG] InferenceSlicer configured: 320x320 tiles, 0.2 overlap, NMS filtering")

image: np.ndarray = cv2.imread(SOURCE_IMAGE_PATH)
if image is not None:
    detections: sv.Detections = slicer(image)
    print(f"[DEBUG] Detections with slicing: {len(detections)}")

    annotator = sv.BoxAnnotator()
    annotated = annotator.annotate(scene=image.copy(), detections=detections)
    cv2.imwrite("output_sliced_detections.jpg", annotated)
    print("[DEBUG] Annotated image saved to output_sliced_detections.jpg")
else:
    print(f"[DEBUG] Could not load image from {SOURCE_IMAGE_PATH} — update the path")

# %% [markdown]
# ## Overlap Filtering Strategies
#
# When tiles overlap, the same object may be detected in multiple tiles.
# `InferenceSlicer` supports three strategies to handle this:
#
# | Strategy | Behavior | Best For |
# |----------|----------|----------|
# | `NON_MAX_SUPPRESSION` | Keeps highest-confidence box, suppresses lower ones with IoU > threshold | Dense scenes with many overlapping objects |
# | `NON_MAX_MERGE` | Merges overlapping boxes by averaging coordinates | Spread-out objects that span tile boundaries |
# | `NONE` | No filtering — keeps all detections from all tiles | Debugging or custom post-processing |

# %% Overlap Filtering Comparison
STRATEGIES: dict[str, sv.OverlapFilter] = {
    "NMS": sv.OverlapFilter.NON_MAX_SUPPRESSION,
    "NMM": sv.OverlapFilter.NON_MAX_MERGE,
    "NONE": sv.OverlapFilter.NONE,
}

if image is not None:
    for name, strategy in STRATEGIES.items():
        s = sv.InferenceSlicer(
            callback=slicer_callback,
            slice_wh=(320, 320),
            overlap_ratio_wh=(0.2, 0.2),
            overlap_filter_strategy=strategy,
            iou_threshold=0.5,
        )
        dets: sv.Detections = s(image)
        print(f"[DEBUG] Strategy {name}: {len(dets)} detections")
else:
    print("[DEBUG] Skipping comparison — no image loaded")

# %% [markdown]
# ## Segmentation with InferenceSlicer
#
# InferenceSlicer also supports instance segmentation models.
# The callback returns `sv.Detections` with masks, which are
# automatically stitched back to the original image dimensions.

# %% Segmentation Slicing Example
from ultralytics import YOLO

seg_model = YOLO("yolo26n-seg.pt")
print(f"[DEBUG] Segmentation model loaded: {seg_model.task}")


def segmentation_callback(image_slice: np.ndarray) -> sv.Detections:
    """Callback for segmentation-based slicing."""
    results = seg_model(image_slice, verbose=False)[0]
    return sv.Detections.from_ultralytics(results)


seg_slicer = sv.InferenceSlicer(
    callback=segmentation_callback,
    slice_wh=(320, 320),
    overlap_ratio_wh=(0.2, 0.2),
    overlap_filter_strategy=sv.OverlapFilter.NON_MAX_SUPPRESSION,
    iou_threshold=0.5,
)

if image is not None:
    seg_detections: sv.Detections = seg_slicer(image)
    print(f"[DEBUG] Segmentation detections with slicing: {len(seg_detections)}")
    has_masks: bool = seg_detections.mask is not None
    print(f"[DEBUG] Masks present: {has_masks}")
else:
    print("[DEBUG] Skipping segmentation slicing — no image loaded")

# %% [markdown]
# ---
# # Part 2: Pre-Processing Optimizations
#
# These strategies are applied **before** or **during** training to improve
# small-object detection from the ground up.
#
# ## 1. Increase Capture or Model Input Resolution
#
# Higher resolution preserves small-object detail:
# - **Capture**: use higher-resolution cameras or sensor settings
# - **Model input**: increase `imgsz` from 640 to 1280 or 1920
#
# Trade-off: larger images require more VRAM and slower inference.
#
# ```python
# # Training with higher resolution
# model.train(data="dataset.yaml", imgsz=1280, epochs=100)
#
# # Prediction with higher resolution
# model.predict(source="image.jpg", imgsz=1280)
# ```
#
# ## 2. Tiling Images During Preprocessing
#
# Instead of tiling at inference time, you can tile your dataset
# during preprocessing:
# 1. Cut each training image into overlapping tiles
# 2. Adjust annotation coordinates to match each tile
# 3. Train the model on these tiles
#
# Tools like **SAHI** and **Roboflow** support automatic tiling
# during dataset preparation.
#
# ## 3. Data Augmentation Strategies
#
# Augmentations that specifically help small objects:
# - **Random crop**: forces the model to learn from zoomed-in portions
# - **Mosaic**: combines 4 images into one, creating varied scales
# - **Copy-paste**: copies small objects and pastes them elsewhere in the scene
# - **MixUp**: blends two images to create harder training examples
#
# Ultralytics supports these via training parameters:
# ```python
# model.train(
#     data="dataset.yaml",
#     imgsz=640,
#     mosaic=1.0,     # mosaic augmentation probability
#     copy_paste=0.5, # copy-paste augmentation probability
#     mixup=0.1,      # mixup augmentation probability
# )
# ```
#
# ## 4. Auto-Learning Model Anchors
#
# Default anchor sizes are tuned for COCO, where small objects start at 32x32.
# If your objects are smaller, auto-learn anchors from your dataset:
# - Older YOLO versions (v5, v7): use `--auto-anchor` or `autoanchor: True`
# - YOLO26 / YOLOv8+: anchor-free architecture — no anchor tuning needed;
#   instead, focus on increasing `imgsz` and using tiling
#
# ## 5. Filtering Extraneous Classes
#
# If your model is trained on many classes but you only care about small ones:
# - **Filter during inference**: set `classes=[0, 2, 5]` to only detect specific classes
# - **Filter during training**: create a dataset with only the relevant classes
#
# ```python
# # Predict only specific classes
# model.predict(source="image.jpg", classes=[0, 2, 5])
# ```

# %% Practical Example — High-Resolution + Slicing Combined
from ultralytics import YOLO as YOLO_Fresh

det_model = YOLO_Fresh("yolo26n.pt")
print("[DEBUG] === Small Object Detection Pipeline ===")

HIGH_RES: int = 1280
SLICE_DIM: int = 640
OVERLAP: float = 0.2

print(f"[DEBUG] Strategy: imgsz={HIGH_RES}, slice={SLICE_DIM}x{SLICE_DIM}, overlap={OVERLAP}")


def high_res_callback(image_slice: np.ndarray) -> sv.Detections:
    """Run detection at high resolution on each slice."""
    results = det_model(image_slice, imgsz=HIGH_RES, verbose=False)[0]
    return sv.Detections.from_ultralytics(results)


combined_slicer = sv.InferenceSlicer(
    callback=high_res_callback,
    slice_wh=(SLICE_DIM, SLICE_DIM),
    overlap_ratio_wh=(OVERLAP, OVERLAP),
    overlap_filter_strategy=sv.OverlapFilter.NON_MAX_SUPPRESSION,
    iou_threshold=0.5,
)

if image is not None:
    combined_dets: sv.Detections = combined_slicer(image)
    print(f"[DEBUG] Combined pipeline detections: {len(combined_dets)}")
else:
    print("[DEBUG] No image loaded — update SOURCE_IMAGE_PATH at the top")

# %% [markdown]
# ## Summary of Strategies
#
# | Strategy | Type | Impact | Cost |
# |----------|------|--------|------|
# | Tiling at inference (SAHI/InferenceSlicer) | Inference | High | Medium (slower inference) |
# | Higher input resolution (`imgsz=1280`) | Both | High | High (more VRAM) |
# | Tiling at preprocessing | Training | High | Medium (larger dataset) |
# | Copy-paste augmentation | Training | Medium | Low |
# | Mosaic augmentation | Training | Medium | Low |
# | Filter to relevant classes | Inference | Low | None |
# | Auto-learn anchors (older YOLO) | Training | Medium | Low |
#
# **Recommended combo for small objects with YOLO26:**
# 1. Train at `imgsz=1280` with mosaic + copy-paste augmentation
# 2. At inference, use `InferenceSlicer` or SAHI with 640x640 tiles
# 3. Use NMS overlap filtering with IoU threshold tuned to your scene density
