# YOLO26 Training Guide

> **Source**: [Ultralytics Training Mode](https://docs.ultralytics.com/modes/train/)

---

## Introduction

Training a deep learning model involves feeding it data and adjusting its parameters so that it can make accurate predictions. YOLO26's Train mode is engineered for effective and efficient training, fully utilizing modern hardware capabilities.

---

## Why Choose Ultralytics YOLO for Training?

| Feature | Description |
|---|---|
| **Efficiency** | Single-GPU or multi-GPU scaling |
| **Versatility** | Custom datasets + preloaded ones (COCO, VOC, ImageNet) |
| **User-Friendly** | Simple CLI and Python interfaces |
| **Hyperparameter Flexibility** | Broad range of customizable settings |

---

## Key Features of Train Mode

- ✅ **Automatic Dataset Download** — Standard datasets download on first use
- ✅ **Multi-GPU Support** — Distribute training across multiple GPUs
- ✅ **Hyperparameter Configuration** — YAML config files or CLI arguments
- ✅ **Visualization & Monitoring** — Real-time training metric tracking

---

## Basic Training

### Single-GPU / CPU Training

```python
from ultralytics import YOLO

# Option 1: Build new model from YAML
model = YOLO("yolo26n.yaml")

# Option 2: Load pretrained model (RECOMMENDED for fine-tuning)
model = YOLO("yolo26n.pt")

# Option 3: Build from YAML and transfer pretrained weights
model = YOLO("yolo26n.yaml").load("yolo26n.pt")

# Train
results = model.train(data="coco8.yaml", epochs=100, imgsz=640)
```

```bash
# From pretrained (recommended)
yolo detect train data=coco8.yaml model=yolo26n.pt epochs=100 imgsz=640

# From scratch
yolo detect train data=coco8.yaml model=yolo26n.yaml epochs=100 imgsz=640

# YAML + pretrained weights
yolo detect train data=coco8.yaml model=yolo26n.yaml pretrained=yolo26n.pt epochs=100 imgsz=640
```

> ⚠️ **Windows Users**: Wrap training code in `if __name__ == "__main__":` to avoid `RuntimeError`.

---

## Multi-GPU Training

Distribute training across multiple GPUs for faster results.

### Python

```python
from ultralytics import YOLO

model = YOLO("yolo26n.pt")

# Train with 2 specific GPUs
results = model.train(data="coco8.yaml", epochs=100, imgsz=640, device=[0, 1])

# Train with 2 most idle GPUs (auto-select)
results = model.train(data="coco8.yaml", epochs=100, imgsz=640, device=[-1, -1])
```

### CLI

```bash
# Specific GPUs
yolo detect train data=coco8.yaml model=yolo26n.pt epochs=100 imgsz=640 device=0,1

# Auto-select idle GPUs
yolo detect train data=coco8.yaml model=yolo26n.pt epochs=100 imgsz=640 device=-1,-1
```

---

## Idle GPU Training

Automatically select the **least utilized GPUs** — great for shared computing environments.

```python
# Single most idle GPU
model.train(data="coco8.yaml", epochs=100, imgsz=640, device=-1)

# Two most idle GPUs
model.train(data="coco8.yaml", epochs=100, imgsz=640, device=[-1, -1])
```

The auto-selection algorithm prioritizes:
1. Lower current utilization
2. Higher available memory (free VRAM)
3. Lower temperature and power consumption

---

## Apple Silicon MPS Training

For Mac users with Apple Silicon chips:

```python
model.train(data="coco8.yaml", epochs=100, imgsz=640, device="mps")
```

```bash
yolo detect train data=coco8.yaml model=yolo26n.pt epochs=100 imgsz=640 device=mps
```

---

## Resuming Interrupted Training

If training is interrupted, resume from the last checkpoint:

### Python

```python
from ultralytics import YOLO

# Load partially trained model
model = YOLO("path/to/last.pt")

# Resume training
results = model.train(resume=True)
```

### CLI

```bash
yolo train resume model=path/to/last.pt
```

When resumed, YOLO26 restores:
- ✅ Model weights
- ✅ Optimizer state
- ✅ Learning rate scheduler
- ✅ Epoch number

> 📌 Checkpoints are saved at the end of every epoch. At least 1 epoch must complete for a resume to work.

---

## Training Settings Reference

### Essential Parameters

| Argument | Type | Default | Description |
|---|---|---|---|
| `model` | `str` | `None` | Model file (`.pt` or `.yaml`) |
| `data` | `str` | `None` | Dataset YAML file path |
| `epochs` | `int` | `100` | Number of training epochs |
| `batch` | `int` | `16` | Batch size |
| `imgsz` | `int` | `640` | Input image size |
| `device` | `int/str/list` | `None` | Training device |
| `optimizer` | `str` | `'auto'` | Optimizer (SGD, MuSGD, Adam, AdamW, etc.) |
| `lr0` | `float` | `0.01` | Initial learning rate |
| `lrf` | `float` | `0.01` | Final LR = lr0 × lrf |
| `momentum` | `float` | `0.937` | Momentum |
| `weight_decay` | `float` | `0.0005` | L2 regularization |
| `patience` | `int` | `100` | Early stopping patience |

### Advanced Parameters

| Argument | Type | Default | Description |
|---|---|---|---|
| `warmup_epochs` | `float` | `3.0` | Warmup epochs |
| `close_mosaic` | `int` | `10` | Disable mosaic for last N epochs |
| `amp` | `bool` | `True` | Mixed precision training |
| `cache` | `bool` | `False` | Cache images in RAM/disk |
| `workers` | `int` | `8` | Data loader workers |
| `cos_lr` | `bool` | `False` | Cosine LR scheduler |
| `freeze` | `int/list` | `None` | Freeze layers for transfer learning |
| `multi_scale` | `float` | `0.0` | Multi-scale factor |
| `resume` | `bool` | `False` | Resume from checkpoint |

----

## MuSGD Optimizer

New in YOLO26! A hybrid of SGD + Muon-style orthogonalized updates:

- Best for **longer training runs** and **larger datasets**
- Auto-selected by `optimizer=auto` when iterations > 10,000
- Conv weights get Muon-style updates; batch norm/bias use standard SGD

```bash
yolo train model=yolo26n.pt data=data.yaml optimizer=MuSGD
```

----

## Augmentation Settings

| Argument | Default | Description |
|---|---|---|
| `hsv_h` | `0.015` | Hue augmentation |
| `hsv_s` | `0.7` | Saturation augmentation |
| `hsv_v` | `0.4` | Value augmentation |
| `degrees` | `0.0` | Rotation |
| `translate` | `0.1` | Translation |
| `scale` | `0.5` | Scale |
| `fliplr` | `0.5` | Horizontal flip probability |
| `mosaic` | `1.0` | Mosaic probability |
| `mixup` | `0.0` | Mixup probability |
| `erasing` | `0.4` | Random erasing probability |

----

## Logging Integrations

| Tool | How to Enable |
|---|---|
| **TensorBoard** | `pip install tensorboard` → auto-enabled |
| **Comet** | `pip install comet_ml` → set API key |
| **ClearML** | `pip install clearml` → configure |

### TensorBoard

```bash
tensorboard --logdir runs/detect/train
```

----

## Training for Your Project

### Complete Example

```python
from ultralytics import YOLO

if __name__ == "__main__":
    # Load pretrained YOLO26n
    model = YOLO("yolo26n.pt")
    
    # Train on your vehicle dataset
    results = model.train(
        data="data.yaml",       # your dataset config
        epochs=100,             # training epochs
        imgsz=640,              # image size
        batch=16,               # batch size (adjust based on GPU memory)
        patience=50,            # early stopping
        optimizer="auto",       # auto-select optimizer
        lr0=0.01,               # initial learning rate
        device=0,               # GPU device
        workers=8,              # data loader workers
        amp=True,               # mixed precision
        save=True,              # save checkpoints
        plots=True,             # generate plots
        # Augmentation
        mosaic=1.0,             # mosaic augmentation
        fliplr=0.5,             # horizontal flip
        hsv_h=0.015,            # hue variation
        hsv_s=0.7,              # saturation variation
        hsv_v=0.4,              # value variation
    )
```

### CLI Equivalent

```bash
yolo detect train \
  model=yolo26n.pt \
  data=data.yaml \
  epochs=100 \
  imgsz=640 \
  batch=16 \
  patience=50 \
  device=0 \
  plots=True
```

### Expected Output Structure

After training, results are saved to `runs/detect/train/`:

```
runs/detect/train/
├── weights/
│   ├── best.pt          ← Best model (use this!)
│   └── last.pt          ← Last checkpoint
├── results.csv          ← Training metrics
├── results.png          ← Training curves
├── confusion_matrix.png ← Confusion matrix
├── val_batch0_*.jpg     ← Validation predictions
└── ...
```
