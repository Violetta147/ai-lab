# Edge AI Deployment Q&A — Jetson Nano Traffic Monitoring

Tổng hợp toàn bộ câu hỏi về triển khai AI trên Jetson Nano, trả lời cụ thể cho dự án PBL5.

---

## Q1: Supervision / Ultralytics solutions có bản C++ không?

**KHÔNG. Tất cả đều chỉ có Python.**

| Thư viện | Ngôn ngữ | Chức năng | Bản C++? |
|---|---|---|---|
| `ultralytics` solutions | Python | Counter, SpeedEstimator, Heatmap, TrackZone | Không |
| `supervision` (Roboflow) | Python | Annotators, LineZone, ByteTrack, analytics | Không |
| `norfair` | Python | Multi-object tracking | Không |
| `motpy` | Python | Multi-object tracking | Không |

**Tại sao không có C++?** Vì các thư viện này nhắm vào developer dùng Python. Cộng đồng C++ edge AI dùng cách khác:

| Bài toán | Python (supervision/ultralytics) | C++ trên Jetson |
|---|---|---|
| Tracking | `supervision.ByteTrack` | ByteTrack trong `infer/` (đã có) |
| Đếm xe | `solutions.ObjectCounter` | Tự code line crossing (~50 dòng C++) |
| Đo tốc độ | `solutions.SpeedEstimator` | Tự code: homography + track distance/time |
| Heatmap | `solutions.Heatmap` | Tự code: accumulate detections vào matrix |
| Annotate | `supervision.BoxAnnotator` | OpenCV `cv::rectangle`, `cv::putText` |

**Kết luận:** Trên Jetson Nano, nếu chạy C++ pipeline (triple-Mu/infer), phải tự code analytics. Nếu chạy Python (chậm hơn), dùng được supervision/ultralytics solutions.

**DeepStream thay thế tốt hơn cho C++:**
- `NvDCF tracker` = tracking
- `nvdsanalytics` plugin = đếm xe, line crossing, ROI
- `nvmsgbroker` = gửi data ra Kafka/MQTT
- Tất cả chạy trên GPU, không cần code C++ tay

---

## Q2: Có cần deploy AI model thành service (FastAPI + Docker) không?

**Tùy kiến trúc. Có 2 cách:**

### Cách 1: Monolithic (TẤT CẢ trên Jetson) — ĐƠN GIẢN
```
Camera → [Jetson: detect + track + count + hiển thị] → Xong
         Mọi thứ chạy trên 1 process
         Không cần FastAPI, không cần Docker service
```
Dùng khi: demo 1 camera, kết quả hiện trực tiếp trên Jetson.

### Cách 2: Edge-Cloud (Jetson xử lý, Dashboard ở PC) — CHO PBL5
```
Jetson (edge):
  Camera → detect + track → gửi metadata (bbox, count, speed)
                              ↓
                         WebSocket / MQTT / Kafka
                              ↓
PC/Server (cloud):
  FastAPI nhận data → Streamlit dashboard hiển thị
```
Dùng khi: cần dashboard real-time trên PC, multi-camera.

**Câu trả lời: KHÔNG cần FastAPI trên Jetson.** Jetson chỉ chạy inference + gửi kết quả ra ngoài. FastAPI chạy trên PC/server nhận data và hiển thị dashboard.

**KHÔNG cần đóng gói model bằng Docker trên Jetson** (trừ khi dùng DeepStream Docker). Model chạy native hoặc trong DeepStream container.

---

## Q3: Có cần debug hệ thống bằng htop, journalctl, ps aux?

**CÓ, nhưng trên Jetson dùng tool khác tốt hơn:**

| Tool | Dùng khi | Lệnh |
|---|---|---|
| **jtop** | Monitor tổng quan (GPU, CPU, RAM, temp, power) | `jtop` |
| **tegrastats** | Real-time GPU/CPU/RAM/thermal | `tegrastats --interval 1000` |
| **htop** | Xem process nào ngốn CPU/RAM | `htop` |
| **journalctl** | Xem log khi service crash | `journalctl -u nv-l4t-usb-device-mode -f` |
| **dmesg** | Kernel log (OOM kill, GPU error) | `dmesg --follow` |
| **nvprof** | Profile CUDA kernels | `nvprof ./main` |
| **trtexec** | Benchmark TensorRT engine | `trtexec --loadEngine=yolov8n.engine --warmUp=500` |

