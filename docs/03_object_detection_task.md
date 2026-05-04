# Object Detection Task with YOLO26

> **Source**: [Ultralytics Object Detection](https://docs.ultralytics.com/tasks/detect/)

---

## What is Object Detection?

Object detection identifies the **location** and **class** of objects in an image or video. The output is a set of **bounding boxes** enclosing objects, along with:
- **Class labels** — what the object is
- **Confidence scores** — how sure the model is

> YOLO26 Detect models are the default YOLO26 models (e.g., `yolo26n.pt`) and are pretrained on the COCO dataset (80 classes).

---

## Available Detection Models

| Model | Size | mAP (val) | Speed (CPU) | Speed (GPU) | Params | FLOPs |
|---|---|---|---|---|---|---|
| **YOLO26n** | Nano | Baseline | Fastest | Fastest | Smallest | Lowest |
| **YOLO26s** | Small | ↑ | Fast | Fast | Small | Low |
| **YOLO26m** | Medium | ↑↑ | Medium | Medium | Medium | Medium |
| **YOLO26l** | Large | ↑↑↑ | Slow | Fast | Large | High |
| **YOLO26x** | X-Large | Highest | Slowest | Fast | Largest | Highest |

> For your project with 4 classes (bus, car, motor, truck), **`yolo26n`** is a great choice — fast and lightweight.

---

## Train

### Python

```python
from ultralytics import YOLO

# Option 1: Load pretrained model (RECOMMENDED for fine-tuning)
model = YOLO("yolo26n.pt")

# Option 2: Build new model from YAML
model = YOLO("yolo26n.yaml")

# Option 3: Build from YAML and transfer pretrained weights
model = YOLO("yolo26n.yaml").load("yolo26n.pt")

# Train the model
results = model.train(data="coco8.yaml", epochs=100, imgsz=640)
```

### CLI

```bash
# Fine-tune from pretrained model (recommended)
yolo detect train data=coco8.yaml model=yolo26n.pt epochs=100 imgsz=640

# Train from scratch using YAML architecture
yolo detect train data=coco8.yaml model=yolo26n.yaml epochs=100 imgsz=640

# Build from YAML with pretrained weights
yolo detect train data=coco8.yaml model=yolo26n.yaml pretrained=yolo26n.pt epochs=100 imgsz=640
```

---

## Dataset Format

YOLO detection datasets require a specific format.

### Directory Structure

```
dataset/
├── train/
│   ├── images/
│   │   ├── image001.jpg
│   │   ├── image002.jpg
│   │   └── ...
│   └── labels/
│       ├── image001.txt
│       ├── image002.txt
│       └── ...
├── valid/
│   ├── images/
│   └── labels/
├── test/
│   ├── images/
│   └── labels/
└── data.yaml
```

### Label Format (per `.txt` file)

Each line in a label file represents one object:

```
<class_id> <x_center> <y_center> <width> <height>
```

- All values are **normalized** (0.0 to 1.0) relative to image dimensions
- `class_id` is 0-indexed

**Example** (for a car at the center of the image):
```
1 0.5 0.5 0.3 0.2
```

### data.yaml Format

```yaml
train: ../train/images
val: ../valid/images
test: ../test/images

nc: 4
names: ['bus', 'car', 'motor', 'truck']
```

> ✅ Your dataset already follows this format!

---

## Validate

### Python

```python
from ultralytics import YOLO

# Load official or custom model
model = YOLO("yolo26n.pt")           # official model
model = YOLO("path/to/best.pt")      # custom trained model

# Validate
metrics = model.val()
print(metrics.box.map)      # mAP50-95
print(metrics.box.map50)    # mAP50
print(metrics.box.map75)    # mAP75
print(metrics.box.maps)     # mAP50-95 per category
```

### CLI

```bash
yolo detect val model=yolo26n.pt                  # official model
yolo detect val model=path/to/best.pt             # custom model
```

---

## Predict

### Python

```python
from ultralytics import YOLO

model = YOLO("path/to/best.pt")
results = model("https://ultralytics.com/images/bus.jpg")

# Access results
for result in results:
    xywh = result.boxes.xywh        # center-x, center-y, width, height
    xyxy = result.boxes.xyxy        # top-left-x, top-left-y, bottom-right-x, bottom-right-y
    names = [result.names[cls.item()] for cls in result.boxes.cls.int()]
    confs = result.boxes.conf       # confidence scores
```

### CLI

```bash
yolo detect predict model=path/to/best.pt source='path/to/images/'
```

---

## Export

### Python

```python
from ultralytics import YOLO

model = YOLO("path/to/best.pt")
model.export(format="onnx")
```

### CLI

```bash
yolo export model=path/to/best.pt format=onnx
```

### Supported Export Formats

| Format | Argument | File Extension |
|---|---|---|
| PyTorch | — | `.pt` |
| TorchScript | `torchscript` | `.torchscript` |
| ONNX | `onnx` | `.onnx` |
| OpenVINO | `openvino` | `_openvino_model/` |
| TensorRT | `engine` | `.engine` |
| CoreML | `coreml` | `.mlpackage` |
| TF Lite | `tflite` | `.tflite` |
| TF SavedModel | `saved_model` | `_saved_model/` |
| PaddlePaddle | `paddle` | `_paddle_model/` |

---

## Your Dataset Summary

Based on your `data.yaml`:

| Property | Value |
|---|---|
| **Classes** | 4 (`bus`, `car`, `motor`, `truck`) |
| **Train path** | `../train/images` |
| **Val path** | `../valid/images` |
| **Test path** | `../test/images` |
| **Label format** | YOLO format (`.txt` per image) |

✅ Your dataset is already in the correct YOLO format for training!
