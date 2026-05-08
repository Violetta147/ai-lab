# Jetson Nano - Tài liệu hệ thống & Cấu trúc thiết bị

## 1. Tổng quan thiết bị

### 1.1 Thông tin Hardware & Firmware

| Thông số | Giá trị |
|---|---|
| **Board** | NVIDIA Jetson Nano (t210ref) |
| **OS** | Ubuntu 20.04.6 LTS (focal) |
| **L4T Version** | R32.6.1 (Linux for Tegra) |
| **JetPack Version** | 4.6 (b199) |
| **GCID** | 27863751 |
| **Architecture** | aarch64 (ARM 64-bit) |
| **Build Date** | Mon Jul 26 19:20:30 UTC 2021 |
| **Core Package** | nvidia-l4t-core 32.6.1-20210726122000 |

> **Lưu ý về OS:** JetPack 4.6 chính thức của NVIDIA đi kèm Ubuntu **18.04**. Hệ thống này chạy Ubuntu **20.04**, nghĩa là đây là **custom image** của Qengineering — dùng Ubuntu 20.04 làm base, rồi cài đè L4T R32.6.1 kernel/drivers và JetPack 4.6 packages lên trên.
>
> Bằng chứng custom image: Python 3.8.10 (mặc định Ubuntu 20.04), PyTorch 1.13.0a0 (build từ source, suffix `+git7c98e70`), OpenCV 4.13.0 (build từ source). Các bản JetPack chính thức không đi kèm PyTorch hay OpenCV phiên bản này.

**GPU xác nhận:**
- `torch.cuda.is_available()` → **True**
- `torch.cuda.get_device_name(0)` → **NVIDIA Tegra X1**
- PyTorch đã nhận GPU và có thể chạy inference/training trên CUDA.

**Board IDs (từ plugin-manager):**
- **Carrier Board:** 3449-0000-400 → kết nối qua I2C bus `i2c@7000c500`, module tại địa chỉ `0x57`
- **SoM (System on Module):** 3448-0000-402 → kết nối qua I2C bus `i2c@7000c500`, module tại địa chỉ `0x50`

> **3448** = Jetson Nano SoM (4GB), **3449** = Jetson Nano Developer Kit Carrier Board.