**Khi nào cần debug:**
- RAM hết → `dmesg | grep -i oom` (xem kernel kill process nào)
- GPU lỗi → `dmesg | grep -i nvidia`
- FPS drop → `tegrastats` (xem GPU/CPU utilization)
- Container crash → `docker logs <container_id>`

---

## Q4: Pipeline real-time tối ưu — tách thread, FPS, delay?

### triple-Mu / infer đã tách thread chưa?

**infer/ framework ĐÃ CÓ** producer-consumer model (`cpm.hpp`):
```
Thread 1 (Producer): Đọc frame từ camera → đẩy vào queue
Thread 2 (Consumer): Lấy frame từ queue → TensorRT inference → postprocess
                     Không block thread đọc camera
```
Đây là thiết kế chuẩn cho real-time inference.

### DeepStream tách thread không?

**DeepStream tách PIPELINE, không phải thread thủ công:**
```
GStreamer pipeline tự quản lý:
  [Source pad] → [Queue] → [Decode pad] → [Queue] → [Inference pad] → ...
  Mỗi element có buffer queue riêng
  GStreamer tự cân bằng throughput
  Không cần tự code thread
```

### Tối ưu FPS/delay:

| Kỹ thuật | Ai làm | Đã làm chưa? |
|---|---|---|
| Tách thread đọc cam / inference | infer/ cpm.hpp | ĐÃ CÓ |
| Batch size = 1 cho real-time | TensorRT engine | CẦN VERIFY |
| Fixed input shape (640x640) | Export ONNX | CẦN VERIFY |
| FP16 inference | Engine đã build | ĐÃ CÓ (yolov8n_fp16.engine) |
| Skip frames (xử lý 1 trong N frames) | Tự code | TÙY NHU CẦU |
| Async decode + inference | DeepStream pipeline | NẾU DÙNG DS |

---

## Q5: Edge → Cloud monitoring?

### Cách gửi data từ Jetson ra:

| Phương thức | Dùng khi | Thư viện |
|---|---|---|
| **WebSocket** | Dashboard real-time, đơn giản | Python: `websockets`, C++: `libwebsockets` |
| **MQTT** | IoT, nhẹ, Jetson → broker → dashboard | `paho-mqtt` |
| **Kafka** | Production, nhiều consumer, persistent | DeepStream nvmsgbroker |
| **RTSP stream** | Gửi video có annotate | DeepStream hoặc GStreamer |
| **HTTP/REST** | Gửi batch data, không real-time | FastAPI trên PC nhận |

### Kiến trúc khuyến nghị cho PBL5:
```
Jetson (edge)                          PC (cloud/server)
┌──────────────┐    WebSocket/MQTT    ┌──────────────────┐
│ YOLOv8 detect│ ──── metadata ────→ │ FastAPI server    │
│ + ByteTrack  │    (JSON: bbox,     │ + Streamlit dash  │
│ + counting   │     count, speed)   │ (hiển thị)        │
└──────────────┘                     └──────────────────┘
```

---

## Q6: Benchmark, latency, profiling?

**CÓ, rất quan trọng cho đồ án.**

### Benchmark TensorRT engine:
```bash
# Trên Jetson:
trtexec --loadEngine=yolov8n_fp16.engine \
        --warmUp=500 --duration=60 --percentile=99
# → Cho biết: avg latency, throughput (FPS), p99 latency
```

### Profile CUDA:
```bash
nvprof ./main   # Profile infer/ binary
# → Cho biết: kernel nào chậm, memory transfer time, GPU utilization
```

### Đo end-to-end latency:
```bash
# Trong code, đo thời gian mỗi giai đoạn:
# t1 = đọc frame
# t2 = preprocess
# t3 = inference
# t4 = postprocess
# t5 = tracking
# t6 = annotate + display
# → Biết bottleneck ở đâu
```

---

## Q7: SIMD có cần không?

**KHÔNG CẦN tự dùng SIMD.** Lý do:
- TensorRT đã tối ưu mọi GPU operations
- OpenCV C++ (4.8.x CUDA) đã dùng NEON SIMD cho ARM CPU operations
- CUDA kernels trong infer/ đã tối ưu preprocess/postprocess trên GPU
- Tự viết SIMD assembly trên ARM sẽ không nhanh hơn đáng kể

