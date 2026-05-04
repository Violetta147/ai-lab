# YOLO26 Validation Guide

> **Source**: [Ultralytics Validation Mode](https://docs.ultralytics.com/modes/val/)

---

## Introduction

Validation assesses the **quality of your trained models**. Val mode provides metrics like mAP, Precision, and Recall to evaluate object detection performance.

---

## Key Features

- ✅ **Automated Settings** — Models remember training configs
- ✅ **Multi-Metric Support** — mAP50, mAP75, mAP50-95, Precision, Recall
- ✅ **CLI and Python API** — Both interfaces supported
- ✅ **Data Compatibility** — Works with training data and custom datasets

> 💡 **Tip**: Models remember their training settings automatically:
> ```bash
> yolo val model=yolo26n.pt
> ```

---

## Basic Usage

### Python

```python
from ultralytics import YOLO

# Load model
model = YOLO("yolo26n.pt")           # official model
model = YOLO("path/to/best.pt")      # custom trained model

# Validate (no arguments needed)
metrics = model.val()

# Access metrics
print(f"mAP50-95: {metrics.box.map}")
print(f"mAP50:    {metrics.box.map50}")
print(f"mAP75:    {metrics.box.map75}")
print(f"Per-class mAP: {metrics.box.maps}")
```

### CLI

```bash
yolo detect val model=yolo26n.pt           # official model
yolo detect val model=path/to/best.pt      # custom model
```

> ⚠️ **Windows**: Wrap code in `if __name__ == "__main__":` to avoid `RuntimeError`.

---

## Metrics Explained

| Metric | Description | Ideal |
|---|---|---|
| **mAP50** | Mean AP @ IoU 0.50 | Higher = Better |
| **mAP75** | Mean AP @ IoU 0.75 (stricter) | Higher = Better |
| **mAP50-95** | Mean AP averaged over IoU 0.50:0.95 | Higher = Better |
| **Precision** | TP / (TP + FP) | Fewer false alarms |
| **Recall** | TP / (TP + FN) | Fewer missed objects |

---

## Validation Arguments

| Argument | Type | Default | Description |
|---|---|---|---|
| `data` | `str` | `None` | Dataset YAML file |
| `imgsz` | `int` | `640` | Input image size |
| `batch` | `int` | `16` | Batch size |
| `conf` | `float` | `0.001` | Confidence threshold |
| `iou` | `float` | `0.7` | IoU threshold for NMS |
| `max_det` | `int` | `300` | Max detections per image |
| `half` | `bool` | `False` | FP16 half-precision |
| `device` | `str` | `None` | Compute device |
| `save_json` | `bool` | `False` | Save results as JSON |
| `save_txt` | `bool` | `False` | Save results as text |
| `plots` | `bool` | `True` | Generate validation plots |
| `split` | `str` | `'val'` | Dataset split (`val`, `test`, `train`) |
| `end2end` | `bool` | `None` | End-to-end or one-to-many head |

---

## Custom Validation

### Python

```python
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
metrics = model.val(
    data="coco8.yaml",
    imgsz=640,
    batch=16,
    conf=0.25,
    iou=0.7,
    device="0",
)
```

### CLI

```bash
yolo val model=yolo26n.pt data=coco8.yaml imgsz=640 batch=16 conf=0.25 iou=0.7 device=0
```

---

## Confusion Matrix Export

```python
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
results = model.val(data="coco8.yaml", plots=True)

# Print confusion matrix as DataFrame
print(results.confusion_matrix.to_df())
```

---

## Validate on Different Splits

```bash
yolo detect val model=best.pt split=val    # validation set (default)
yolo detect val model=best.pt split=test   # test set
yolo detect val model=best.pt split=train  # training set (sanity check)
```

---

## For Your Project

### After Training

```python
from ultralytics import YOLO

if __name__ == "__main__":
    model = YOLO("runs/detect/train/weights/best.pt")
    
    # Validate
    metrics = model.val()
    print(f"mAP50-95: {metrics.box.map:.4f}")
    print(f"mAP50:    {metrics.box.map50:.4f}")
    
    # Per-class results
    for i, name in enumerate(['bus', 'car', 'motor', 'truck']):
        print(f"  {name}: mAP50-95 = {metrics.box.maps[i]:.4f}")

    # Test set validation
    test_metrics = model.val(split="test")
    print(f"Test mAP50-95: {test_metrics.box.map:.4f}")
```

### CLI

```bash
yolo detect val model=runs/detect/train/weights/best.pt
yolo detect val model=runs/detect/train/weights/best.pt split=test
```

### Generated Outputs

```
runs/detect/val/
├── confusion_matrix.png
├── confusion_matrix_normalized.png
├── F1_curve.png
├── P_curve.png
├── R_curve.png
├── PR_curve.png
├── val_batch0_labels.jpg
├── val_batch0_pred.jpg
└── ...
```
