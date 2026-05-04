# %% [markdown]
# # Steps of a Computer Vision Project
# Source: https://docs.ultralytics.com/guides/steps-of-a-cv-project/
#
# This guide walks through the complete lifecycle of a computer vision project,
# from goal definition through deployment and maintenance.
#
# ## Overview
# 1. Define project goals and select CV task
# 2. Collect and annotate data
# 3. Augment data and split dataset
# 4. Train the model
# 5. Evaluate and fine-tune
# 6. Test on unseen data
# 7. Deploy
# 8. Monitor, maintain, and document

# %% [markdown]
# ## Step 1: Define Project Goals
#
# Your objective determines the CV task:
#
# | Objective | CV Task | Why |
# |-----------|---------|-----|
# | Monitor vehicle flow on highways | Object Detection | Locates multiple objects efficiently |
# | Outline tumors in medical scans | Image Segmentation | Pixel-level boundaries for assessment |
# | Categorize document types | Image Classification | One class per image, no spatial info needed |
#
# ### Choosing Training Approach
# - **From scratch**: need large, diverse dataset; model learns everything
# - **Transfer learning**: start from pretrained weights; adapt with smaller dataset
# - **Model size**: lightweight (yolo26n) for edge; larger (yolo26x) for servers

# %% [markdown]
# ## Step 2: Data Collection and Annotation
#
# ### Data Sources
# - [Google Dataset Search](https://datasetsearch.research.google.com/)
# - [Kaggle Datasets](https://www.kaggle.com/datasets)
# - [Roboflow Universe](https://universe.roboflow.com/)
# - Ultralytics built-in datasets (COCO, VOC, etc.)
#
# ### Annotation Types
# - **Classification**: label entire image as one class
# - **Detection**: draw bounding boxes around each object
# - **Segmentation**: label each pixel by object
#
# ### Annotation Tools
# - [Label Studio](https://labelstud.io/)
# - [CVAT](https://www.cvat.ai/)
# - [Labelme](https://github.com/wkentaro/labelme)
# - [Roboflow Annotate](https://roboflow.com/annotate)

# %% [markdown]
# ## Step 3: Data Augmentation and Splitting
#
# **Split BEFORE augmentation** to keep test/val data unaltered:
# - Training: 70-80%
# - Validation: 10-15% (tune hyperparameters, early stopping)
# - Test: 10-15% (final evaluation on unseen data)
#
# ### Augmentation Techniques
# - Random crop, rotation, flip, scale
# - Mosaic (combine 4 images)
# - MixUp (blend 2 images)
# - Color jitter (HSV adjustments)
#
# Ultralytics has built-in augmentation — configured via training parameters.

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
# ## Step 4: Model Training
#
# Key setup:
# - Install framework (Ultralytics, PyTorch)
# - Configure GPU (CUDA, cuDNN)
# - Select model variant and hyperparameters
# - Use version control for datasets (DVC)

# %% Train a YOLO26 Model (Demo)
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
print(f"[DEBUG] Model loaded: yolo26n.pt")
print(f"[DEBUG] Task: {model.task}")
print(f"[DEBUG] Classes: {len(model.names)} classes")

DATASET_YAML: str = "coco8.yaml"  # UPDATE for your dataset
EPOCHS: int = 5
IMAGE_SIZE: int = 640

print(f"[DEBUG] Training on {DATASET_YAML} for {EPOCHS} epochs...")
train_results = model.train(
    data=DATASET_YAML,
    epochs=EPOCHS,
    imgsz=IMAGE_SIZE,
    batch=16,
    project="runs/cv_project",
    name="step4_train",
)
print("[DEBUG] Training complete")

# %% [markdown]
# ## Step 5: Evaluate and Fine-Tune
#
# ### Key Metrics
# - **Precision**: of all positive predictions, how many are correct?
# - **Recall**: of all actual positives, how many were found?
# - **mAP50**: mean Average Precision at IoU 0.5
# - **mAP50-95**: mean AP across IoU thresholds 0.5 to 0.95
#
# ### Fine-Tuning Strategies
# - Adjust learning rate, batch size, weight decay
# - Try different model variants
# - Hyperparameter search (grid search, Ray Tune)

# %% Evaluate on Validation Set
print("[DEBUG] Running validation...")
val_metrics = model.val(
    data=DATASET_YAML,
    imgsz=IMAGE_SIZE,
    batch=16,
)

print(f"[DEBUG] === Validation Metrics ===")
print(f"  mAP50:     {val_metrics.box.map50:.4f}")
print(f"  mAP50-95:  {val_metrics.box.map:.4f}")
print(f"  Precision:  {val_metrics.box.mp:.4f}")
print(f"  Recall:     {val_metrics.box.mr:.4f}")

# %% [markdown]
# ## Step 6: Model Testing
#
# Test on a **separate, unseen test set** that was never used during
# training or validation. This confirms real-world readiness.
#
# Key checks:
# - Performance consistent with validation metrics
# - No signs of overfitting (train >> test accuracy)
# - No data leakage (suspicious near-perfect metrics)

# %% Test on Unseen Data
print("[DEBUG] Predicting on sample test images...")
test_results = model.predict(
    source="https://ultralytics.com/images/bus.jpg",
    imgsz=IMAGE_SIZE,
    conf=0.25,
    save=True,
    project="runs/cv_project",
    name="step6_test",
)

for r in test_results:
    print(f"[DEBUG] Test image: {len(r.boxes)} detections")
    for box in r.boxes:
        cls_id: int = int(box.cls.item())
        conf_val: float = float(box.conf.item())
        print(f"  {model.names[cls_id]}: {conf_val:.3f}")

# %% [markdown]
# ## Step 7: Model Deployment
#
# 1. **Set up environment** — cloud (AWS/GCP/Azure), edge (Jetson), or local
# 2. **Export model** — ONNX, TensorRT, CoreML, OpenVINO
# 3. **Deploy** — API endpoint, embedded app, or batch pipeline
# 4. **Scale** — load balancers, auto-scaling, monitoring

# %% Export for Deployment
print("[DEBUG] Exporting to ONNX for deployment...")
onnx_path: str = model.export(format="onnx", imgsz=IMAGE_SIZE)
print(f"[DEBUG] ONNX model: {onnx_path}")

# %% [markdown]
# ## Step 8: Monitor, Maintain, and Document
#
# ### Monitoring
# - Track KPIs (accuracy, latency, throughput)
# - Detect model drift — performance decline due to changing input data
# - Set up alerts for anomalies
#
# ### Maintenance
# - Periodically retrain with updated data
# - Version your models (model registry)
# - A/B test new versions before full rollout
#
# ### Documentation
# - Record model architecture, hyperparameters, training procedures
# - Document data preprocessing steps
# - Log all changes during deployment and maintenance
# - Ensure reproducibility for future iterations