SIMD (NEON trên ARM) chỉ hữu ích nếu tự viết CPU-side processing từ đầu. Các thư viện đã dùng sẵn.

---

## Q8: Tối ưu memory, GPU, CPU?

### Memory:
| Kỹ thuật | Mô tả | Áp dụng |
|---|---|---|
| Pre-allocate buffers | Cấp phát GPU memory 1 lần, reuse | TensorRT đã làm |
| CUDA unified memory | CPU+GPU chia sẻ address space | Jetson Nano tự động (shared memory) |
| Tránh memory leak | Free CUDA memory sau inference | Kiểm tra bằng `tegrastats` |
| Giảm resolution | 640→320 nếu đủ accuracy | Trade-off FPS vs accuracy |

### GPU:
| Kỹ thuật | Mô tả | Đã làm? |
|---|---|---|
| FP16 inference | Nhanh gấp đôi FP32 | ĐÃ CÓ |
| MAXN power mode | Full GPU/CPU clock | CẦN SET |
| jetson_clocks | Lock max frequency | CẦN SET |
| Batch size = 1 | Giảm latency cho real-time | CẦN VERIFY |

### CPU:
- **CPU KHÔNG xử lý AI inference** — GPU (TensorRT) làm hết
- CPU chỉ: đọc camera (nếu không dùng NVDEC), quản lý pipeline, tracking logic (nếu dùng C++ ByteTrack), gửi data ra network
- Tắt service không cần để giải phóng CPU: `systemctl disable apt-daily snapd ModemManager`

---

## Q9: Framework overhead đã loại bỏ chưa? Model đã compile tối ưu chưa?

### Framework overhead:
| Cách chạy | Overhead | Trạng thái |
|---|---|---|
| Python + PyTorch | **CAO** (~200-500ms/frame) | KHÔNG dùng cho production |
| Python + TensorRT (ultralytics export) | Trung bình (~50-100ms overhead Python) | Dùng được cho dev |
| **C++ + TensorRT (infer/, triple-Mu)** | **GẦN ZERO** (~1-2ms overhead) | **ĐÃ CÓ** |
| **DeepStream** | **ZERO** (native C/GStreamer) | NẾU CÀI |

infer/ và triple-Mu C++ pipeline **đã loại bỏ hoàn toàn PyTorch overhead**. Gọi TensorRT API trực tiếp.

### Model đã compile tối ưu chưa?
- `yolov8n_fp16.engine` — **ĐÃ compile FP16 cho Tegra X1** ✓
- `best_v8n_pruned.engine` — **ĐÃ compile + pruned** ✓
- TensorRT tự động: layer fusion, kernel auto-tuning, memory optimization ✓

---

## Q10: Execution graph tối ưu chưa?

**TensorRT engine BUILD = tối ưu execution graph.** Khi build engine:
1. Parse ONNX graph
2. Layer fusion (Conv+BN+ReLU → 1 kernel)
3. Kernel selection (chọn kernel nhanh nhất cho GPU cụ thể)
4. Memory planning (tối ưu GPU memory layout)
5. Output: `.engine` file = optimized execution graph

**Đã build rồi → ĐÃ TỐI ƯU.** Không cần làm thêm gì.

---

## Q11: Calibration dataset — FP16 có cần không?

**KHÔNG. FP16 không cần calibration dataset.**

| Precision | Cần calibration? | Lý do |
|---|---|---|
| FP32 | Không | Giữ nguyên precision |
| **FP16** | **Không** | Chỉ giảm bit-width, KHÔNG cần statistics |
| INT8 | **CÓ** | Cần dataset để tính min/max range cho quantization |

Jetson Nano (Maxwell GPU) **KHÔNG hỗ trợ INT8 inference** → FP16 là lựa chọn tốt nhất, và không cần calibration.

---

## Q12: Batch size = 1 cho real-time?

**ĐÚNG.** Và đây là setting lúc INFERENCE, không liên quan đến training.

| | Training | Inference |
|---|---|---|
| Batch size | 16, 32, 64... (lớn → GPU util cao) | **1** (cho real-time, thấp latency) |
| Mục đích | Tận dụng GPU song song | Xử lý từng frame ngay lập tức |
| Latency | Không quan trọng | **Rất quan trọng** |

```
Batch=1:  Frame vào → 20ms xử lý → kết quả ngay → 50 FPS
Batch=4:  Đợi 4 frame → 40ms xử lý → kết quả cả 4 → throughput cao hơn nhưng delay 3 frame
```