### 1.1b Qengineering Overclock
Bản Qengineering đã can thiệp kernel để nâng mức trần xung nhịp GPU/CPU vượt mức gốc NVIDIA.
- `sudo nvpmodel -m 0` → gỡ giới hạn 5W, cho phép 10-15W
- `sudo jetson_clocks` → khóa CPU/GPU/RAM ở xung nhịp cao nhất (bao gồm mức OC của Qengineering)
- Không gõ `jetson_clocks` → máy không bao giờ chạm mức OC → phí bản Qengineering
- **Yêu cầu:** nguồn 5V-4A Barrel Jack + quạt tản nhiệt (xem issues.md #7)

### 1.2 JetPack 4.6 — Software Stack

JetPack là bộ SDK tổng hợp của NVIDIA cho Jetson. `nvidia-jetpack` là **meta-package** — bản thân nó không chứa code, mà kéo theo (depends) tất cả các thành phần AI/GPU cần thiết:

```
nvidia-jetpack (4.6-b199)
├── nvidia-cuda          → CUDA Toolkit (compiler, runtime, libraries)
├── nvidia-cudnn8        → cuDNN (deep learning primitives)
├── nvidia-tensorrt      → TensorRT (inference optimizer)
├── nvidia-opencv        → OpenCV with CUDA support
├── nvidia-visionworks   → VisionWorks (computer vision primitives)
├── nvidia-vpi           → Vision Programming Interface
├── nvidia-container     → NVIDIA Container Runtime (Docker GPU support)
└── nvidia-l4t-jetson-multimedia-api → Multimedia API (camera, codec, V4L2)
```

### 1.3 Phiên bản phần mềm chi tiết

| Component | Version | Ghi chú |
|---|---|---|
| **CUDA** | 10.2 (V10.2.300) | `nvcc` compiler, release 10.2 |
| **cuDNN** | 8.2.1 | Deep learning acceleration primitives |
| **TensorRT** | 8.0.1 (+cuda10.2) | Inference optimizer & runtime |
| **PyTorch** | 1.13.0a0+git7c98e70 | Build từ source cho aarch64, CUDA enabled |
| **OpenCV (Python pip)** | 4.13.0 | `~/.local/` — CUDA: NO, GStreamer: NO, FFMPEG only |
| **OpenCV (C++ system)** | 4.1 / 4.2 / 4.5 / 4.6 / 4.8 | `/usr/lib/aarch64-linux-gnu/` — 4.5/4.6/4.8 có CUDA |
| **Python** | 3.8.10 | System Python (Ubuntu 20.04 default) |
| **pip** | 25.0.1 | Package manager |
| **setuptools** | 58.0.4 | Build backend |
| **wheel** | 0.34.2 | Package format |
| **jtop** | 4.3.2 | Jetson system monitor (jetson-stats) |

### 1.4 Docker & NVIDIA Container Runtime

| Component | Version / Value | Mô tả |
|---|---|---|
| **Docker Runtimes** | `io.containerd.runc.v2`, `nvidia`, `runc` | 3 runtimes có sẵn |
| **Default Runtime** | `runc` | Runtime mặc định (không có GPU) |
| **nvidia-container-toolkit** | 1.0.1-1 (arm64) | Hook cho phép Docker container truy cập GPU |

**Cách hoạt động:**
- `runc` = runtime chuẩn của Docker, container **không** thấy GPU
- `nvidia` = runtime đặc biệt, inject NVIDIA driver + CUDA libs vào container → container truy cập được GPU
- Khi chạy `docker run --runtime nvidia ...`, Docker dùng `nvidia` runtime thay vì `runc`
- `nvidia-container-toolkit` (1.0.1-1) là package cài hook `nvidia-container-runtime-hook` — nó tự động mount `/dev/nvidia*`, CUDA libraries, và driver vào bên trong container

```
docker run --runtime runc ...      →  Container KHÔNG thấy GPU
docker run --runtime nvidia ...    →  Container thấy GPU (128 CUDA cores)
```

> **Lưu ý:** Default runtime là `runc`, nên **phải luôn thêm `--runtime nvidia`** khi chạy container cần GPU (hoặc cấu hình `/etc/docker/daemon.json` để đổi default thành nvidia).

### 1.5 TensorRT packages đã cài

| Package | Version | Mô tả |
|---|---|---|
| `libnvinfer8` | 8.0.1-1+cuda10.2 | TensorRT runtime libraries |
| `libnvinfer-dev` | 8.0.1-1+cuda10.2 | Development headers & libs |
| `libnvinfer-plugin8` | 8.0.1-1+cuda10.2 | TensorRT plugin libraries (custom layers) |
| `libnvinfer-plugin-dev` | 8.0.1-1+cuda10.2 | Plugin development headers |
| `libnvinfer-bin` | 8.0.1-1+cuda10.2 | TensorRT CLI binaries (trtexec) |
| `libnvinfer-samples` | 8.0.1-1+cuda10.2 | Sample code |
| `libnvinfer-doc` | 8.0.1-1+cuda10.2 | Documentation |

---

## 2. Ổ E:\ - USB Mass Storage (nhìn từ Windows)

Khi kết nối Jetson Nano với PC Windows qua cáp micro-USB, Jetson tự động expose một phân vùng USB Mass Storage **read-only**. Đây chính là ổ `E:\` trên Windows.

### 2.1 Cấu trúc thư mục

```
E:\
├── INDEX.txt                    # Mục lục tài liệu
├── README-usb-dev-mode.txt      # Hướng dẫn USB Device Mode
├── README-wifi.txt              # Hướng dẫn kết nối WiFi
├── README-vnc.txt               # Hướng dẫn cấu hình VNC
├── l4t-serial.inf               # Windows driver cho USB serial port
└── version/
    ├── nv_tegra_release          # Phiên bản L4T firmware
    ├── nvidia-l4t-core.dpkg-s.txt # Thông tin package nvidia-l4t-core
    └── plugin-manager/
        ├── name                  # "plugin-manager"
        ├── odm-data/             # Cấu hình hardware ODM
        │   ├── name              # "odm-data"
        │   ├── disable-uart-over-jack
        │   ├── enable-utmi1-snps
        │   ├── no-battery
        │   ├── enable-debug-console
        │   ├── enable-pmic-wdt
        │   ├── disable-tegra-wdt
        │   └── normal-build
        └── ids/                  # Board identification
            ├── name              # "ids"
            ├── 3449-0000-400     # Carrier board ID
            ├── 3448-0000-402     # SoM module ID
            └── connection/
                └── i2c@7000c500/
                    ├── module@0x50/  # SoM EEPROM
                    └── module@0x57/  # Carrier EEPROM
```

### 2.2 Chi tiết từng file

#### INDEX.txt
Mục lục tài liệu, liệt kê 3 file README chính và mô tả ngắn.

#### README-usb-dev-mode.txt — USB Device Mode
Hướng dẫn đầy đủ về **3 giao thức USB Device Mode** mà Jetson hỗ trợ đồng thời:

**a) Ethernet qua USB:**
- Jetson có IP tĩnh: `192.168.55.1`
- PC host được cấp DHCP: `192.168.55.100`
- IPv6 link-local: `fe80::1`
- Hỗ trợ 2 loại driver: **RNDIS** (Windows) và **NCM** (Mac/Linux)
- Dùng để SSH/SFTP vào Jetson:
  - Linux/Mac: `ssh nvidia@192.168.55.1` hoặc `ssh nvidia@fe80::1%usb0`
  - Windows: dùng PuTTY
- Có thể biến PC thành gateway Internet cho Jetson (qua IP forwarding + NAT)
- Cấu hình IP tại: `/opt/nvidia/l4t-usb-device-mode/nv-l4t-usb-device-mode-config.sh`

**b) Serial Port (UART ảo):**
- Tạo cổng COM ảo trên Windows, `/dev/ttyACM0` trên Linux
- Dùng terminal app (PuTTY, Screen, Picocom, Tera Term) để login
- Baud rate bất kỳ, cấu hình 8N1

**c) USB Mass Storage:**
- Chính là ổ E:\ đang thấy trên Windows
- **Read-only**, chứa driver và tài liệu
- Tự động mount trên mọi hệ điều hành

**Tắt/bật USB Device Mode:**
- Tạm thời: `sudo service nv-l4t-usb-device-mode stop/start`
- Vĩnh viễn: `sudo systemctl disable nv-l4t-usb-device-mode.service`

#### README-wifi.txt — Kết nối WiFi
- Dùng NetworkManager: `sudo nmcli device wifi connect 'SSID' password 'PASSWORD'`
- Hoặc dùng GUI nếu có gắn màn hình HDMI
- Cần cài trước: `sudo apt install network-manager`

#### README-vnc.txt — VNC Remote Desktop
Hướng dẫn cài đặt VNC server (Vino) để điều khiển Jetson từ xa không cần màn hình:
- Cài: `sudo apt install vino`
- Cấu hình: tắt prompt, tắt encryption, đặt password
- Autostart khi login
- Mặc định resolution 640x480 khi không gắn HDMI, thay đổi tại `/etc/X11/xorg.conf`
- Kết nối bằng VNC client (gvncviewer, Remmina, RealVNC...)

#### l4t-serial.inf — Windows USB Serial Driver
- File driver `.inf` cho Windows nhận diện cổng Serial ảo của Jetson
- USB Vendor ID: `0955` (NVIDIA), Product ID: `701A`
- Tên thiết bị: "L4T Serial Device"
- Cần cài thủ công trên Windows < 10; Windows 10+ tự nhận

#### version/nv_tegra_release
Một dòng duy nhất chứa thông tin firmware:
```
# R32 (release), REVISION: 6.1, GCID: 27863751, BOARD: t210ref, EABI: aarch64, DATE: Mon Jul 26 19:20:30 UTC 2021
```

#### version/nvidia-l4t-core.dpkg-s.txt
Thông tin Debian package `nvidia-l4t-core`:
- Version: 32.6.1-20210726122000
- Dependencies: libc6, libegl1, libexpat1, libgcc1, libstdc++6
- Đây là package lõi của L4T, chứa NVIDIA Tegra libraries

#### version/plugin-manager/
Hệ thống **Plugin Manager** của NVIDIA dùng để tự động nhận diện phần cứng và áp dụng Device Tree Overlay phù hợp:

**odm-data/ (Original Device Manufacturer data):**

| File | Ý nghĩa |
|---|---|
| `disable-uart-over-jack` | Tắt UART qua jack 3.5mm audio |
| `enable-utmi1-snps` | Bật USB UTMI PHY (Synopsys controller) |
| `no-battery` | Board không có pin (chạy nguồn DC) |
| `enable-debug-console` | Bật debug console (UART debug) |
| `enable-pmic-wdt` | Bật watchdog timer trên PMIC (Power Management IC) |
| `disable-tegra-wdt` | Tắt Tegra internal watchdog timer |
| `normal-build` | Đánh dấu là bản build bình thường (không phải debug/recovery) |

> Các file này có kích thước 0 byte — sự tồn tại (có/không) của file là cờ bật/tắt tính năng.

**ids/ (Board Identification):**
- `3449-0000-400`: Carrier board, đọc EEPROM tại I2C address `0x57`
- `3448-0000-402`: SoM module, đọc EEPROM tại I2C address `0x50`
- Plugin Manager dùng ID này để chọn đúng Device Tree Overlay cho phần cứng cụ thể

---

## 3. Thư mục Home trên Jetson Nano

```
jetson@nano:~$
├── Desktop/
├── Documents/
├── Downloads/
├── Music/
├── Pictures/
├── Public/
├── Templates/
├── Videos/
├── KHOA_PBL5_TRAFFIC/           # Dự án PBL5 Traffic Monitoring
├── docker_dli_run.sh            # Script khởi chạy NVIDIA DLI Docker container
├── nomachine_9.3.7_1_arm64.deb  # NoMachine remote desktop installer
└── nvdli-data/                  # Thư mục data cho NVIDIA DLI courses
```

### 3.1 Chi tiết các mục quan trọng

#### docker_dli_run.sh — NVIDIA Deep Learning Institute Container

##### DLI Docker Container là gì?

**NVIDIA DLI (Deep Learning Institute)** là nền tảng đào tạo chính thức của NVIDIA. Thay vì bắt người dùng tự cài đặt hàng chục thư viện AI (TensorFlow, PyTorch, Jupyter, CUDA bindings...), NVIDIA đóng gói toàn bộ thành một **Docker image** sẵn sàng chạy.

**Docker container này chứa:**

| Thành phần | Mô tả |
|---|---|
| **JupyterLab** | IDE trên trình duyệt web (port 8888), nơi viết và chạy code |
| **Pre-built notebooks** | Bài thực hành có sẵn (image classification, object detection...) |
| **TensorFlow / PyTorch** | Framework deep learning đã build cho ARM + CUDA 10.2 |
| **CUDA + cuDNN bindings** | GPU acceleration cho inference & training |
| **Pre-trained models** | ResNet-18, SSD-MobileNet... đã tối ưu cho Jetson |
| **Camera utilities** | Thư viện truy cập CSI/USB camera trực tiếp |
| **OpenCV (GPU)** | Computer vision với CUDA backend |

**Tại sao dùng Docker?** Vì trên Jetson Nano (ARM aarch64 + CUDA 10.2), việc build TensorFlow/PyTorch từ source rất khó và mất nhiều giờ. Docker image có sẵn mọi thứ đã biên dịch đúng cho phần cứng.

##### Script docker_dli_run.sh chạy lệnh dạng:
```bash
sudo docker run --runtime nvidia -it --rm \
    --network host \
    --volume ~/nvdli-data:/nvdli-nano/data \
    --device /dev/video0 \
    nvcr.io/nvidia/dli/dli-nano-ai:v2.0.2-r32.6.1
```

| Flag | Ý nghĩa |
|---|---|
| `--runtime nvidia` | Dùng NVIDIA Container Runtime → container truy cập được GPU (xem mục 1.4) |
| `-it` | Interactive + TTY (terminal tương tác) |
| `--rm` | Tự xóa container khi thoát (không lưu thay đổi bên trong) |
| `--network host` | Dùng chung network với Jetson → JupyterLab truy cập được qua IP Jetson |
| `--volume ~/nvdli-data:/nvdli-nano/data` | Mount thư mục host vào container → data tồn tại sau khi container bị xóa |
| `--device /dev/video0` | Truyền USB camera vào container |
| `nvcr.io/nvidia/dli/dli-nano-ai:v2.0.2-r32.6.1` | Docker image từ NVIDIA NGC Registry, phiên bản cho L4T R32.6.1 |

##### Luồng hoạt động khi chạy `--runtime nvidia`:

```
docker run --runtime nvidia ...
       │
       ▼
┌──────────────────────────┐
│ Docker Engine             │
│ Chọn runtime: "nvidia"   │
│ (thay vì "runc" mặc định)│
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ nvidia-container-toolkit (1.0.1-1)   │
│ Hook: nvidia-container-runtime-hook  │
│                                      │
│ Tự động inject vào container:        │
│  • /dev/nvidia0 (GPU device)         │
│  • libcuda.so (CUDA driver)          │
│  • libnvidia-*.so (GPU libraries)    │
│  • nvidia-smi (GPU monitor)          │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ DLI Container (đang chạy)            │
│                                      │
│  JupyterLab :8888                    │
│  TensorFlow / PyTorch (GPU-enabled)  │
│  CUDA 10.2 + cuDNN 8.2.1            │
│  Pre-trained models                  │
│  Camera access (/dev/video0)         │
│  ~/nvdli-data ← mounted from host   │
└──────────────────────────────────────┘
```

##### Cách sử dụng:
1. Chạy: `bash docker_dli_run.sh`
2. Mở trình duyệt: `http://192.168.55.1:8888` (qua USB) hoặc `http://<IP_WiFi>:8888`
3. Nhập password (hiện trong terminal khi container khởi động)
4. Thực hành trên JupyterLab với các notebook có sẵn

##### Các khóa học DLI cho Jetson Nano:
- **Getting Started with AI on Jetson Nano** — image classification, regression, object detection
- **Building Video AI Applications at the Edge** — video analytics, DeepStream pipeline

#### nvdli-data/ — NVIDIA DLI Persistent Data

Thư mục **persistent storage** cho Docker container DLI. Cơ chế hoạt động:

```
Container (tạm thời, --rm)          Host (vĩnh viễn)
┌─────────────────────┐              ┌──────────────┐
│ /nvdli-nano/data/   │ ◄──mount──► │ ~/nvdli-data/ │
│   notebooks/        │              │   notebooks/  │
│   models/           │              │   models/     │
│   datasets/         │              │   datasets/   │
└─────────────────────┘              └──────────────┘
     Bị xóa khi thoát                 Vẫn còn mãi
```

- Khi container bị xóa (`--rm`), mọi thay đổi bên trong mất hết
- Nhưng dữ liệu trong `/nvdli-nano/data/` được mount từ `~/nvdli-data/` nên vẫn tồn tại
- Notebooks đã sửa, models đã train, datasets đã tải đều được giữ lại

#### nomachine_9.3.7_1_arm64.deb — NoMachine Remote Desktop
- Package `.deb` cài đặt **NoMachine** — phần mềm remote desktop hiệu năng cao
- Phiên bản 9.3.7, kiến trúc ARM64 (phù hợp Jetson Nano)
- NoMachine sử dụng giao thức NX, nhanh hơn VNC đáng kể
- Cài đặt: `sudo dpkg -i nomachine_9.3.7_1_arm64.deb`

#### KHOA_PBL5_TRAFFIC/ — Dự án Traffic Monitoring
Thư mục dự án PBL5 (Project-Based Learning 5) về giám sát giao thông, liên quan trực tiếp đến workspace `Final.yolov8` hiện tại.

### 3.2 Thư mục Documents/ — C++ Inference Repos & Models

```
~/Documents/
├── YOLOv8-TensorRT/     # triple-Mu/YOLOv8-TensorRT (repo Trung Quốc)
├── infer/                # TensorRT C++ inference framework (repo Trung Quốc)
├── models/               # TensorRT engines đã build
├── baselines/
├── *.onnx, *.engine      # ONNX models và TensorRT engines
└── *.py                  # Python test scripts
```

#### YOLOv8-TensorRT (triple-Mu)
- **Repo:** https://github.com/triple-mu/YOLOv8-TensorRT.git
- **Chức năng:** YOLOv8 inference bằng TensorRT, hỗ trợ cả Python và C++
- **C++ source:** `csrc/` chứa code cho detect, segment, pose, obb, cls
- **Đặc biệt:** Có `csrc/deepstream/` và `csrc/jetson/`
- **csrc/deepstream/** — Plugin DeepStream cho YOLOv8:
  - Build bằng CMake → `libnvdsinfer_custom_bbox_yoloV8.so`
  - Cần cấu hình: `config_yoloV8.txt` (model) + `deepstream_app_config.txt` (pipeline)
  - Output blob names: `num_dets;bboxes;scores;labels`
  - Có thể dùng trực tiếp engine đã build sẵn (`yolov8n_fp16.engine`)
  - Ref: https://github.com/triple-mu/YOLOv8-TensorRT/blob/main/csrc/deepstream/README.md
- **csrc/jetson/** — Code tối ưu cho Jetson (Tegra X1)

#### infer/ — TensorRT C++ Inference Framework
- **Loại:** Custom TensorRT C++ framework (phong cách shouxieai/tensorRT_Pro)
- **Hỗ trợ:** YOLO 3/4/5/x/7/8 + YoloV8-Segment
- **Tính năng:**
  - `cpm.hpp` — Producer-consumer model, tự động multi-batch inference
  - `infer.cu` — TensorRT wrapper bằng CUDA
  - `yolo.cu` — YOLO pre/post-processing trên GPU (~1ms pre, ~0.5ms post)
  - `bt_byte_tracker.*` — ByteTrack tích hợp sẵn (multi-object tracking)
- **Build:** Makefile link tới OpenCV C++ system (`/usr/lib/aarch64-linux-gnu/`) + TensorRT + CUDA
- **Binary:** `main` (đã compile), có benchmark results

#### Models đã build sẵn

| File | Mô tả |
|---|---|
| `models/yolov8n_fp16.engine` | YOLOv8n FP16 TensorRT engine |
| `models/yolo26n_fp16.engine` | YOLO26n (v11-nano?) FP16 engine |
| `models/best_v8n_pruned.engine` | YOLOv8n pruned TensorRT engine |
| `yolov8n_static_fp16.engine` | YOLOv8n static shape FP16 |
| `yolov8n.transd.engine` | YOLOv8n transpose-optimized engine |
| `yolov8n.transd.onnx` | ONNX trước khi build engine |
| `yolov8n.onnx` | YOLOv8n ONNX gốc |
| `yolo26n.onnx` / `yolo26n.pt` | YOLO26n model gốc |
| `best.onnx` | Custom trained model (best checkpoint) |

#### Các thư mục chuẩn Linux
| Thư mục | Mô tả |
|---|---|
| `Desktop/` | Shortcut hiện trên desktop GUI |
| `Documents/` | Tài liệu cá nhân |
| `Downloads/` | File tải về |
| `Music/`, `Pictures/`, `Videos/` | Media files |
| `Public/` | File chia sẻ công khai |
| `Templates/` | Template cho file mới |

---

## 4. Các phương thức kết nối Jetson Nano

| Phương thức | Giao thức | Từ Windows | Cách dùng |
|---|---|---|---|
| **USB Ethernet** | SSH/SFTP | PuTTY → `192.168.55.1` | Nhanh nhất, chỉ cần cáp USB |
| **USB Serial** | UART | PuTTY COM port | Khi network không hoạt động |
| **WiFi SSH** | SSH | PuTTY → IP WiFi | Không cần dây, linh hoạt |
| **VNC (Vino)** | VNC | RealVNC Viewer | GUI đầy đủ, chậm hơn |
| **NoMachine** | NX | NoMachine Client | GUI nhanh, khuyên dùng |
| **USB Mass Storage** | USB MSC | Windows Explorer (ổ E:\) | Read-only, chỉ xem tài liệu |

---

## 5. Thông tin kỹ thuật bổ sung

### 5.1 Software Stack Diagram

```
┌─────────────────────────────────────────────────────┐
│                   User Applications                  │
│        (PBL5 Traffic, DLI Notebooks, YOLOv8)        │
├──────────┬──────────┬───────────┬───────────────────┤
│ Python   │ OpenCV   │ jtop      │ Docker + NVIDIA   │
│ 3.8.10   │ 4.13.0   │ 4.3.2    │ Container Runtime │
├──────────┴──────────┴───────────┴───────────────────┤
│              AI / Deep Learning Frameworks            │
│     PyTorch 1.13.0a0 │  TensorRT 8.0.1 │ (no TF)    │
├─────────────────────┴───────────┴───────────────────┤
│                   cuDNN 8.2.1                        │
├─────────────────────────────────────────────────────┤
│                   CUDA 10.2.300                      │
├─────────────────────────────────────────────────────┤
│           L4T R32.6.1 (Linux for Tegra)              │
│           JetPack 4.6 (nvidia-jetpack 4.6-b199)     │
├─────────────────────────────────────────────────────┤
│          Ubuntu 20.04.6 LTS (aarch64, custom)        │
├─────────────────────────────────────────────────────┤
│       Jetson Nano (NVIDIA Tegra X1 / t210ref)        │
│       128 CUDA Cores │ 4GB LPDDR4 │ ARM Cortex-A57   │
└─────────────────────────────────────────────────────┘
```

### 5.2 Mối quan hệ giữa L4T, JetPack và CUDA

| Tầng | Package | Version | Vai trò |
|---|---|---|---|
| **JetPack** | nvidia-jetpack | 4.6-b199 | Meta-package, kéo mọi thứ bên dưới |
| **L4T** | nvidia-l4t-core | 32.6.1 | Kernel + Tegra drivers + boot firmware |
| **CUDA Toolkit** | cuda-toolkit-10-2 | 10.2.300 | GPU compiler (nvcc) + runtime + math libs |
| **cuDNN** | libcudnn8 | 8.2.1 | Convolution, pooling, normalization primitives cho GPU |
| **TensorRT** | libnvinfer8 | 8.0.1 | Tối ưu model → FP16/INT8, layer fusion, inference engine |
| **OpenCV (Python)** | cv2 pip | 4.13.0 | CPU-only (CUDA: NO, GStreamer: NO) |
| **OpenCV (C++)** | system libs | 4.8.x (Qengineering) | **CUDA: YES** — đầy đủ 12 CUDA modules |

> **Lưu ý OpenCV:** Hệ thống có 5 bản OpenCV C++ tại `/usr/lib/aarch64-linux-gnu/` (4.1, 4.2, 4.5, 4.6, 4.8) — các bản 4.5/4.6/4.8 (Qengineering build) **có đầy đủ CUDA modules** (`cudaimgproc`, `cudacodec`, `cudaarithm`...). Tuy nhiên, Python `import cv2` load bản **pip 4.13.0** (`~/.local/`) — bản này KHÔNG có CUDA/GStreamer. C++ code (infer/, YOLOv8-TensorRT) link đúng bản system có CUDA. Xem chi tiết tại `jetson_nano_issues.md` Issue #3.

### 5.3 L4T Core Package Dependencies
```
nvidia-l4t-core (32.6.1) phụ thuộc:
├── libc6        (C standard library)
├── libegl1      (EGL graphics interface)
├── libexpat1    (XML parser)
├── libgcc1      (GCC runtime)
└── libstdc++6   (C++ standard library)
```

### 5.4 Plugin Manager - Cách hoạt động
1. Khi boot, Plugin Manager đọc EEPROM trên I2C bus `i2c@7000c500`
2. Nhận diện board qua ID (3448 = SoM, 3449 = Carrier)
3. Kiểm tra các cờ trong `odm-data/` (file tồn tại = bật)
4. Áp dụng Device Tree Overlay phù hợp cho phần cứng cụ thể
5. Cho phép cùng 1 firmware chạy trên nhiều cấu hình board khác nhau

### 5.5 USB Device Mode - Service Management
```bash
# Xem trạng thái
sudo systemctl status nv-l4t-usb-device-mode

# Tắt tạm thời
sudo service nv-l4t-usb-device-mode stop

# Tắt vĩnh viễn
sudo systemctl disable nv-l4t-usb-device-mode.service

# Bật lại
sudo systemctl enable /opt/nvidia/l4t-usb-device-mode/nv-l4t-usb-device-mode.service
sudo service nv-l4t-usb-device-mode start
```

### 5.6 Các lệnh kiểm tra hệ thống hữu ích

```bash
# OS version
lsb_release -a

# Phiên bản JetPack
sudo apt-cache show nvidia-jetpack

# Phiên bản L4T
cat /etc/nv_tegra_release

# CUDA version
nvcc --version

# cuDNN version
cat /usr/include/cudnn_version.h | grep CUDNN_MAJOR -A 2

# TensorRT version
dpkg -l | grep nvinfer

# OpenCV version
python3 -c "import cv2; print(cv2.__version__)"

# Docker runtimes
sudo docker info | grep -i runtime

# NVIDIA container toolkit
dpkg -l | grep nvidia-container-toolkit

# System monitor (GPU, CPU, RAM, temp)
jtop
```
