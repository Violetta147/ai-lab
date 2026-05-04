# YOLO Configuration & Settings

> **Source**: [Ultralytics Configuration](https://docs.ultralytics.com/usage/cfg/)

---

## CLI Syntax

```bash
yolo TASK MODE ARGS
```

| Component | Options | Required |
|---|---|---|
| **TASK** | `detect`, `segment`, `classify`, `pose`, `obb` | Optional |
| **MODE** | `train`, `val`, `predict`, `export`, `track`, `benchmark` | Required |
| **ARGS** | `key=value` pairs | Optional |

### Example

```bash
yolo detect train data=data.yaml model=yolo26n.pt epochs=100 imgsz=640
```

### Python Equivalent

```python
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
model.train(data="data.yaml", epochs=100, imgsz=640)
```

---

## Train Settings

### Core Training Parameters

| Argument | Type | Default | Description |
|---|---|---|---|
| `model` | `str` | `None` | Model file (`.pt` or `.yaml`) to load |
| `data` | `str` | `None` | Path to dataset YAML file (e.g., `coco8.yaml`) |
| `epochs` | `int` | `100` | Total training epochs |
| `time` | `float` | `None` | Max training time in hours (overrides `epochs`) |
| `patience` | `int` | `100` | Epochs to wait for no improvement before early stopping |
| `batch` | `int/float` | `16` | Batch size (`-1` for auto, `0.70` for 70% GPU memory) |
| `imgsz` | `int` | `640` | Target image size for training |
| `save` | `bool` | `True` | Save train checkpoints and predict results |
| `save_period` | `int` | `-1` | Save checkpoint every N epochs (-1 = disabled) |
| `cache` | `bool` | `False` | Cache images (`True`/`ram`/`disk`) |
| `device` | `int/str/list` | `None` | Device (`0`, `[0,1]`, `cpu`, `mps`, `-1` for idle GPU) |
| `workers` | `int` | `8` | Data loading workers (per `RANK` in DDP) |
| `project` | `str` | `None` | Project name directory |
| `name` | `str` | `None` | Experiment name |
| `exist_ok` | `bool` | `False` | Overwrite existing experiment |
| `pretrained` | `bool/str` | `True` | Use pretrained model |
| `resume` | `bool` | `False` | Resume training from last checkpoint |
| `amp` | `bool` | `True` | Enable Automatic Mixed Precision training |

### Optimizer Settings

| Argument | Type | Default | Description |
|---|---|---|---|
| `optimizer` | `str` | `'auto'` | Optimizer choice: `SGD`, `MuSGD`, `Adam`, `AdamW`, `NAdam`, `RAdam`, `RMSProp`, `auto` |
| `lr0` | `float` | `0.01` | Initial learning rate (SGD=1E-2, Adam=1E-3) |
| `lrf` | `float` | `0.01` | Final learning rate = `lr0 * lrf` |
| `momentum` | `float` | `0.937` | Momentum for SGD or beta1 for Adam |
| `weight_decay` | `float` | `0.0005` | L2 regularization term |
| `warmup_epochs` | `float` | `3.0` | Warmup epochs (fractional allowed) |
| `warmup_momentum` | `float` | `0.8` | Warmup initial momentum |
| `warmup_bias_lr` | `float` | `0.1` | Warmup initial bias learning rate |

### Learning Rate & Schedule

| Argument | Type | Default | Description |
|---|---|---|---|
| `cos_lr` | `bool` | `False` | Use cosine learning rate scheduler |
| `close_mosaic` | `int` | `10` | Disable mosaic augmentation for final N epochs |

### Other Training Settings

| Argument | Type | Default | Description |
|---|---|---|---|
| `seed` | `int` | `0` | Random seed for reproducibility |
| `deterministic` | `bool` | `True` | Enable deterministic mode |
| `single_cls` | `bool` | `False` | Treat all classes as single class |
| `rect` | `bool` | `False` | Rectangular training (vs square padding) |
| `multi_scale` | `float` | `0.0` | Multi-scale training factor (e.g., 0.25 = 0.75x to 1.25x) |
| `fraction` | `float` | `1.0` | Fraction of dataset to use |
| `freeze` | `int/list` | `None` | Freeze first N layers for transfer learning |

---

## MuSGD Optimizer (New in YOLO26)

MuSGD is a **hybrid optimizer** combining SGD + Muon-style orthogonalized updates:

- Recommended for **longer training runs** and **larger datasets**
- Only parameters with `param.ndim >= 2` (e.g., conv weights) get the Muon-style update
- Lower-dimensional parameters (batch norm, bias) use standard SGD
- When `optimizer=auto`: MuSGD is auto-selected for long runs (iterations > 10000), otherwise AdamW

### Usage

```bash
yolo train model=yolo26n.pt data=data.yaml optimizer=MuSGD
```

```python
model.train(data="data.yaml", optimizer="MuSGD")
```

---

## Validation Settings

| Argument | Type | Default | Description |
|---|---|---|---|
| `data` | `str` | `None` | Dataset config file |
| `imgsz` | `int` | `640` | Input image size |
| `batch` | `int` | `16` | Batch size |
| `conf` | `float` | `0.001` | Minimum confidence threshold |
| `iou` | `float` | `0.7` | IoU threshold for NMS |
| `max_det` | `int` | `300` | Max detections per image |
| `half` | `bool` | `False` | Use FP16 half-precision |
| `device` | `str` | `None` | Compute device |
| `save_json` | `bool` | `False` | Save results as JSON |
| `save_txt` | `bool` | `False` | Save results as text files |
| `plots` | `bool` | `True` | Generate validation plots |
| `rect` | `bool` | `True` | Rectangular validation |
| `split` | `str` | `'val'` | Dataset split to use (`val`, `test`, `train`) |
| `end2end` | `bool` | `None` | Use end-to-end head (default) or one-to-many |

---

## Predict Settings

| Argument | Type | Default | Description |
|---|---|---|---|
| `source` | `str` | `None` | Image/video source |
| `conf` | `float` | `0.25` | Minimum confidence threshold |
| `iou` | `float` | `0.7` | IoU threshold for NMS |
| `imgsz` | `int/tuple` | `640` | Input image size |
| `half` | `bool` | `False` | Use FP16 |
| `device` | `str` | `None` | Compute device |
| `max_det` | `int` | `300` | Max detections per image |
| `save` | `bool` | `False` | Save prediction images |
| `show` | `bool` | `False` | Display predictions |
| `classes` | `list[int]` | `None` | Filter by class |

---

## Augmentation Settings

| Argument | Type | Default | Description |
|---|---|---|---|
| `hsv_h` | `float` | `0.015` | HSV-Hue augmentation range |
| `hsv_s` | `float` | `0.7` | HSV-Saturation augmentation range |
| `hsv_v` | `float` | `0.4` | HSV-Value augmentation range |
| `degrees` | `float` | `0.0` | Rotation degree range |
| `translate` | `float` | `0.1` | Translation range |
| `scale` | `float` | `0.5` | Scale range |
| `shear` | `float` | `0.0` | Shear range |
| `perspective` | `float` | `0.0` | Perspective augmentation |
| `flipud` | `float` | `0.0` | Flip up-down probability |
| `fliplr` | `float` | `0.5` | Flip left-right probability |
| `bgr` | `float` | `0.0` | BGR channel probability |
| `mosaic` | `float` | `1.0` | Mosaic augmentation probability |
| `mixup` | `float` | `0.0` | Mixup augmentation probability |
| `copy_paste` | `float` | `0.0` | Copy-paste augmentation probability |
| `copy_paste_mode` | `str` | `'flip'` | Copy-paste mode |
| `auto_augment` | `str` | `'randaugment'` | Auto augmentation policy |
| `erasing` | `float` | `0.4` | Random erasing probability |
| `crop_fraction` | `float` | `1.0` | Crop fraction for classification |

---

## Recommended Settings for Your Project

For fine-tuning YOLO26n on your 4-class vehicle dataset:

```bash
yolo detect train \
  model=yolo26n.pt \
  data=data.yaml \
  epochs=100 \
  imgsz=640 \
  batch=16 \
  patience=50 \
  optimizer=auto \
  lr0=0.01 \
  device=0 \
  workers=8 \
  amp=True \
  save=True \
  plots=True
```

```python
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
results = model.train(
    data="data.yaml",
    epochs=100,
    imgsz=640,
    batch=16,
    patience=50,
    optimizer="auto",
    lr0=0.01,
    device=0,
    workers=8,
    amp=True,
    save=True,
    plots=True,
)
```