Real-time camera → **Batch = 1** luôn.

---

## Q13: Fixed input shape?

**ĐÃ LÀM (khi build engine).** TensorRT engine có 2 loại:
- Static shape: input cố định (ví dụ 1x3x640x640) — **NHANH HƠN**
- Dynamic shape: input thay đổi — linh hoạt nhưng chậm hơn

File `yolov8n_static_fp16.engine` cho thấy đã build static shape. Đúng cách.

---

## Q14: Tăng tốc xử lý từng frame?

Checklist:

| Kỹ thuật | Mô tả | Trạng thái |
|---|---|---|
| TensorRT FP16 | GPU inference tối ưu | ✓ ĐÃ CÓ |
| CUDA preprocess | resize, normalize trên GPU | ✓ infer/ yolo.cu |
| CUDA postprocess | NMS trên GPU | ✓ infer/ yolo.cu |
| Async pipeline | Đọc frame song song inference | ✓ infer/ cpm.hpp |
| Hardware decode | NVDEC (chỉ DeepStream) | ✗ CHƯA (nếu chưa cài DS) |
| Skip frames | Xử lý 1/2 hoặc 1/3 frame | TÙY NHU CẦU |
| Reduce resolution | 640→416 hoặc 320 | Trade-off accuracy |

---

## Q15: Profiler đo latency?

### Trên Jetson:
```bash
# TensorRT profiler (engine-level)
trtexec --loadEngine=yolov8n_fp16.engine --warmUp=500 --duration=30

# CUDA profiler (kernel-level)
nvprof --print-gpu-trace ./main

# System-level
tegrastats --interval 500    # GPU%, CPU%, RAM, temp mỗi 0.5s
jtop                         # GUI monitor
```

### Trong code C++ (infer/):
infer/ framework đã có benchmark: `benchmark_runtime.sh` và kết quả trong `benchmark_*` directories.

---

## Q16: DeepStream pipeline hoàn chỉnh?

**CHƯA.** Cần cài DeepStream trước, rồi build pipeline.

### Có 2 cách viết DeepStream pipeline:

**Cách 1: Config file (.txt) + deepstream-app** — dùng config, không code
```bash
deepstream-app -c deepstream_app_config.txt
```

**Cách 2: Python + pyds bindings** — code pipeline bằng Python, linh hoạt hơn
```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import pyds  # NVIDIA DeepStream Python bindings
```

> **QUAN TRỌNG:** pyds chỉ có trong Docker image `6.0.1-samples` (cần compile).
> `6.0.1-base` KHÔNG có pyds source → không code Python pipeline được.

### Chọn Docker image nào?

| Image | Size | Có pyds? | Có samples? | Dùng khi |
|---|---|---|---|---|
| `6.0.1-samples` | ~2.5GB | **Có** (cần build) | **Có** | **DÙNG CÁI NÀY** — dev + prototype |
| `6.0.1-base` | ~1.5GB | Không | Không | Production đã hoàn thiện, muốn nhẹ |
| `6.0.1-iot` | ~1.8GB | Không | Không | Chuyên Kafka/MQTT output |
| `6.0.1-triton` | ~3.5GB | Không | Không | **CẤM trên Nano** — sập RAM ngay |

### 5 plugin GStreamer cốt lõi (dùng pyds):

```
1. INGEST: nvmultiurisrcbin
   → Thu nhận video từ camera/RTSP/file

2. BATCH: nvstreammux
   → Gom frame từ nhiều source thành batch
   → Quan trọng cho multi-stream

3. INFER: nvinfer
   → Nạp TensorRT engine (.engine) để detect
   → CẤU HÌNH: KHÔNG BAO GIỜ dùng FP32 trên Nano
   → Phải set network-mode=2 (FP16) trong config

4. TRACK: nvtracker (NvDCF)
   → Tracker built-in của NVIDIA, tích hợp sâu vào pipeline
   → Tốt hơn tự tích hợp ByteTrack từ bên ngoài (phức tạp, overhead)
   → Cho tracking ID để đếm xe qua polygon zones

5. OUTPUT: nvmsgbroker
   → Đẩy metadata (số lượng xe, mật độ, tốc độ) ra Kafka/MQTT
   → Kết nối với dashboard ở PC
```

### Pipeline hoàn chỉnh:

