# Ultralytics YOLO26 Modes

> **Source**: [Ultralytics Modes Documentation](https://docs.ultralytics.com/modes/)

---

## Introduction

Ultralytics YOLO26 is a versatile framework that covers the **entire lifecycle** of machine learning models — from data ingestion and model training to validation, deployment, and real-world tracking. Each mode serves a specific purpose.

---

## Modes at a Glance

| Mode | Purpose | When to Use |
|---|---|---|
| **Train** | Fine-tune model on custom or preloaded datasets | When you want to teach the model to recognize your specific objects |
| **Val** | Post-training validation checkpoint | After training, to measure model accuracy and generalization |
| **Predict** | Run inference on real-world data | When deploying or testing your model on new images/videos |
| **Export** | Convert model for deployment | When preparing your model for production (ONNX, TensorRT, etc.) |
| **Track** | Real-time object tracking in video | For surveillance, autonomous vehicles, etc. |
| **Benchmark** | Analyze speed and accuracy across formats | When choosing the best export format for your hardware |

---

## 1. Train Mode

Train mode is used for training a YOLO26 model on a custom dataset. The model is trained using the specified dataset and hyperparameters, optimizing parameters to accurately predict classes and locations of objects.

### Python Example

```python
from ultralytics import YOLO

# Load a pretrained model
model = YOLO("yolo26n.pt")

# Start training on your custom dataset
model.train(data="path/to/dataset.yaml", epochs=100, imgsz=640)
```

### CLI Example

```bash
yolo detect train data=path/to/dataset.yaml model=yolo26n.pt epochs=100 imgsz=640
```

📖 [Full Train Guide](https://docs.ultralytics.com/modes/train/)

---

## 2. Val Mode

Val mode evaluates the trained model on a **validation set** to measure accuracy and generalization. It provides metrics such as **mAP** (mean Average Precision) to quantify performance.

### Metrics Provided

| Metric | Description |
|---|---|
| **mAP50** | Mean Average Precision at IoU threshold 0.50 |
| **mAP75** | Mean Average Precision at IoU threshold 0.75 |
| **mAP50-95** | Mean Average Precision averaged over IoU 0.50 to 0.95 |
| **Precision** | Ratio of true positive detections to total detected positives |
| **Recall** | Ratio of true positive detections to total actual positives |
| **IoU** | Intersection over Union between predicted and ground truth boxes |

### Python Example

```python
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
model.val(data="path/to/validation.yaml")
```

### CLI Example

```bash
yolo val model=yolo26n.pt data=path/to/validation.yaml
```

📖 [Full Validation Guide](https://docs.ultralytics.com/modes/val/)

---

## 3. Predict Mode

Predict mode runs inference using a trained model on new images or videos. The model identifies and localizes objects in the input media.

### Python Example

```python
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
results = model("path/to/image.jpg")
```

### CLI Example

```bash
yolo predict model=yolo26n.pt source=path/to/image.jpg
```

📖 [Full Predict Guide](https://docs.ultralytics.com/modes/predict/)

---

## 4. Export Mode

Export mode converts your trained model into formats suitable for deployment:

| Format | Extension | Use Case |
|---|---|---|
| ONNX | `.onnx` | Cross-platform deployment |
| TensorRT | `.engine` | NVIDIA GPU acceleration |
| CoreML | `.mlpackage` | Apple devices |
| TFLite | `.tflite` | Mobile/edge devices |
| OpenVINO | `_openvino_model/` | Intel hardware |
| TorchScript | `.torchscript` | PyTorch deployment |

### Python Example

```python
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
model.export(format="onnx")
```

### CLI Example

```bash
yolo export model=yolo26n.pt format=onnx
```

📖 [Full Export Guide](https://docs.ultralytics.com/modes/export/)

---

## 5. Track Mode

Track mode extends object detection to **track objects across video frames** or live streams, maintaining object identity over time.

### Python Example

```python
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
model.track(source="path/to/video.mp4")
```

### CLI Example

```bash
yolo track model=yolo26n.pt source=path/to/video.mp4
```

📖 [Full Track Guide](https://docs.ultralytics.com/modes/track/)

---

## 6. Benchmark Mode

Benchmark mode profiles speed and accuracy of various export formats. Provides metrics like model size, mAP50-95, and inference time.

### Python Example

```python
from ultralytics.utils.benchmarks import benchmark

benchmark(model="yolo26n.pt", data="coco8.yaml", imgsz=640, half=False, device=0)
```

### CLI Example

```bash
yolo benchmark model=yolo26n.pt data='coco8.yaml' imgsz=640 half=False device=0
```

📖 [Full Benchmark Guide](https://docs.ultralytics.com/modes/benchmark/)

---

## CLI Syntax

All modes follow this pattern:

```bash
yolo TASK MODE ARGS
```

Where:
- **TASK** (optional): `detect`, `segment`, `classify`, `pose`, `obb`
- **MODE** (required): `train`, `val`, `predict`, `export`, `track`, `benchmark`
- **ARGS** (optional): `key=value` pairs like `imgsz=640`, `epochs=100`

### Examples for Your Project

```bash
# Train detection model
yolo detect train data=data.yaml model=yolo26n.pt epochs=100 imgsz=640

# Validate your trained model
yolo detect val model=runs/detect/train/weights/best.pt

# Predict on an image
yolo detect predict model=runs/detect/train/weights/best.pt source=test/images/

# Export for deployment
yolo export model=runs/detect/train/weights/best.pt format=onnx
```
