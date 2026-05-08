# Ultralytics YOLO — Traffic Smart Dashboard Reference

> Tổng hợp từ 14+ trang tài liệu Ultralytics, phục vụ xây dựng **Traffic Monitoring Dashboard** trên Jetson Nano / Desktop.

---

## Mục lục

1. [Kiến trúc tổng quan](#1-kiến-trúc-tổng-quan)
2. [Multi-Object Tracking](#2-multi-object-tracking)
3. [Object Counting — Line / Region](#3-object-counting)
4. [Speed Estimation](#4-speed-estimation)
5. [Distance Calculation](#5-distance-calculation)
6. [Heatmap Visualization](#6-heatmap-visualization)
7. [Analytics — Charts](#7-analytics--charts)
8. [TrackZone — Zone-based Tracking](#8-trackzone)
9. [VisionEye — Spatial Mapping](#9-visioneye)
10. [Streamlit Live Inference (Dashboard)](#10-streamlit-live-inference)
11. [Custom Trainer — Loss & Metrics](#11-custom-trainer)
12. [DeepStream on Jetson](#12-deepstream-on-jetson)
13. [Thread-Safe Inference](#13-thread-safe-inference)
14. [Performance Metrics](#14-performance-metrics)
15. [API Reference — Lazy Imports](#15-api-reference)
16. [Recommended Stack for Traffic Dashboard](#16-recommended-stack)
17. [Code Template — Full Pipeline](#17-code-template)

---

## 1. Kiến trúc tổng quan

```
Camera / Video File
       │
       ▼
┌─────────────────┐
│  YOLO Detection  │  ← yolo26n.pt / custom best.pt
│  + Tracking      │  ← BoT-SORT / ByteTrack
└────────┬────────┘
         │ results (boxes, track_ids, classes, conf)
         ▼
┌─────────────────────────────────────────┐
│          Solution Modules               │
│  ┌───────────┐  ┌──────────────────┐    │
│  │ Counter   │  │ SpeedEstimator   │    │
│  │ (line/    │  │ (pixel→meter)    │    │
│  │  region)  │  └──────────────────┘    │
│  └───────────┘  ┌──────────────────┐    │
│  ┌───────────┐  │ Heatmap          │    │
│  │ TrackZone │  │ (density viz)    │    │
│  └───────────┘  └──────────────────┘    │
│  ┌───────────┐  ┌──────────────────┐    │
│  │ Analytics │  │ DistanceCalc     │    │
│  │ (charts)  │  │ VisionEye        │    │
│  └───────────┘  └──────────────────┘    │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  Dashboard UI    │  ← Streamlit / FastAPI + React
│  (real-time)     │
└─────────────────┘
```

---

## 2. Multi-Object Tracking

**Source:** https://docs.ultralytics.com/vi/modes/track/

### Trackers hỗ trợ sẵn

| Tracker | File config | Đặc điểm |
|---------|-------------|-----------|
| **BoT-SORT** | `botsort.yaml` | Mặc định, kết hợp motion + appearance (ReID) |
| **ByteTrack** | `bytetrack.yaml` | Nhẹ, chỉ dùng motion, phù hợp edge device |

### Tracking Arguments

| Arg | Type | Default | Mô tả |
|-----|------|---------|-------|
| `tracker` | str | `'botsort.yaml'` | Chọn tracker |
| `conf` | float | `0.1` | Ngưỡng confidence (thấp → track nhiều hơn) |
| `iou` | float | `0.7` | Ngưỡng IoU lọc overlap |
| `classes` | list | `None` | Lọc class index (vd: `[0, 2]` = person + car) |
| `persist` | bool | `False` | Duy trì track IDs giữa các frame |
| `verbose` | bool | `True` | Hiển thị tracking output |

### Code — Tracking cơ bản

```python
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
results = model.track(
    source="traffic_video.mp4",
    tracker="bytetrack.yaml",
    persist=True,
    show=True,
)
```

### Code — Vòng lặp persist tracks

```python
import cv2
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
cap = cv2.VideoCapture("traffic_video.mp4")

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break

    results = model.track(frame, persist=True)
    annotated = results[0].plot()
    cv2.imshow("Tracking", annotated)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
```

### Bật ReID (Re-Identification)

Trong `botsort.yaml`, set `with_reid: true` để cải thiện tracking qua occlusion.

---

## 3. Object Counting

**Source:** https://docs.ultralytics.com/vi/guides/object-counting/ & https://docs.ultralytics.com/vi/guides/region-counting/

### ObjectCounter Arguments

| Arg | Type | Default | Mô tả |
|-----|------|---------|-------|
| `model` | str | `None` | Path to YOLO model |
| `region` | list | `[(20,400),(1260,400)]` | Line/polygon points |
| `show_in` | bool | `True` | Hiển thị IN count |
| `show_out` | bool | `True` | Hiển thị OUT count |

### Code — Line Counting (đếm xe qua vạch)

```python
import cv2
from ultralytics import solutions

cap = cv2.VideoCapture("traffic.mp4")
w, h, fps = (int(cap.get(x)) for x in (
    cv2.CAP_PROP_FRAME_WIDTH,
    cv2.CAP_PROP_FRAME_HEIGHT,
    cv2.CAP_PROP_FPS,
))

line_points = [(20, 400), (1080, 400)]

counter = solutions.ObjectCounter(
    show=True,
    region=line_points,
    model="yolo26n.pt",
    classes=[2, 5, 7],  # car, bus, truck (COCO)
)

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break
    results = counter(frame)

cap.release()
cv2.destroyAllWindows()
```

### Code — Region Counting (đếm theo vùng)

```python
import cv2
from ultralytics import solutions

cap = cv2.VideoCapture("traffic.mp4")
w, h, fps = (int(cap.get(x)) for x in (
    cv2.CAP_PROP_FRAME_WIDTH,
    cv2.CAP_PROP_FRAME_HEIGHT,
    cv2.CAP_PROP_FPS,
))

region_points = {
    "lane-1": [(50, 300), (300, 300), (300, 500), (50, 500)],
    "lane-2": [(350, 300), (600, 300), (600, 500), (350, 500)],
    "lane-3": [(650, 300), (900, 300), (900, 500), (650, 500)],
}

regioncounter = solutions.RegionCounter(
    show=True,
    region=region_points,
    model="yolo26n.pt",
)

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break
    results = regioncounter(frame)

cap.release()
cv2.destroyAllWindows()
```

---

## 4. Speed Estimation

**Source:** https://docs.ultralytics.com/vi/guides/speed-estimation/

### SpeedEstimator Arguments

| Arg | Type | Default | Mô tả |
|-----|------|---------|-------|
| `model` | str | `None` | Path to YOLO model |
| `fps` | float | `30.0` | FPS video (ảnh hưởng tính toán) |
| `max_hist` | int | `5` | Số frame tối thiểu để tính speed |
| `meter_per_pixel` | float | `0.05` | Hệ số pixel → meter (phụ thuộc camera calibration) |
| `max_speed` | int | `120` | Cap tốc độ tối đa (km/h) |

> **Lưu ý:** Tốc độ chỉ là **ước tính** — phụ thuộc camera angle, calibration, FPS.

### Code — Speed Estimation

```python
import cv2
from ultralytics import solutions

cap = cv2.VideoCapture("highway.mp4")
w, h, fps = (int(cap.get(x)) for x in (
    cv2.CAP_PROP_FRAME_WIDTH,
    cv2.CAP_PROP_FRAME_HEIGHT,
    cv2.CAP_PROP_FPS,
))

speedestimator = solutions.SpeedEstimator(
    show=True,
    model="yolo26n.pt",
    fps=fps,
    meter_per_pixel=0.05,
    max_speed=120,
    classes=[2, 5, 7],
)

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break
    results = speedestimator(frame)

cap.release()
cv2.destroyAllWindows()
```

### Calibration `meter_per_pixel`

Giá trị `meter_per_pixel` phụ thuộc vào:
- **Chiều cao camera** so với mặt đường
- **Góc nghiêng** (tilt angle)
- **Focal length** của lens

Phương pháp: Đo khoảng cách thực tế giữa 2 điểm đã biết trên đường (vd: vạch kẻ đường 3m) → đếm pixels giữa chúng → `meter_per_pixel = 3.0 / pixel_distance`.

---

## 5. Distance Calculation

**Source:** https://docs.ultralytics.com/vi/guides/distance-calculation/

Tính khoảng cách Euclidean giữa 2 bounding box centroid (pixel-based).

### Code

```python
import cv2
from ultralytics import solutions

cap = cv2.VideoCapture("traffic.mp4")
w, h, fps = (int(cap.get(x)) for x in (
    cv2.CAP_PROP_FRAME_WIDTH,
    cv2.CAP_PROP_FRAME_HEIGHT,
    cv2.CAP_PROP_FPS,
))

distcalc = solutions.DistanceCalculation(
    model="yolo26n.pt",
    show=True,
)

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break
    results = distcalc(frame)

cap.release()
cv2.destroyAllWindows()
```

### Tương tác
- **Left click** vào 2 bounding box → tính khoảng cách
- **Right click** → xóa các điểm đã vẽ

> Khoảng cách là pixel-based, cần kết hợp `meter_per_pixel` để có giá trị thực.

---

## 6. Heatmap Visualization

**Source:** https://docs.ultralytics.com/vi/guides/heatmaps/

### Heatmap Arguments

| Arg | Type | Default | Mô tả |
|-----|------|---------|-------|
| `model` | str | `None` | Path to YOLO model |
| `colormap` | int | `cv2.COLORMAP_DEEPGREEN` | OpenCV colormap |
| `region` | list | `[(20,400),(1260,400)]` | Vùng đếm kèm heatmap |

### Colormaps phổ biến cho traffic

| Colormap | Mô tả |
|----------|-------|
| `cv2.COLORMAP_JET` | Rainbow — phổ biến nhất |
| `cv2.COLORMAP_HOT` | Đỏ-vàng — trực quan cho mật độ |
| `cv2.COLORMAP_INFERNO` | Tối-sáng — dễ nhìn ban đêm |
| `cv2.COLORMAP_PARULA` | Xanh-vàng — hiện đại |
| `cv2.COLORMAP_TURBO` | Improved rainbow |

### Code — Traffic Heatmap

```python
import cv2
from ultralytics import solutions

cap = cv2.VideoCapture("intersection.mp4")
w, h, fps = (int(cap.get(x)) for x in (
    cv2.CAP_PROP_FRAME_WIDTH,
    cv2.CAP_PROP_FRAME_HEIGHT,
    cv2.CAP_PROP_FPS,
))
out = cv2.VideoWriter("heatmap_output.avi",
    cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

heatmap = solutions.Heatmap(
    show=True,
    model="yolo26n.pt",
    colormap=cv2.COLORMAP_JET,
    classes=[2, 5, 7],  # car, bus, truck
)

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break
    results = heatmap(frame)
    out.write(results.plot_im)

cap.release()
out.release()
cv2.destroyAllWindows()
```

---

## 7. Analytics — Charts

**Source:** https://docs.ultralytics.com/vi/guides/analytics/

Tạo biểu đồ real-time từ detection results.

### Analytics Arguments

| Arg | Type | Default | Mô tả |
|-----|------|---------|-------|
| `model` | str | `None` | Path to YOLO model |
| `analytics_type` | str | `'line'` | `line` / `bar` / `area` / `pie` |

### Code — Line Chart (vehicle count over time)

```python
import cv2
from ultralytics import solutions

cap = cv2.VideoCapture("traffic.mp4")
w, h, fps = (int(cap.get(x)) for x in (
    cv2.CAP_PROP_FRAME_WIDTH,
    cv2.CAP_PROP_FRAME_HEIGHT,
    cv2.CAP_PROP_FPS,
))
out = cv2.VideoWriter("analytics.avi",
    cv2.VideoWriter_fourcc(*"MJPG"), fps, (1280, 720))

analytics = solutions.Analytics(
    show=True,
    analytics_type="line",
    model="yolo26n.pt",
    classes=[0, 2, 5, 7],  # person, car, bus, truck
)

frame_count = 0
while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break
    frame_count += 1
    results = analytics(frame, frame_count)
    out.write(results.plot_im)

cap.release()
out.release()
cv2.destroyAllWindows()
```

### Analytics types cho Traffic Dashboard

| Type | Ứng dụng |
|------|----------|
| `line` | Số xe theo thời gian, trend analysis |
| `bar` | So sánh class counts (car vs bus vs truck) |
| `pie` | Phân bố loại phương tiện |
| `area` | Cumulative vehicle flow |

---

## 8. TrackZone

**Source:** https://docs.ultralytics.com/vi/guides/trackzone/

Tracking chỉ trong **vùng xác định** — giảm tải tính toán, focus vào khu vực quan tâm.

### Code — Track vehicles in intersection zone only

```python
import cv2
from ultralytics import solutions

cap = cv2.VideoCapture("intersection.mp4")
w, h, fps = (int(cap.get(x)) for x in (
    cv2.CAP_PROP_FRAME_WIDTH,
    cv2.CAP_PROP_FRAME_HEIGHT,
    cv2.CAP_PROP_FPS,
))

intersection_zone = [(150, 150), (1130, 150), (1130, 570), (150, 570)]

trackzone = solutions.TrackZone(
    show=True,
    region=intersection_zone,
    model="yolo26n.pt",
    classes=[2, 5, 7],
)

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break
    results = trackzone(frame)

cap.release()
cv2.destroyAllWindows()
```

---

## 9. VisionEye

**Source:** https://docs.ultralytics.com/vi/guides/vision-eye/

Mô phỏng "tầm nhìn" từ 1 điểm cố định — vẽ đường từ điểm quan sát đến mọi đối tượng.

### VisionEye Arguments

| Arg | Type | Default | Mô tả |
|-----|------|---------|-------|
| `model` | str | `None` | Path to YOLO model |
| `vision_point` | tuple | `(20, 20)` | Điểm quan sát (pixel) |

### Code

```python
import cv2
from ultralytics import solutions

cap = cv2.VideoCapture("traffic.mp4")
w, h, fps = (int(cap.get(x)) for x in (
    cv2.CAP_PROP_FRAME_WIDTH,
    cv2.CAP_PROP_FRAME_HEIGHT,
    cv2.CAP_PROP_FPS,
))

visioneye = solutions.VisionEye(
    show=True,
    model="yolo26n.pt",
    classes=[2, 5, 7],
    vision_point=(w // 2, h),  # bottom center = camera position
)

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break
    results = visioneye(frame)

cap.release()
cv2.destroyAllWindows()
```

---

## 10. Streamlit Live Inference

**Source:** https://docs.ultralytics.com/vi/guides/streamlit-live-inference/

### Quick Start

```bash
pip install ultralytics streamlit
yolo solutions inference
```

### Code — Custom Streamlit Dashboard

```python
from ultralytics import solutions

inf = solutions.Inference(
    model="yolo26n.pt",
)
inf.inference()
# Run: streamlit run app.py
```

### CLI Options

```bash
yolo solutions inference model="path/to/best.pt"
yolo solutions inference source="path/to/video.mp4"
```

### Tích hợp với Traffic Dashboard

Streamlit phù hợp cho **prototype nhanh**. Cho production, dùng:
- **FastAPI** backend + **React/Vue** frontend
- **Grafana + InfluxDB** cho time-series metrics
- **WebSocket** cho real-time updates

---

## 11. Custom Trainer

**Source:** https://docs.ultralytics.com/vi/guides/custom-trainer/

### Override Methods

| Method | Mục đích |
|--------|----------|
| `validate()` | Custom metrics (F1, recall) |
| `build_optimizer()` | Per-layer learning rates |
| `get_model()` | Custom loss (weighted classes) |
| `save_model()` | Save best by custom metric |

### Code — Log F1 Score

```python
import numpy as np
from ultralytics import YOLO
from ultralytics.models.yolo.detect import DetectionTrainer
from ultralytics.utils import LOGGER

class MetricsTrainer(DetectionTrainer):
    def validate(self):
        metrics, fitness = super().validate()
        if metrics is None:
            return metrics, fitness
        if hasattr(self.validator, "metrics") and hasattr(self.validator.metrics, "box"):
            box = self.validator.metrics.box
            valid_f1 = box.f1[box.f1 > 0]
            mean_f1 = np.mean(valid_f1) if len(valid_f1) > 0 else 0.0
            LOGGER.info(f"Mean F1 Score: {mean_f1:.4f}")
        return metrics, fitness

model = YOLO("yolo26n.pt")
model.train(data="traffic.yaml", epochs=50, trainer=MetricsTrainer)
```

### Available Metrics (sau validation)

| Key | Mô tả |
|-----|-------|
| `metrics/precision(B)` | Precision |
| `metrics/recall(B)` | Recall |
| `metrics/mAP50(B)` | mAP@IoU=0.5 |
| `metrics/mAP50-95(B)` | mAP@IoU=0.5:0.95 |
| `box.f1` | F1 score per class |
| `box.p` | Precision per class |
| `box.r` | Recall per class |

### Freeze Backbone + Unfreeze

```python
from ultralytics import YOLO
from ultralytics.models.yolo.detect import DetectionTrainer
from ultralytics.utils import LOGGER

FREEZE_EPOCHS = 5

def unfreeze_backbone(trainer):
    if trainer.epoch == FREEZE_EPOCHS:
        LOGGER.info(f"Epoch {trainer.epoch}: Unfreezing all layers")
        for name, param in trainer.model.named_parameters():
            if not param.requires_grad:
                param.requires_grad = True

class FreezingTrainer(DetectionTrainer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_callback("on_train_epoch_start", unfreeze_backbone)

model = YOLO("yolo26n.pt")
model.train(data="traffic.yaml", epochs=50, freeze=10, trainer=FreezingTrainer)
```

---

## 12. DeepStream on Jetson

**Source:** https://docs.ultralytics.com/vi/guides/deepstream-nvidia-jetson/

### JetPack → DeepStream Compatibility

| JetPack | DeepStream | CUDA |
|---------|------------|------|
| 4.6.4 | 6.0.1 | 10.2 |
| 5.1.3 | 6.3 | 11.4 |
| 6.1 | 7.1 | 12.6 |
| 7.1 | 9.0 | — |

### Pipeline tóm tắt

```
1. pip install ultralytics
2. git clone DeepStream-Yolo
3. python3 export_yolo26.py -w best.pt --opset 12 --simplify
4. cp best.pt.onnx labels.txt ~/DeepStream-Yolo/
5. make -C nvdsinfer_custom_impl_Yolo
6. Edit config_infer_primary_yolo26.txt
7. deepstream-app -c deepstream_app_config.txt
```

### FP16 trên Jetson (khuyến nghị cho Nano)

Trong `config_infer_primary_yolo26.txt`:
```ini
model-engine-file=model_b1_gpu0_fp16.engine
network-mode=2
```

### Multi-stream

```ini
[tiled-display]
rows=2
columns=2

[source0]
enable=1
type=3
uri=rtsp://camera1/stream
uri=rtsp://camera2/stream
uri=rtsp://camera3/stream
uri=rtsp://camera4/stream
num-sources=4
```

### Benchmark (Jetson Orin NX 16GB, 640×640)

| Model | FP32 (ms) | FP16 (ms) | INT8 (ms) |
|-------|-----------|-----------|-----------|
| YOLO11n | 8.64 | 5.27 | 4.54 |
| YOLO11s | 14.53 | 7.91 | 6.05 |
| YOLO11m | 32.05 | 15.55 | 10.43 |

---

## 13. Thread-Safe Inference

**Source:** https://docs.ultralytics.com/vi/guides/yolo-thread-safe-inference/

### Rule: Mỗi thread phải tạo model instance riêng

```python
from threading import Thread
from ultralytics import YOLO

def thread_safe_predict(image_path: str) -> None:
    local_model = YOLO("yolo26n.pt")
    results = local_model.predict(image_path)

Thread(target=thread_safe_predict, args=("frame1.jpg",)).start()
Thread(target=thread_safe_predict, args=("frame2.jpg",)).start()
```

### ThreadingLocked Decorator (shared model, serialized access)

```python
from ultralytics import YOLO
from ultralytics.utils import ThreadingLocked

model = YOLO("yolo26n.pt")

@ThreadingLocked()
def thread_safe_predict(image_path: str):
    return model.predict(image_path)
```

> Cho traffic dashboard multi-camera: ưu tiên **multiprocessing** thay vì threading để bypass GIL.

---

## 14. Performance Metrics

**Source:** https://docs.ultralytics.com/vi/guides/yolo-performance-metrics/

### Metrics chính cho Traffic Detection

| Metric | Ý nghĩa | Mục tiêu |
|--------|----------|----------|
| **mAP@0.5** | Mean Average Precision tại IoU=0.5 | ≥ 0.7 |
| **mAP@0.5:0.95** | mAP trung bình nhiều IoU thresholds | ≥ 0.5 |
| **Precision** | Tỷ lệ detection đúng / tổng detection | Giảm false positive |
| **Recall** | Tỷ lệ detection đúng / tổng ground truth | Giảm miss |
| **F1 Score** | Harmonic mean of P & R | Cân bằng P/R |
| **FPS** | Frames per second | ≥ 15 cho real-time |

### Inference Speed Metrics

| Phase | Mô tả |
|-------|-------|
| **Preprocess** | Resize, normalize |
| **Inference** | Forward pass qua model |
| **Postprocess** | NMS, box decode |

### Code — Evaluate model

```python
from ultralytics import YOLO

model = YOLO("best.pt")
metrics = model.val(data="traffic.yaml")

print(f"mAP50:    {metrics.box.map50:.4f}")
print(f"mAP50-95: {metrics.box.map:.4f}")
print(f"Precision: {metrics.box.mp:.4f}")
print(f"Recall:    {metrics.box.mr:.4f}")
```

---

## 15. API Reference

**Source:** https://docs.ultralytics.com/reference/__init__/

### Lazy Import System

```python
from ultralytics import YOLO, SAM, RTDETR, NAS
```

Ultralytics sử dụng `__getattr__` để lazy-import — model class chỉ được load khi truy cập lần đầu:

```python
MODELS = {"YOLO", "SAM", "RTDETR", "NAS", ...}

def __getattr__(name: str):
    if name in MODELS:
        return getattr(importlib.import_module("ultralytics.models"), name)
    raise AttributeError(...)
```

### Solutions Module

```python
from ultralytics import solutions

solutions.ObjectCounter(...)
solutions.SpeedEstimator(...)
solutions.Heatmap(...)
solutions.Analytics(...)
solutions.TrackZone(...)
solutions.VisionEye(...)
solutions.DistanceCalculation(...)
solutions.RegionCounter(...)
solutions.Inference(...)
```

---

## 16. Recommended Stack for Traffic Dashboard

### Edge (Jetson Nano / Orin)

| Component | Recommended | Lý do |
|-----------|-------------|-------|
| Detection | YOLOv8n (pruned+KD) → TensorRT FP16 | Tối ưu cho edge |
| Tracking | ByteTrack | Nhẹ, không cần ReID model |
| Counting | `solutions.ObjectCounter` | Built-in, line/region |
| Speed | `solutions.SpeedEstimator` | Cần calibration `meter_per_pixel` |
| Pipeline | DeepStream SDK | Multi-stream, hardware decode |
| Inference | C++ TensorRT hoặc DeepStream | Tối ưu latency |

### Desktop / Server

| Component | Recommended | Lý do |
|-----------|-------------|-------|
| Detection | YOLOv8n/s + BoT-SORT | Accuracy + ReID |
| Dashboard | **Streamlit** (prototype) hoặc **FastAPI + React** (production) |
| Heatmap | `solutions.Heatmap` | Real-time density viz |
| Analytics | `solutions.Analytics` + Grafana | Charts + time-series |
| Database | InfluxDB / TimescaleDB | Time-series vehicle counts |
| Multi-cam | `multiprocessing` + queue | Bypass GIL |

### Metrics Pipeline

```
Detection → Tracking → Counting/Speed → Database → Dashboard
              │
              └→ Heatmap → Video overlay / Web stream
```

---

## 17. Code Template — Full Traffic Pipeline

```python
import cv2
from ultralytics import solutions

VIDEO_SOURCE = "rtsp://camera_ip/stream"
MODEL_PATH = "best.pt"

cap = cv2.VideoCapture(VIDEO_SOURCE)
assert cap.isOpened(), f"Cannot open {VIDEO_SOURCE}"

w, h, fps = (int(cap.get(x)) for x in (
    cv2.CAP_PROP_FRAME_WIDTH,
    cv2.CAP_PROP_FRAME_HEIGHT,
    cv2.CAP_PROP_FPS,
))

# --- Module 1: Vehicle Counting (line) ---
count_line = [(0, h // 2), (w, h // 2)]
counter = solutions.ObjectCounter(
    show=False,
    region=count_line,
    model=MODEL_PATH,
    classes=[2, 5, 7],  # car, bus, truck
)

# --- Module 2: Speed Estimation ---
speed = solutions.SpeedEstimator(
    show=False,
    model=MODEL_PATH,
    fps=fps,
    meter_per_pixel=0.05,
    classes=[2, 5, 7],
)

# --- Module 3: Heatmap ---
heatmap = solutions.Heatmap(
    show=False,
    model=MODEL_PATH,
    colormap=cv2.COLORMAP_JET,
    classes=[2, 5, 7],
)

# --- Process ---
frame_idx = 0
while cap.isOpened():
    ok, frame = cap.read()
    if not ok:
        break
    frame_idx += 1

    count_result = counter(frame.copy())
    speed_result = speed(frame.copy())
    heat_result = heatmap(frame.copy())

    # Access counts: count_result has IN/OUT data
    # Access speed: speed_result has per-object speed
    # Access heatmap: heat_result.plot_im for overlay

    # Display or stream to dashboard
    cv2.imshow("Heatmap", heat_result.plot_im)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
```

---

## Guides Sub-pages — Quick Reference

**Source:** https://docs.ultralytics.com/vi/guides/

| Guide | Relevance cho Traffic Dashboard |
|-------|-------------------------------|
| **Custom Trainer** | Train model traffic riêng, class weights, freeze backbone |
| **DeepStream on Jetson** | Production deployment multi-stream |
| **Hyperparameter Tuning** | `model.tune()` tối ưu detection accuracy |
| **NVIDIA Jetson** | JetPack setup, TensorRT export |
| **Model Deployment Practices** | ONNX/TensorRT best practices |
| **SAHI Tiled Inference** | Small object (xe máy, biển báo) ở xa |
| **Data Augmentation** | Mosaic, mixup cho traffic data |
| **K-Fold Cross Validation** | Validate model robustness |
| **Model Testing** | Systematic evaluation pipeline |
| **Docker** | Container deployment |
| **Thread-Safe Inference** | Multi-camera processing |
| **Performance Metrics** | mAP, F1, FPS evaluation |

---

## Nguồn tham khảo

| # | URL | Chủ đề |
|---|-----|--------|
| 1 | https://docs.ultralytics.com/vi/modes/track/ | Multi-Object Tracking |
| 2 | https://docs.ultralytics.com/vi/guides/analytics/ | Analytics Charts |
| 3 | https://docs.ultralytics.com/vi/guides/distance-calculation/ | Distance Calculation |
| 4 | https://docs.ultralytics.com/vi/guides/heatmaps/ | Heatmap Visualization |
| 5 | https://docs.ultralytics.com/vi/guides/streamlit-live-inference/ | Streamlit Dashboard |
| 6 | https://docs.ultralytics.com/vi/guides/object-counting/ | Object Counting |
| 7 | https://docs.ultralytics.com/vi/guides/region-counting/ | Region Counting |
| 8 | https://docs.ultralytics.com/vi/guides/speed-estimation/ | Speed Estimation |
| 9 | https://docs.ultralytics.com/vi/guides/trackzone/ | TrackZone |
| 10 | https://docs.ultralytics.com/vi/guides/vision-eye/ | VisionEye |
| 11 | https://docs.ultralytics.com/vi/guides/yolo-thread-safe-inference/ | Thread Safety |
| 12 | https://docs.ultralytics.com/vi/guides/yolo-performance-metrics/ | Performance Metrics |
| 13 | https://docs.ultralytics.com/vi/guides/ | Guides Index |
| 14 | https://docs.ultralytics.com/vi/guides/custom-trainer/ | Custom Trainer |
| 15 | https://docs.ultralytics.com/vi/guides/deepstream-nvidia-jetson/ | DeepStream Jetson |
| 16 | https://docs.ultralytics.com/reference/__init__/ | API Reference |