```
[nvmultiurisrcbin] → [nvstreammux] → [nvinfer] → [nvtracker] → [nvdsanalytics] → [nvdsosd] → [sink]
     camera/RTSP        batch frames    YOLOv8       NvDCF        đếm xe,          vẽ bbox     display/
                                        FP16 engine  tracking     line crossing                 RTSP/file
                                                                                       ↓
                                                                              [nvmsgconv] → [nvmsgbroker]
                                                                                              Kafka/MQTT
                                                                                              → Dashboard
```

### Lưu ý quan trọng từ kinh nghiệm thực tế:
- **KHÔNG BAO GIỜ chạy FP32** trên Nano → FP16 bắt buộc (network-mode=2)
- FP16 chỉ mất ~1-2% accuracy nhưng FPS tăng 2-3x
- INT8 Nano không hỗ trợ nên FP16 là tốt nhất
- Nếu video .mp4 không đọc được trong container → chạy:
  ```bash
  /opt/nvidia/deepstream/deepstream/user_additional_install.sh
  ```
  Lệnh này tải thêm codec libraries (H.264, H.265 decoder)

---

## Q17: Input/Output đã chuẩn hóa chưa?

### Input:
- Normalize: `1/255` (pixel 0-255 → 0.0-1.0) — **ĐÃ CÓ** trong TensorRT engine
- Resize: letterbox padding về 640x640 — **ĐÃ CÓ** trong CUDA preprocess
- Color: BGR→RGB — **ĐÃ CÓ**

### Output:
- Format: `[num_dets, bboxes(N,4), scores(N), labels(N)]` — chuẩn triple-Mu format
- NMS: **ĐÃ TÍCH HỢP** trong engine (EfficientNMS plugin)
- DeepStream cần custom parser để đọc format này → đó là plugin `csrc/deepstream/`

---

## Q18: OTA update model từ xa là gì?

**OTA (Over-The-Air) = cập nhật model mới cho Jetson mà không cần ra hiện trường.**

```
Quy trình OTA:
  PC (train model mới) → export .engine → upload lên server
                                            ↓
  Jetson (tại hiện trường) → download .engine mới → restart pipeline
                             Tự động, không cần người đến
```

**Cách đơn giản cho PBL5:**
```bash
# Trên Jetson, dùng scp hoặc rsync:
scp user@server:/models/yolov8n_v2.engine ~/models/
# Restart pipeline
```

**Cách production:**
- NVIDIA Fleet Command (quản lý fleet Jetson từ xa)
- Hoặc tự build: script cron check server → download model mới → restart service

**Cho đồ án PBL5: KHÔNG CẦN.** OTA là tính năng production. Demo chỉ cần copy model thủ công.

---

## Q19: Kết nối camera từ xa? DeepStream hỗ trợ không?

**CÓ, DeepStream hỗ trợ native.**

| Loại camera | Kết nối | DeepStream source type |
|---|---|---|
| USB camera | `/dev/video0` | `type=1` (CameraV4L2) |
| CSI camera (Raspberry Pi cam) | MIPI CSI | `type=5` (CSI) |
| IP camera (RTSP) | `rtsp://ip:port/stream` | `type=4` (URI) |
| Video file | `/path/to/video.mp4` | `type=3` (URI) |

**Camera từ xa = IP camera qua RTSP.** Config trong DeepStream:
```ini
[source0]
enable=1
type=4
uri=rtsp://192.168.1.100:554/stream1
```

**Không dùng DeepStream:** OpenCV cũng đọc được RTSP:
```python
cap = cv2.VideoCapture("rtsp://192.168.1.100:554/stream1")
```

---

## Q20: 3 cách xem kết quả DeepStream (output methods)

**Nguồn:** Hướng dẫn từ thầy.

### Cách 1: Xuất file video — Dễ nhất, dùng cho báo cáo
```
Pipeline → nvdsosd (vẽ bbox, ID, FPS) → FileSink → file .mp4/.mkv trên Jetson
```
- DeepStream vẽ bbox + tracking ID + FPS lên video
- Lưu thành file .mp4 trên Jetson (hoặc USB)
- Xem: dùng WinSCP/FileZilla kéo file từ Nano sang Laptop

