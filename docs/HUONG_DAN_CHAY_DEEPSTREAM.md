# 🚀 Hướng dẫn chạy DeepStream RTSP Pipeline

> **Dự án**: Phát hiện phương tiện giao thông (bus, car, motor, truck) trên Jetson Nano  
> **Pipeline**: Laptop phát video → Jetson AI xử lý → Laptop nhận kết quả + ghi MP4  
> **Cập nhật**: 14/04/2026 (đã test thành công)

---

## 📋 Mục lục

1. [Tổng quan kiến trúc](#1-tổng-quan-kiến-trúc)
2. [Yêu cầu phần cứng & phần mềm](#2-yêu-cầu-phần-cứng--phần-mềm)
3. [Xác định IP (BẮT BUỘC đọc trước)](#3-xác-định-ip-bắt-buộc-đọc-trước)
4. [Chuẩn bị 1 lần](#4-chuẩn-bị-1-lần)
5. [Chạy Pipeline — 4 Terminal](#5-chạy-pipeline--4-terminal)
6. [Xem kết quả](#6-xem-kết-quả)
7. [Tính năng nâng cao (v3)](#7-tính-năng-nâng-cao-v3)
8. [Tùy chỉnh hiệu năng](#8-tùy-chỉnh-hiệu-năng)
9. [Xử lý sự cố](#9-xử-lý-sự-cố)
10. [Cấu trúc thư mục](#10-cấu-trúc-thư-mục)

---

## 1. Tổng quan kiến trúc

```
┌───────────────────────────────────────────────────────────┐
│  LAPTOP (Windows) — IP: <LAPTOP_IP>                       │
│                                                           │
│  [Terminal 1] MediaMTX         ← RTSP Server port 8554    │
│  [Terminal 2] FFmpeg Push      ← Phát video nguồn (TCP)   │
│  [Terminal 4] FFmpeg Record    ← Ghi kết quả AI (TCP)     │
└──────────────────────┬────────────────────────────────────┘
                       │  LAN / Wi-Fi (cùng mạng)
                       ▼
┌───────────────────────────────────────────────────────────┐
│  JETSON NANO (Docker) — IP: <JETSON_IP>                   │
│                                                           │
│  [Terminal 3] DeepStream Pipeline                         │
│    RTSP In → Decode → YOLOv8n FP16 → IOU Tracker         │
│    → OSD (bbox) → Encode → RTSP Out port 8555             │
└───────────────────────────────────────────────────────────┘
```

---

## 2. Yêu cầu phần cứng & phần mềm

### Jetson Nano

| Mục | Yêu cầu |
|-----|--------|
| Board | Jetson Nano 4GB (B01) |
| OS | Ubuntu 20.04 ([Q-Engineering image](https://github.com/Qengineering/Jetson-Nano-Ubuntu-20-image)) |
| Nguồn | **5V-4A Barrel Jack** + jumper J48 (BẮT BUỘC) |
| Tản nhiệt | Quạt 5V hoặc heatsink lớn |
| Docker | `nvcr.io/nvidia/deepstream-l4t:6.0.1-samples` |

### Laptop (Windows)

| Mục | Yêu cầu |
|-----|--------|
| OS | Windows 10/11 |
| FFmpeg | [gyan.dev/ffmpeg](https://www.gyan.dev/ffmpeg/builds/) — tải bản essentials, thêm vào PATH |
| MediaMTX | Đã có tại `rstp/mediamtx_v1.17.1_windows_amd64/` |

---

## 3. Xác định IP (BẮT BUỘC đọc trước)

> ⚠️ **Đây là bước quan trọng nhất!** Sai IP = pipeline không chạy.

### Bước 1: Tìm IP Laptop

Trên Laptop PowerShell:
```powershell
ipconfig | findstr "IPv4"
```

Ví dụ output:
```
IPv4 Address. . . : 192.168.1.154    ← IP LAN (dùng cái này)
IPv4 Address. . . : 192.168.55.100   ← IP USB RNDIS
```

**Chọn IP LAN** (thường dạng `192.168.1.xxx` hoặc `192.168.0.xxx`).

### Bước 2: Tìm IP Jetson

Trên Jetson terminal:
```bash
hostname -I
```

Ví dụ: `192.168.1.10` ← IP LAN của Jetson.

### Bước 3: Test kết nối

Từ Jetson, ping Laptop:
```bash
ping -c 3 <LAPTOP_IP>
# Ví dụ: ping -c 3 192.168.1.154
# → Phải hiện "0% packet loss"
```

Nếu **100% packet loss** → tắt Windows Firewall tạm (PowerShell Admin):
```powershell
Set-NetFirewallProfile -Profile Private,Public -Enabled False
```

### Bước 4: Ghi nhớ 2 IP

Trong toàn bộ hướng dẫn bên dưới, thay:
- **`<LAPTOP_IP>`** = IP LAN của Laptop (vd: `192.168.1.154`)
- **`<JETSON_IP>`** = IP LAN của Jetson (vd: `192.168.1.10`)

---

## 4. Chuẩn bị 1 lần

> Phần này chỉ cần làm **1 lần** khi setup lần đầu.

### 4.1 Jetson — Tối ưu hệ thống

```bash
sudo nvpmodel -m 0 && sudo jetson_clocks
sudo sh -c 'echo 255 > /sys/devices/pwm-fan/target_pwm'
```

### 4.2 Jetson — Docker

```bash
sudo tee /etc/docker/daemon.json <<'EOF'
{
    "runtimes": {
        "nvidia": { "path": "nvidia-container-runtime", "runtimeArgs": [] }
    },
    "default-runtime": "nvidia"
}
EOF
sudo systemctl restart docker
sudo docker pull nvcr.io/nvidia/deepstream-l4t:6.0.1-samples
```

### 4.3 Copy files vào Jetson

Trên Jetson:
```bash
mkdir -p ~/deepstream_yolo
```

Trên Laptop PowerShell:
```powershell
scp "d:\datas\Final.yolov8\deepstream\best_deepstream.onnx" jetson@<JETSON_IP>:~/deepstream_yolo/
scp "d:\datas\Final.yolov8\deepstream\labels.txt" jetson@<JETSON_IP>:~/deepstream_yolo/
scp "d:\datas\Final.yolov8\setup_deepstream_jetson.sh" jetson@<JETSON_IP>:~/deepstream_yolo/
```

Kiểm tra:
```bash
ssh jetson@<JETSON_IP> "ls ~/deepstream_yolo/"
# Phải thấy: best_deepstream.onnx  labels.txt  setup_deepstream_jetson.sh
```

### 4.4 Laptop — Firewall

PowerShell Admin:
```powershell
# Mở port RTSP + cho phép ping
netsh advfirewall firewall add rule name="RTSP 8554 IN" dir=in action=allow protocol=TCP localport=8554
netsh advfirewall firewall add rule name="RTSP 8554 UDP IN" dir=in action=allow protocol=UDP localport=8000-8001
netsh advfirewall firewall add rule name="ICMPv4 Allow" protocol=icmpv4:8,any dir=in action=allow
```

> Nếu vẫn bị chặn, tắt tạm firewall: `Set-NetFirewallProfile -Profile Private,Public -Enabled False`

### 4.5 MediaMTX — Config đã sẵn sàng

File `rstp/mediamtx_v1.17.1_windows_amd64/mediamtx.yml` đã được cấu hình:
```yaml
rtspTransports: [udp, tcp]   # Cho phép cả hai protocol
```

---

## 5. Chạy Pipeline — 4 Terminal

> **⚠️ QUAN TRỌNG**: Chạy theo **đúng thứ tự** 1 → 2 → (chờ) → 3 → (chờ) → 4!  
> DeepStream sẽ lỗi 404 nếu FFmpeg Push chưa sẵn sàng.

### ▶️ Terminal 1 — MediaMTX (RTSP Server trên Laptop)

```powershell
cd d:\datas\Final.yolov8\rstp\mediamtx_v1.17.1_windows_amd64
.\mediamtx.exe
```

✅ **Chờ thấy**: `[RTSP] listener opened on :8554`  
🔴 Để cửa sổ này chạy. **KHÔNG TẮT.**

---

### ▶️ Terminal 2 — FFmpeg Push (Phát video → RTSP Server)

Mở PowerShell mới:

```powershell
ffmpeg -re -stream_loop -1 `
  -i "D:\datas\Final.yolov8\datasets\VID_20260404_160133.mp4" `
  -rtsp_transport tcp `
  -c:v libx264 -preset ultrafast -tune zerolatency `
  -vf scale=640:480 `
  -b:v 1M -maxrate 1M -bufsize 2M `
  -an `
  -f rtsp rtsp://localhost:8554/mystream
```

> **Giải thích tham số:**
> | Tham số | Ý nghĩa |
> |---------|---------|
> | `-re` | Phát đúng tốc độ real-time |
> | `-stream_loop -1` | Lặp vô hạn |
> | `-rtsp_transport tcp` | Publish qua TCP (ổn định) |
> | `-preset ultrafast` | Encode nhanh nhất (tránh lag) |
> | `-vf scale=640:480` | Giảm resolution (DeepStream dùng 640x480) |
> | `-b:v 1M` | Bitrate 1Mbps (nhẹ cho mạng) |
> | `-an` | Bỏ audio (DeepStream không cần) |
>
> 💡 Đổi file video: thay path sau `-i` bằng video khác (MP4, H.264).

✅ **Chờ thấy**: `speed=1.0x` hoặc `speed=1.01x`  
⚠️ Nếu `speed < 0.9x` → video quá nặng, cần giảm resolution hoặc bitrate.

✅ **MediaMTX (Terminal 1)** phải hiện: `is publishing to path 'mystream'`

---

### ▶️ Terminal 3 — DeepStream trên Jetson

> ⚠️ **CHỈ CHẠY SAU KHI Terminal 2 hiện `speed=1.0x`!**

SSH vào Jetson, chạy Docker, rồi chạy script:

```bash
# SSH vào Jetson
ssh jetson@<JETSON_IP>

# Chạy Docker container
sudo docker run -it --rm --runtime nvidia --privileged \
    --network host \
    -v ~/deepstream_yolo:/root/deepstream_yolo \
    nvcr.io/nvidia/deepstream-l4t:6.0.1-samples

# Trong container — chạy script (THAY <LAPTOP_IP> bằng IP thật!)
LAPTOP_RTSP_URI=rtsp://<LAPTOP_IP>:8554/mystream \
  bash /root/deepstream_yolo/setup_deepstream_jetson.sh
```

**Ví dụ thực tế:**
```bash
ssh jetson@192.168.1.10
sudo docker run -it --rm --runtime nvidia --privileged --network host -v ~/deepstream_yolo:/root/deepstream_yolo nvcr.io/nvidia/deepstream-l4t:6.0.1-samples
LAPTOP_RTSP_URI=rtsp://192.168.1.154:8554/mystream bash /root/deepstream_yolo/setup_deepstream_jetson.sh
```

> **Lần đầu tiên** sẽ mất 5-15 phút:
> 1. Clone DeepStream-Yolo + compile custom parser (~2 phút)
> 2. Build TensorRT FP16 engine từ ONNX (~10 phút)
>
> **Từ lần thứ 2**: khởi chạy trong ~5 giây (engine đã cache).

✅ **Chờ thấy** FPS > 0:
```
**PERF:  0.00 (0.00)      ← Đang kết nối...
**PERF:  25.00 (25.00)    ← ĐÃ CHẠY! ✅
**PERF:  28.50 (26.75)
```

⚠️ Các warning này là **BÌNH THƯỜNG**, bỏ qua:
```
(Argus) Error FileOperationFailed: Connecting to nvargus-daemon failed
Failed to load plugin libnvdsgst_inferserver.so
Failed to load plugin libnvdsgst_udp.so
```

---

### ▶️ Terminal 4 — FFmpeg Record (Ghi kết quả AI)

> ⚠️ **CHỈ CHẠY SAU KHI Terminal 3 hiện `PERF > 0`!**

Mở PowerShell mới trên Laptop:

```powershell
ffmpeg -rtsp_transport tcp `
  -i "rtsp://<JETSON_IP>:8555/ds-test" `
  -c copy `
  "D:\datas\Final.yolov8\deepstream\output_ai_result.mp4"
```

**Ví dụ thực tế:**
```powershell
ffmpeg -rtsp_transport tcp -i "rtsp://192.168.1.10:8555/ds-test" -c copy "D:\datas\Final.yolov8\deepstream\output_ai_result.mp4"
```

> **Quan trọng**: `-rtsp_transport tcp` phải viết **TRƯỚC** `-i`!

**Dừng ghi**: Nhấn `q` khi muốn dừng.

---

## 6. Xem kết quả

### Video output

```
D:\datas\Final.yolov8\deepstream\output_ai_result.mp4
```

Mở bằng VLC hoặc Media Player — video có bounding box AI quanh phương tiện.

### Xem real-time (không cần ghi file)

```powershell
ffplay -rtsp_transport tcp "rtsp://<JETSON_IP>:8555/ds-test"
```

Hoặc VLC: `Media → Open Network Stream → rtsp://<JETSON_IP>:8555/ds-test`

### Monitor Jetson (terminal SSH thêm)

```bash
sudo tegrastats
```

| Chỉ số | Tốt | Cảnh báo |
|--------|-----|----------|
| GR3D_FREQ | < 80% | > 95% → GPU nghẽn |
| CPU | < 50% | > 80% → CPU nghẽn |
| RAM | < 3000MB | > 3500MB → sắp hết |
| GPU temp | < 60°C | > 80°C → quá nóng |

---

## 7. Tính năng nâng cao (v3)

Script v3 bao gồm 3 tính năng demo nâng cao, tất cả **bật mặc định**:

### 🎨 7.1 Bbox màu theo class

Mỗi loại phương tiện có màu riêng — dễ phân biệt trong video:

| Class | Màu | Ghi chú |
|-------|------|---------|
| `bus` (0) | 🟢 Xanh lá | Threshold 0.25 |
| `car` (1) | 🔵 Xanh dương | Threshold 0.25 |
| `motor` (2) | 🟡 Vàng | Threshold **0.20** (thấp hơn vì xe nhỏ) |
| `truck` (3) | 🔴 Đỏ | Threshold 0.25 |

> Không cần cấu hình gì — tự động theo script v3.

### 🔄 7.2 NvDCF Tracker (thay IOU)

| | IOU (cũ) | NvDCF (mặc định v3) |
|---|---|---|
| **Track khi bị che** | ❌ Mất ID luôn | ✅ Giữ ID qua occlusion |
| **Chạy trên** | CPU | GPU |
| **Chính xác** | Thấp | Cao |
| **FPS** | ~30 | ~22-28 |

Đổi tracker:
```bash
# Mặc định v3: NvDCF
LAPTOP_RTSP_URI=rtsp://<LAPTOP_IP>:8554/mystream \
  bash /root/deepstream_yolo/setup_deepstream_jetson.sh

# Quay lại IOU nếu cần FPS cao hơn
TRACKER_TYPE=iou LAPTOP_RTSP_URI=rtsp://<LAPTOP_IP>:8554/mystream \
  bash /root/deepstream_yolo/setup_deepstream_jetson.sh
```

### 📊 7.3 Đếm xe — Line Crossing Counter

Một vạch đếm ảo được vẽ trên video. Mỗi xe đi qua vạch → bộ đếm +1.

```
    ┌──────────────────────────────┐
    │                              │
    │     🚗        🏍️             │
    │ ═══════ VẠCH ĐẾM ══════════ │  ← Mặc định: 60% chiều cao
    │              🚛              │
    │                              │
    └──────────────────────────────┘
```

**Tùy chỉnh vị trí vạch đếm:**
```bash
# Mặc định: ngang ở 60% chiều cao, từ 10% đến 90% chiều rộng
LAPTOP_RTSP_URI=rtsp://<LAPTOP_IP>:8554/mystream \
  bash /root/deepstream_yolo/setup_deepstream_jetson.sh

# Đổi vạch lên 40% chiều cao (gần hơn phía trên video)
LC_Y1=288 LC_Y2=288 LAPTOP_RTSP_URI=rtsp://<LAPTOP_IP>:8554/mystream \
  bash /root/deepstream_yolo/setup_deepstream_jetson.sh

# Tắt đếm xe
ENABLE_ANALYTICS=0 LAPTOP_RTSP_URI=rtsp://<LAPTOP_IP>:8554/mystream \
  bash /root/deepstream_yolo/setup_deepstream_jetson.sh
```

> 💡 Tọa độ vạch tính theo pixel của streammux (mặc định 1280×720).
> Vạch mặc định: `(128, 432) → (1152, 432)` — ngang ở 60% chiều cao.

---

## 8. Tùy chỉnh hiệu năng

Override bằng biến môi trường khi chạy script trong container:

### Preset: Demo chất lượng cao (mặc định v3)

```bash
# NvDCF tracker + analytics + 720p + 4Mbps → ~22-28 FPS
LAPTOP_RTSP_URI=rtsp://<LAPTOP_IP>:8554/mystream \
  bash /root/deepstream_yolo/setup_deepstream_jetson.sh
```

### Preset: FPS tối đa

```bash
# IOU tracker + no analytics + interval=2 → ~30 FPS
TRACKER_TYPE=iou ENABLE_ANALYTICS=0 \
LAPTOP_RTSP_URI=rtsp://<LAPTOP_IP>:8554/mystream \
  bash /root/deepstream_yolo/setup_deepstream_jetson.sh
```

### Preset: Chính xác tối đa

```bash
# NvDCF + interval=0 + low threshold → ~12-16 FPS
INFER_INTERVAL=0 PRE_CLUSTER_THRESHOLD=0.10 \
LAPTOP_RTSP_URI=rtsp://<LAPTOP_IP>:8554/mystream \
  bash /root/deepstream_yolo/setup_deepstream_jetson.sh
```

### Preset: Full HD demo

```bash
# 1080p + 6Mbps + NvDCF → ~15-20 FPS (rất sắc nét)
STREAMMUX_WIDTH=1920 STREAMMUX_HEIGHT=1080 OUTPUT_BITRATE=6000000 \
LAPTOP_RTSP_URI=rtsp://<LAPTOP_IP>:8554/mystream \
  bash /root/deepstream_yolo/setup_deepstream_jetson.sh
```

> ⚠️ FFmpeg Push phải scale tương ứng: `-vf scale=1920:1080 -b:v 5M`

### Bảng tham số đầy đủ

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| **Inference** | | |
| `INFER_INTERVAL` | `2` | Skip N frame giữa 2 lần AI (0=mọi frame) |
| `PRE_CLUSTER_THRESHOLD` | `0.25` | Ngưỡng confidence tối thiểu |
| `NMS_IOU_THRESHOLD` | `0.45` | Ngưỡng NMS loại box trùng |
| **Video** | | |
| `STREAMMUX_WIDTH` | `1280` | Chiều rộng video pipeline |
| `STREAMMUX_HEIGHT` | `720` | Chiều cao video pipeline |
| `OUTPUT_BITRATE` | `4000000` | Bitrate output (4Mbps) |
| **Tracker** | | |
| `TRACKER_TYPE` | `nvdcf` | `nvdcf` (chính xác) hoặc `iou` (nhanh) |
| **Analytics** | | |
| `ENABLE_ANALYTICS` | `1` | `0` = tắt line crossing counter |
| `LC_X1`, `LC_Y1` | auto | Tọa độ điểm đầu vạch đếm |
| `LC_X2`, `LC_Y2` | auto | Tọa độ điểm cuối vạch đếm |
| **Khác** | | |
| `JETSON_RTSP_PORT` | `8555` | Port output RTSP |
| `SKIP_SOURCE_CHECK` | `0` | `1` = bỏ qua ffprobe check |
| `RUN_PIPELINE` | `1` | `0` = chỉ tạo config |

---

## 9. Xử lý sự cố

### ❌ `Failed to connect (Generic error)` / FPS = 0

**Nguyên nhân**: Jetson không kết nối được RTSP source trên Laptop.

**Checklist:**
1. FFmpeg Push (Terminal 2) còn đang chạy? Phải hiện `speed≈1.0x`
2. MediaMTX (Terminal 1) hiện `is publishing to path 'mystream'`?
3. Từ Jetson container: `ping -c 3 <LAPTOP_IP>` → phải `0% loss`
4. Nếu ping fail → tắt Windows Firewall: `Set-NetFirewallProfile -Profile Private,Public -Enabled False`
5. IP có đúng không? Kiểm tra lại bằng `ipconfig` và `hostname -I`

> **Lỗi phổ biến nhất**: Chạy DeepStream TRƯỚC khi FFmpeg Push sẵn sàng → lỗi 404.

### ❌ `Not Found (404)` / `no stream is available`

**Nguyên nhân**: FFmpeg Push chưa publish hoặc đã crash.

**Fix**: Restart FFmpeg Push (Terminal 2), chờ `speed=1.0x`, rồi restart DeepStream.

### ❌ `461 Unsupported Transport`

**Nguyên nhân**: MediaMTX config chỉ cho TCP nhưng client dùng UDP.

**Fix**: Kiểm tra `mediamtx.yml` phải có `rtspTransports: [udp, tcp]`

### ❌ `RTP packets lost` / `invalid FU-A packet`

**Nguyên nhân**: Video bitrate quá cao cho mạng.

**Fix**:
1. FFmpeg Push phải dùng `-preset ultrafast -vf scale=640:480 -b:v 1M`
2. Dùng dây LAN thay Wi-Fi
3. FFmpeg Record phải dùng `-rtsp_transport tcp`

### ❌ `speed=0.5x` (FFmpeg Push quá chậm)

**Nguyên nhân**: CPU Laptop encode 1080p không kịp.

**Fix**: Thêm `-vf scale=640:480` và `-preset ultrafast` vào lệnh FFmpeg Push.

### ❌ `Missing ONNX file`

**Nguyên nhân**: Docker mount sai hoặc chưa copy files.

**Fix**:
- Docker mount phải là: `-v ~/deepstream_yolo:/root/deepstream_yolo`
- Kiểm tra files: `ls /root/deepstream_yolo/` trong container

### ❌ FPS thấp (< 15)

Chạy `sudo tegrastats`:

| Nếu | Fix |
|-----|-----|
| GR3D > 95% | Tăng `INFER_INTERVAL=2` hoặc `3` |
| CPU > 80% | Giảm tracker resolution |
| RAM > 3500MB | Giảm streammux resolution |

### ❌ DeepStream crash / engine lỗi

```bash
# Trong container — xóa engine cũ, build lại
rm -f /root/deepstream_yolo/*.engine
# Chạy lại script
```

---

## 10. Cấu trúc thư mục

### Trên Laptop

```
d:\datas\Final.yolov8\
├── deepstream\
│   ├── best_deepstream.onnx      ← Model ONNX (copy sang Jetson)
│   ├── labels.txt                ← Nhãn: bus, car, motor, truck
│   └── output_ai_result.mp4     ← Video kết quả (sau khi ghi)
├── datasets\
│   └── VID_*.mp4                 ← Video test nguồn
├── rstp\
│   └── mediamtx_v1.17.1_windows_amd64\
│       ├── mediamtx.exe          ← RTSP Server
│       └── mediamtx.yml          ← Config (đã sửa: udp+tcp)
├── setup_deepstream_jetson.sh    ← Script chính (copy sang Jetson)
└── docs\
    └── HUONG_DAN_CHAY_DEEPSTREAM.md  ← File này
```

### Trên Jetson (trong Docker container)

```
~/deepstream_yolo/                    ← Mount vào /root/deepstream_yolo
├── best_deepstream.onnx              ← Model ONNX
├── best_deepstream.onnx_b1_gpu0_fp16.engine  ← TensorRT (tự build lần đầu)
├── labels.txt                        ← Nhãn
├── libnvdsinfer_custom_impl_Yolo.so  ← Parser (tự build lần đầu)
├── config_infer_primary_yolov8.txt   ← Config inference (tự tạo)
├── deepstream_app_yolov8_rtsp.txt    ← Config pipeline (tự tạo)
└── setup_deepstream_jetson.sh        ← Script chính
```

---

## 📎 Copy & Paste nhanh

> Thay `192.168.1.154` và `192.168.1.10` bằng IP thật của bạn.

**Terminal 1 — MediaMTX:**
```powershell
cd d:\datas\Final.yolov8\rstp\mediamtx_v1.17.1_windows_amd64; .\mediamtx.exe
```

**Terminal 2 — FFmpeg Push (chờ MediaMTX ready):**
```powershell
ffmpeg -re -stream_loop -1 -i "D:\datas\Final.yolov8\datasets\VID_20260404_160133.mp4" -rtsp_transport tcp -c:v libx264 -preset ultrafast -tune zerolatency -vf scale=640:480 -b:v 1M -maxrate 1M -bufsize 2M -an -f rtsp rtsp://localhost:8554/mystream
```

**Terminal 3 — DeepStream (chờ FFmpeg hiện speed=1.0x):**
```bash
ssh jetson@192.168.1.10
sudo docker run -it --rm --runtime nvidia --privileged --network host -v ~/deepstream_yolo:/root/deepstream_yolo nvcr.io/nvidia/deepstream-l4t:6.0.1-samples
LAPTOP_RTSP_URI=rtsp://192.168.1.154:8554/mystream bash /root/deepstream_yolo/setup_deepstream_jetson.sh
```

**Terminal 4 — Record (chờ DeepStream hiện PERF > 0):**
```powershell
ffmpeg -rtsp_transport tcp -i "rtsp://192.168.1.10:8555/ds-test" -c copy "D:\datas\Final.yolov8\deepstream\output_ai_result.mp4"
```

---

> **Lưu ý**: Lần đầu TensorRT cần 5-15 phút build engine. Từ lần 2 trở đi chỉ ~5 giây.
