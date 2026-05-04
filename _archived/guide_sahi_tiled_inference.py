# %% [markdown]
# # SAHI Tiled Inference with YOLO26
# Source: https://docs.ultralytics.com/guides/sahi-tiled-inference/
#
# SAHI (Slicing Aided Hyper Inference) optimizes object detection for
# large-scale and high-resolution imagery by partitioning images into
# manageable slices, running detection on each, and stitching results.
#
# ## Key Features
# - **Seamless Integration**: Works with YOLO models with minimal code changes
# - **Resource Efficiency**: Breaks large images into smaller parts to optimize memory
# - **High Accuracy**: Smart algorithms merge overlapping detection boxes during stitching
#
# ## What is Sliced Inference?
# Sliced inference subdivides a large image into smaller segments (slices),
# runs object detection on each slice independently, then recompiles results
# onto the original image. Benefits:
# - Reduced computational burden (smaller slices = faster, less memory)
# - Preserved detection quality (each slice processed independently)
# - Enhanced scalability (works across different image sizes and resolutions)

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

_install(["ultralytics", "sahi"])

# %% Download Model and Test Images
from sahi.utils.file import download_from_url
from sahi.utils.ultralytics import download_yolo26n_model

MODEL_PATH: str = "models/yolo26n.pt"
download_yolo26n_model(MODEL_PATH)
print(f"[DEBUG] Model downloaded to {MODEL_PATH}")

download_from_url(
    "https://raw.githubusercontent.com/obss/sahi/main/demo/demo_data/small-vehicles1.jpeg",
    "demo_data/small-vehicles1.jpeg",
)
download_from_url(
    "https://raw.githubusercontent.com/obss/sahi/main/demo/demo_data/terrain2.png",
    "demo_data/terrain2.png",
)
print("[DEBUG] Test images downloaded to demo_data/")

# %% [markdown]
# ## Standard Inference with YOLO26
# Before using sliced inference, run standard inference for baseline comparison.

# %% Instantiate Detection Model
from sahi import AutoDetectionModel

detection_model = AutoDetectionModel.from_pretrained(
    model_type="ultralytics",
    model_path=MODEL_PATH,
    confidence_threshold=0.3,
    device="cpu",  # change to "cuda:0" for GPU
)
print(f"[DEBUG] Detection model loaded from {MODEL_PATH}")

# %% Standard Prediction
from sahi.predict import get_prediction
from sahi.utils.cv import read_image

result = get_prediction("demo_data/small-vehicles1.jpeg", detection_model)
print(f"[DEBUG] Standard prediction: {len(result.object_prediction_list)} objects detected")

result_with_np = get_prediction(
    read_image("demo_data/small-vehicles1.jpeg"),
    detection_model,
)
print(f"[DEBUG] Prediction from numpy image: {len(result_with_np.object_prediction_list)} objects detected")

# %% Visualize Standard Results
result.export_visuals(export_dir="demo_data/")
print("[DEBUG] Visualization exported to demo_data/prediction_visual.png")

try:
    from IPython.display import Image, display
    display(Image("demo_data/prediction_visual.png"))
except ImportError:
    print("[DEBUG] IPython not available — open demo_data/prediction_visual.png manually")

# %% [markdown]
# ## Sliced Inference with YOLO26
# Specify slice dimensions and overlap ratios.
# Smaller slices and higher overlap improve small-object detection
# at the cost of longer inference time.

# %% Sliced Prediction
from sahi.predict import get_sliced_prediction

SLICE_HEIGHT: int = 256
SLICE_WIDTH: int = 256
OVERLAP_HEIGHT_RATIO: float = 0.2
OVERLAP_WIDTH_RATIO: float = 0.2

sliced_result = get_sliced_prediction(
    "demo_data/small-vehicles1.jpeg",
    detection_model,
    slice_height=SLICE_HEIGHT,
    slice_width=SLICE_WIDTH,
    overlap_height_ratio=OVERLAP_HEIGHT_RATIO,
    overlap_width_ratio=OVERLAP_WIDTH_RATIO,
)
print(f"[DEBUG] Sliced prediction: {len(sliced_result.object_prediction_list)} objects detected")
print(f"[DEBUG] Slice config: {SLICE_HEIGHT}x{SLICE_WIDTH}, overlap={OVERLAP_HEIGHT_RATIO}")

# %% Visualize Sliced Results
sliced_result.export_visuals(export_dir="demo_data/")
print("[DEBUG] Sliced visualization exported to demo_data/prediction_visual.png")

try:
    from IPython.display import Image, display
    display(Image("demo_data/prediction_visual.png"))
except ImportError:
    print("[DEBUG] IPython not available — open demo_data/prediction_visual.png manually")

# %% [markdown]
# ## Handling Prediction Results
# SAHI provides a `PredictionResult` object that can be converted into
# various annotation formats: COCO, imantics, and fiftyone.

# %% Convert Results to Different Formats
object_prediction_list = sliced_result.object_prediction_list
print(f"[DEBUG] Total predictions: {len(object_prediction_list)}")

coco_annotations = sliced_result.to_coco_annotations()[:3]
print(f"[DEBUG] COCO annotations (first 3): {coco_annotations}")

coco_predictions = sliced_result.to_coco_predictions(image_id=1)[:3]
print(f"[DEBUG] COCO predictions (first 3): {coco_predictions}")

# %% [markdown]
# ## Batch Prediction
# Run sliced prediction on an entire directory of images at once.

# %% Batch Prediction on Directory
from sahi.predict import predict

BATCH_SOURCE_DIR: str = "demo_data/"

predict(
    model_type="ultralytics",
    model_path=MODEL_PATH,
    model_device="cpu",  # change to "cuda:0" for GPU
    model_confidence_threshold=0.4,
    source=BATCH_SOURCE_DIR,
    slice_height=SLICE_HEIGHT,
    slice_width=SLICE_WIDTH,
    overlap_height_ratio=OVERLAP_HEIGHT_RATIO,
    overlap_width_ratio=OVERLAP_WIDTH_RATIO,
)
print(f"[DEBUG] Batch prediction complete on directory: {BATCH_SOURCE_DIR}")

# %% [markdown]
# ## Summary
# - Standard inference: fast but may miss small objects in large images
# - Sliced inference (SAHI): partitions image into tiles, detects per-tile, merges results
# - Tune `slice_height`, `slice_width`, and overlap ratios for your use case
# - Results exportable to COCO, imantics, fiftyone formats
# - Batch mode available for processing entire directories