### Cách 2: RTSP live stream — Real-time qua mạng LAN
```
Pipeline → nvdsosd → RTSP Sink → phát stream qua mạng WiFi/LAN
```
- Jetson biến thành "đài phát sóng" video đã xử lý
- Xem: Laptop mở VLC → Open Network Stream → `rtsp://192.168.x.x:8554/ds-test`
- Giống hệ thống camera an ninh thật

### Cách 3: Chỉ gửi metadata (JSON) — Chuẩn doanh nghiệp
```
Pipeline → nvmsgconv → nvmsgbroker → MQTT/Kafka → Cloud/Dashboard
```
- KHÔNG gửi video (tốn băng thông)
- Chỉ gửi JSON: `{"time": "10:00", "type": "Truck", "id": 12, "count": 45}`
- Thỉnh thoảng gửi 1 ảnh chụp từ camera
- Xem: Dashboard web (biểu đồ nhảy số liên tục)

### Khuyến nghị cho PBL5:
- **Flow hiện tại nên chốt:** RTSP-in từ Laptop (`source type=4`) + RTSP-out từ Jetson.
- **Không lưu MP4 trên Jetson** để tránh tốn I/O và dung lượng thẻ nhớ.
- **Ghi MP4 trên Laptop** từ luồng RTSP-out của Jetson bằng FFmpeg:
  ```bash
  ffmpeg -rtsp_transport tcp -i rtsp://<JETSON_IP>:8555/ds-test -c copy output_jetson_processed.mp4
  ```
- **Demo trước mặt thầy:** xem live bằng VLC từ RTSP-out của Jetson.
- **Nộp báo cáo:** dùng file MP4 đã record ở Laptop.

---

## Tổng hợp: Cái gì đã làm, cái gì chưa?

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| Model training (YOLOv8n) | ✓ ĐÃ LÀM | best.pt, best.onnx |
| Export ONNX | ✓ ĐÃ LÀM | yolov8n.onnx |
| TensorRT engine build (FP16) | ✓ ĐÃ LÀM | yolov8n_fp16.engine |
| Model pruning | ✓ ĐÃ LÀM | best_v8n_pruned.engine |
| Fixed input shape | ✓ ĐÃ LÀM | yolov8n_static_fp16.engine |
| C++ inference pipeline | ✓ ĐÃ LÀM | infer/ + triple-Mu |
| CUDA preprocess/postprocess | ✓ ĐÃ LÀM | infer/ yolo.cu |
| ByteTrack tracking | ✓ ĐÃ LÀM | infer/ bt_byte_tracker.cpp |
| Producer-consumer async | ✓ ĐÃ LÀM | infer/ cpm.hpp |
| Framework overhead removed | ✓ ĐÃ LÀM | C++ direct TensorRT, no Python |
| Execution graph optimized | ✓ ĐÃ LÀM | TensorRT engine build = tối ưu graph |
| Docker daemon.json fix | ✓ ĐÃ LÀM | default-runtime nvidia ✅ |
| Headless mode | ✓ ĐÃ LÀM | multi-user.target ✅ |
| Swap optimized | ✓ ĐÃ LÀM | swappiness=10, snap removed ✅ |
| Calibration dataset | ✗ KHÔNG CẦN | FP16 không cần, INT8 Nano không hỗ trợ |
| SIMD optimization | ✗ KHÔNG CẦN | Libraries đã dùng NEON sẵn |
| OTA model update | ✗ KHÔNG CẦN | Cho production, không cần cho PBL5 |
| Batch size = 1 real-time | ? CẦN VERIFY | Kiểm tra engine build settings |
| **Nguồn 5V-4A Barrel Jack** | **? CẦN KIỂM TRA** | **BẮT BUỘC cho MAXN** |
| **Quạt tản nhiệt** | **? CẦN KIỂM TRA** | **BẮT BUỘC cho MAXN** |
| MAXN power mode | ✗ CHƯA | Cần nguồn + quạt trước |
| DeepStream pipeline | ✗ CHƯA | Pull 6.0.1-samples |
| Hardware video decode | ✗ CHƯA | Cần DeepStream |
| Analytics (đếm xe, speed) | ✗ CHƯA | nvdsanalytics trong DeepStream |
| Edge → Cloud data flow | ✗ CHƯA | MQTT/Kafka từ Jetson → Dashboard |
| Dashboard UI | ✗ CHƯA | Streamlit/FastAPI trên PC |
| Benchmark/profiling | ? CÓ SẴN | infer/ có benchmark results |
