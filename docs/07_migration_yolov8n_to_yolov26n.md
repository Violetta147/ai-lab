# Migration Guide: YOLOv8n → YOLOv26n

> **How to switch your custom dataset project from YOLOv8n to YOLOv26n**

---

## Good News: It's Very Simple! 🎉

Your dataset is **already compatible** with YOLO26 — no format changes needed. The Ultralytics framework uses the **same dataset format** across all YOLO versions. The migration is essentially just changing the model name.

---

## What Changes (and What Doesn't)

| Component | Changes Required? | Details |
|---|---|---|
| **Dataset format** | ❌ No change | Same YOLO `.txt` label format |
| **data.yaml** | ❌ No change | Same YAML structure |
| **Directory structure** | ❌ No change | Same `images/` + `labels/` layout |
| **Label annotations** | ❌ No change | Same `class_id x_center y_center w h` |
| **Model file** | ✅ Change | `yolov8n.pt` → `yolo26n.pt` |
| **Ultralytics package** | ✅ Update | Must use latest version |
| **Training code** | ✅ Minor change | Just swap the model name |

---

## Step-by-Step Migration

### Step 1: Update Ultralytics Package

```bash
pip install ultralytics --upgrade
```

Verify the version supports YOLO26:

```bash
pip show ultralytics
```

> You need version **8.4.0+** (YOLO26 was released January 14, 2026).

---

### Step 2: Verify Your Dataset (No Changes Needed)

Your current dataset structure is already correct:

```
Final.yolov8/
├── data.yaml           ← No changes needed
├── train/
│   ├── images/         ← Same images
│   └── labels/         ← Same .txt label files
├── valid/
│   ├── images/
│   └── labels/
└── test/
    ├── images/
    └── labels/
```

Your `data.yaml` works as-is:

```yaml
train: ../train/images
val: ../valid/images
test: ../test/images

nc: 4
names: ['bus', 'car', 'motor', 'truck']
```

Your label format is identical between YOLOv8 and YOLO26:

```
# class_id  x_center  y_center  width  height  (all normalized 0-1)
1 0.5 0.5 0.3 0.2
```

✅ **No dataset changes required!**

---

### Step 3: Change the Model Name in Your Code

This is the **only code change** you need to make.

#### Before (YOLOv8n)

```python
from ultralytics import YOLO

model = YOLO("yolov8n.pt")
results = model.train(data="data.yaml", epochs=100, imgsz=640)
```

```bash
yolo detect train model=yolov8n.pt data=data.yaml epochs=100 imgsz=640
```

#### After (YOLOv26n)

```python
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
results = model.train(data="data.yaml", epochs=100, imgsz=640)
```

```bash
yolo detect train model=yolo26n.pt data=data.yaml epochs=100 imgsz=640
```

> The pretrained weights will download automatically the first time.

---

### Step 4: Adjust for New YOLO26 Features (Optional)

YOLO26 introduces new features you can optionally use:

#### A. MuSGD Optimizer (New!)

```python
# Auto-selects MuSGD for long training runs
model.train(data="data.yaml", epochs=100, optimizer="auto")

# Force MuSGD
model.train(data="data.yaml", epochs=100, optimizer="MuSGD")
```

#### B. End-to-End Inference (NMS-Free)

YOLO26 is natively end-to-end — **no NMS needed by default**:

```python
# Default: end-to-end (no NMS)
results = model.predict("image.jpg")

# Optional: use one-to-many head with NMS (slightly higher accuracy)
results = model.predict("image.jpg", end2end=False)
```

#### C. Dual-Head Validation

```python
# End-to-end validation (default)
metrics = model.val(data="data.yaml")

# One-to-many validation
metrics = model.val(data="data.yaml", end2end=False)
```

---

## Model Name Mapping

| YOLOv8 Model | YOLO26 Equivalent | Task |
|---|---|---|
| `yolov8n.pt` | `yolo26n.pt` | Detection |
| `yolov8s.pt` | `yolo26s.pt` | Detection |
| `yolov8m.pt` | `yolo26m.pt` | Detection |
| `yolov8l.pt` | `yolo26l.pt` | Detection |
| `yolov8x.pt` | `yolo26x.pt` | Detection |
| `yolov8n-seg.pt` | `yolo26n-seg.pt` | Segmentation |
| `yolov8n-pose.pt` | `yolo26n-pose.pt` | Pose |
| `yolov8n-obb.pt` | `yolo26n-obb.pt` | OBB |
| `yolov8n-cls.pt` | `yolo26n-cls.pt` | Classification |

---

## Architecture Differences

| Feature | YOLOv8n | YOLOv26n |
|---|---|---|
| **NMS** | Required (post-processing) | Not needed (end-to-end) |
| **DFL Module** | Present | Removed |
| **Optimizer** | SGD / Adam | MuSGD (hybrid SGD+Muon) |
| **CPU Inference** | Baseline | Up to 43% faster |
| **Small Object Detection** | Standard | Improved (ProgLoss+STAL) |
| **Loss Function** | Standard | ProgLoss + STAL |
| **Edge Deployment** | Good | Excellent |
| **Dataset Format** | YOLO format | Same YOLO format ✅ |
| **Label Format** | `.txt` per image | Same `.txt` per image ✅ |

---

## Complete Migration Example

### Full Training Script for YOLO26n

```python
from ultralytics import YOLO

if __name__ == "__main__":
    # ===== BEFORE (YOLOv8n) =====
    # model = YOLO("yolov8n.pt")
    
    # ===== AFTER (YOLO26n) =====
    model = YOLO("yolo26n.pt")
    
    # Train (same arguments work!)
    results = model.train(
        data="data.yaml",
        epochs=100,
        imgsz=640,
        batch=16,
        patience=50,
        device=0,
        workers=8,
        amp=True,
        plots=True,
    )
    
    # Validate
    metrics = model.val()
    print(f"mAP50-95: {metrics.box.map:.4f}")
    
    # Predict
    results = model.predict("test/images/", save=True)
    
    # Export
    model.export(format="onnx")
```

### Full CLI Workflow

```bash
# 1. Install/Update ultralytics
pip install ultralytics --upgrade

# 2. Train with YOLO26n (just change the model name!)
yolo detect train model=yolo26n.pt data=data.yaml epochs=100 imgsz=640 batch=16 device=0

# 3. Validate
yolo detect val model=runs/detect/train/weights/best.pt

# 4. Predict
yolo detect predict model=runs/detect/train/weights/best.pt source=test/images/

# 5. Export
yolo export model=runs/detect/train/weights/best.pt format=onnx
```

---

## Troubleshooting

### "Model not found" Error
```bash
# Make sure ultralytics is updated
pip install ultralytics --upgrade

# The model will auto-download on first use
python -c "from ultralytics import YOLO; YOLO('yolo26n.pt')"
```

### Windows RuntimeError
```python
# Always wrap in main guard on Windows
if __name__ == "__main__":
    model = YOLO("yolo26n.pt")
    model.train(data="data.yaml", epochs=100)
```

### GPU Memory Issues
```python
# Reduce batch size
model.train(data="data.yaml", batch=8)

# Or use auto batch sizing
model.train(data="data.yaml", batch=-1)

# Or use 70% GPU memory
model.train(data="data.yaml", batch=0.70)
```

---

## Summary

| Step | Action | Difficulty |
|---|---|---|
| 1 | `pip install ultralytics --upgrade` | 🟢 Easy |
| 2 | Dataset — no changes needed | 🟢 Nothing to do |
| 3 | Change `yolov8n.pt` → `yolo26n.pt` | 🟢 One-line change |
| 4 | (Optional) Use new YOLO26 features | 🟡 Optional |

**That's it!** The migration is essentially a one-line model name change. 🚀
