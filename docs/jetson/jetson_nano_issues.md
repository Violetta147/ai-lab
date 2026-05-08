# Jetson Nano — Các vấn đề phát hiện (ĐÃ XÁC NHẬN)

## Môi trường Python

### Issue #1: Ba tầng Python — pip/wheel ở 2 tầng khác nhau (XÁC NHẬN)

**Kết quả kiểm tra:**

```
pip3 show pip   → Location: /home/jetson/.local/lib/python3.8/site-packages  (tầng 2: user-local)
pip3 show wheel → Location: /usr/lib/python3/dist-packages                   (tầng 1: system apt)
```

Xác nhận pip 25.0.1 và wheel 0.34.2 nằm ở 2 tầng khác nhau, **không phải mismatch thật sự**.

**Hệ thống có 2 tầng hoạt động (không phải 3):**

```
Tầng 1: System (apt)
  Path: /usr/lib/python3/dist-packages/
  Chứa: wheel 0.34.2, tensorflow, tensorboard, astunparse...
  Quản lý bởi: sudo apt install python3-xxx

Tầng 2: User-local (pip --user)
  Path: /home/jetson/.local/lib/python3.8/site-packages/
  Chứa: pip 25.0.1, và các package cài bằng pip3 install
  Quản lý bởi: pip3 install xxx (không sudo, không venv)
```

**Python lookup order (khi KHÔNG trong venv):**
```
python3 import → tìm theo thứ tự:
  1. ~/.local/lib/python3.8/site-packages/   (user-local, ưu tiên cao nhất)
  2. /usr/local/lib/python3.8/dist-packages/
  3. /usr/lib/python3/dist-packages/          (system, ưu tiên thấp nhất)
```

**Mức độ:** Thấp — hoạt động bình thường, chỉ cần biết pip ở `~/.local/` và wheel ở system.

### Issue #2: .venv bị hỏng — không có pip (XÁC NHẬN)

**Kết quả kiểm tra:**

```bash
.venv/bin/pip → "No such file or directory"    # KHÔNG CÓ PIP
.venv/bin/python3 --version → Python 3.8.10    # Python có

cat .venv/pyvenv.cfg:
  home = /usr/bin
  include-system-site-packages = false          # KHÔNG kế thừa system packages
  version = 3.8.10

sys.path trong venv:
  /home/jetson/.venv/lib/python3.8/site-packages   # venv riêng
  /usr/lib/python3.8                                # stdlib only
  # KHÔNG có ~/.local/ → không thấy pip, torch, cv2...
```

**Vấn đề:**
- `.venv` được tạo bằng `python3 -m venv .venv` (không có `--system-site-packages`)
- `include-system-site-packages = false` → venv **cô lập hoàn toàn**
- Không có pip bên trong → **không thể cài package nào vào venv**
- Venv không thấy PyTorch, OpenCV, TensorRT... từ system
- → Venv này về cơ bản **vô dụng** trong trạng thái hiện tại

**Cách fix (chọn 1 trong 2):**

```bash
# Option A: Xóa và tạo lại với system site-packages (KHUYÊN DÙNG cho Jetson)
rm -rf ~/.venv
python3 -m venv ~/.venv --system-site-packages
# → venv sẽ thấy torch, cv2, tensorrt từ system
# → vẫn có thể pip install thêm package riêng

# Option B: Cài pip vào venv hiện tại
.venv/bin/python3 -m ensurepip --upgrade
# → Nhưng venv vẫn không thấy system packages (torch, cv2...)
```

> **Trên Jetson, Option A luôn tốt hơn** vì PyTorch, OpenCV, TensorRT được build đặc biệt cho ARM+CUDA và rất khó cài lại bằng pip.

**Mức độ: Trung bình** — venv không dùng được, nhưng code hiện tại có thể đang chạy trực tiếp bằng system python3.

---

## OpenCV

### Issue #3: OpenCV — CHỈ Python pip thiếu CUDA (ĐÃ SỬA ĐÁNH GIÁ)

**Phát hiện mới:** Hệ thống có **5 phiên bản OpenCV C++**, trong đó 3 bản Qengineering **CÓ ĐẦY ĐỦ CUDA modules**.

#### Toàn cảnh OpenCV trên hệ thống:

```
/usr/lib/aarch64-linux-gnu/ chứa:

Bản 1: JetPack 4.1.1 (NVIDIA build, có CUDA)
  dpkg: libopencv 4.1.1-2-gd5a58aa75
  .so:  libopencv_core.so.4.1

Bản 2: Ubuntu 20.04 apt (KHÔNG có CUDA)
  dpkg: libopencv-dev 4.2.0+dfsg-5
  .so:  libopencv_core.so.4.2

Bản 3: Qengineering build (CÓ CUDA)
  .so:  libopencv_core.so.4.5
        libopencv_cudaarithm.so.4.5, libopencv_cudaimgproc.so.4.5, ...

Bản 4: Qengineering build (CÓ CUDA)
  .so:  libopencv_core.so.406
        libopencv_cudaarithm.so.406, libopencv_cudaimgproc.so.406, ...

Bản 5: Qengineering build (CÓ CUDA)  ← MỚI NHẤT, symlink mặc định
  .so:  libopencv_core.so.408
        libopencv_cudaarithm.so.408, libopencv_cudaimgproc.so.408, ...

Python pip (KHÔNG có CUDA, KHÔNG có GStreamer)
  Version: 4.13.0
  Location: ~/.local/lib/python3.8/site-packages/cv2/
  Chỉ có FFMPEG
```

#### CUDA modules C++ có sẵn (từ ldconfig):

```
libopencv_cudaarithm    — GPU arithmetic operations
libopencv_cudabgsegm    — GPU background segmentation
libopencv_cudacodec     — GPU video encode/decode
libopencv_cudafeatures2d — GPU feature detection
libopencv_cudafilters   — GPU image filters
libopencv_cudaimgproc   — GPU image processing (resize, cvtColor)
libopencv_cudalegacy    — Legacy GPU functions
libopencv_cudaobjdetect — GPU object detection (HOG, cascade)
libopencv_cudaoptflow   — GPU optical flow
libopencv_cudastereo    — GPU stereo matching
libopencv_cudawarping   — GPU geometric transforms
libopencv_cudev         — CUDA device layer
```

#### Vấn đề thực tế:

| Workflow | OpenCV version | CUDA | GStreamer | Trạng thái |
|---|---|---|---|---|
| **C++ inference** (infer/, YOLOv8-TensorRT) | 4.8.x system | **CÓ** | Chưa verify | **OK** |
| **Python** (`import cv2`) | 4.13.0 pip | **KHÔNG** | **KHÔNG** | **Vấn đề** |

**Nguyên nhân Python thiếu CUDA:** `pip install opencv-python` cài bản pre-built từ PyPI, nó tự mang `.so` riêng bên trong `~/.local/`, **hoàn toàn bỏ qua** OpenCV C++ CUDA system. Python và C++ dùng 2 bản OpenCV khác nhau.

#### Cách fix Python OpenCV (chọn 1):

```bash
# Option A: Xóa pip opencv, dùng system binding (KHUYÊN DÙNG)
pip3 uninstall opencv-python opencv-python-headless opencv-contrib-python
# → Python sẽ fallback dùng libopencv-python 4.1.1 (JetPack, có CUDA)
# Verify: python3 -c "import cv2; print(cv2.__version__, cv2.cuda.getCudaEnabledDeviceCount())"

# Option B: Nếu cần OpenCV mới hơn, rebuild Python binding từ system OpenCV
# (phức tạp hơn, chỉ khi Option A không đủ)
```

**Mức độ: TRUNG BÌNH** (hạ từ CAO) — C++ inference path đã có CUDA đầy đủ. Chỉ Python workflow bị ảnh hưởng, và có thể fix dễ dàng bằng cách xóa pip opencv.

---

## Docker

### Issue #4: Default runtime là `runc` — daemon.json thiếu default-runtime (XÁC NHẬN)

**Kết quả kiểm tra:**

```json
// /etc/docker/daemon.json hiện tại:
{
    "runtimes": {
        "nvidia": {
            "path": "nvidia-container-runtime",
            "runtimeArgs": []
        }
    }
    // ← THIẾU "default-runtime": "nvidia"
}
```

nvidia runtime **đã đăng ký**, nhưng **không phải default**. Mỗi lần chạy container cần GPU phải thêm `--runtime nvidia`.

**Cách fix:**

```bash
sudo cp /etc/docker/daemon.json /etc/docker/daemon.json.bak

sudo tee /etc/docker/daemon.json <<'EOF'
{
    "runtimes": {
        "nvidia": {
            "path": "nvidia-container-runtime",
            "runtimeArgs": []
        }
    },
    "default-runtime": "nvidia"
}
EOF

sudo systemctl restart docker
sudo docker info | grep "Default Runtime"
```

**Mức độ: Trung bình** — hoạt động được nếu nhớ `--runtime nvidia`, nhưng dễ quên.

### Issue #5: nvidia-container-toolkit 1.0.1-1 — Phiên bản cũ (KHÔNG CẦN FIX)

Phiên bản hiện tại ngoài thị trường là 1.14+. Bản 1.0.1 là từ 2019. Tuy nhiên đây là phiên bản NVIDIA cung cấp chính thức cho JetPack 4.6 / L4T R32.6.1. **KHÔNG nên upgrade** — bản mới không tương thích với CUDA 10.2 trên Nano.

**Mức độ: Không cần hành động.**

---

---

## Ghi chú: DeepStream Integration Paths

Có 2 phương án tích hợp YOLOv8 + DeepStream:

**Phương án A (User đang thực hiện):** Tự cài DeepStream Docker → cấu hình pipeline bên trong container. Cần build custom parser plugin hoặc dùng DeepStream-Yolo repo.

**Phương án B (Dự phòng):** Dùng `~/Documents/YOLOv8-TensorRT/csrc/deepstream/` — plugin đã viết sẵn cho output format của triple-Mu. Chỉ cần `cmake && make` → có `libnvdsinfer_custom_bbox_yoloV8.so`. Dùng được trực tiếp với engine đã build sẵn (`yolov8n_fp16.engine`).

Xem chi tiết tại DeepStream plan (Phase 4A vs 4B).

---

### Issue #6: Swap trên SD card — BẪY CHẾT (CỰC KỲ QUAN TRỌNG)

**Nguồn:** Lời khuyên thực chiến từ người có kinh nghiệm deploy Jetson Nano.

**Vấn đề:** Jetson Nano 4GB RAM bắt buộc cần swap. Nhưng swap trên SD card = **tử huyệt**:

| Đặc điểm SD card | Giá trị | Hậu quả |
|---|---|---|
| Random write speed | 10-20 MB/s | Cực chậm so với RAM (25 GB/s) |
| Write endurance | ~10,000-100,000 cycles | SD card chết sau vài tuần/tháng chạy liên tục |
| Latency | ~1-10ms | So với RAM ~10ns = chậm 100,000x |

**Khi xảy ra:**
1. RAM đầy (DeepStream + TensorRT + video buffers)
2. Kernel swap data xuống SD card
3. I/O bottleneck → video giật lag nghiêm trọng
4. SD card bị ghi đè liên tục → **chết đột ngột** (không nhận thẻ nữa)

**Giải pháp BẮT BUỘC:**

```bash
# KHÔNG dùng swap trên SD card. Dùng USB SSD/flash drive:
sudo fallocate -l 6G /mnt/usb/swapfile
sudo chmod 600 /mnt/usb/swapfile
sudo mkswap /mnt/usb/swapfile
sudo swapon /mnt/usb/swapfile
echo '/mnt/usb/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Tắt swap trên SD card (nếu có):
sudo swapoff /swapfile   # hoặc path swap hiện tại
```

**Nếu KHÔNG có USB SSD:** Giảm thiểu swap usage:
- Chạy headless (tắt GUI): tiết kiệm ~800MB RAM
- Dùng DeepStream base image (nhẹ nhất)
- Monitor: `free -h` và `tegrastats` liên tục

**Mức độ: CỰC KỲ CAO** — có thể phá hủy SD card vĩnh viễn.

---

### Issue #7: MAXN + jetson_clocks — 2 TỬ HUYỆT PHẦN CỨNG

**Nguồn:** Lời khuyên từ thầy hướng dẫn.

`sudo nvpmodel -m 0` (MAXN) + `sudo jetson_clocks` = ép Jetson chạy 100%+ công suất. **BẮT BUỘC** cho DeepStream nhưng CẦN 2 điều kiện phần cứng:

#### Tử huyệt 1: Nguồn điện

| Cách cấp điện | Dòng tối đa | Đủ cho MAXN? | Hậu quả nếu thiếu |
|---|---|---|---|
| Micro-USB (sạc ĐT) | ~2A | **KHÔNG** | Tắt nguồn đột ngột ("phụp") |
| **Barrel Jack 5V-4A** | 4A | **CÓ** | Ổn định |

**BẮT BUỘC:**
- Mua nguồn **5V-4A** cắm cổng tròn (Barrel Jack)
- **Cắm jumper J48** trên bo mạch để chuyển sang nhận điện từ Barrel Jack
- KHÔNG dùng Micro-USB khi chạy MAXN

#### Tử huyệt 2: Tản nhiệt

| Tản nhiệt | Đủ cho MAXN? | Hậu quả nếu thiếu |
|---|---|---|
| Nhôm thụ động (heat sink) | **KHÔNG** | CPU/GPU thermal throttle → sập |
| **Quạt tản nhiệt (active fan)** | **CÓ** | Ổn định |

**BẮT BUỘC:**
- Gắn quạt tản nhiệt
- Cấu hình quạt quay tốc độ tối đa:
  ```bash
  # Ép quạt quay max (PWM fan control)
  sudo sh -c 'echo 255 > /sys/devices/pwm-fan/target_pwm'
  
  # Để tự động khi boot, thêm vào /etc/rc.local hoặc cron:
  echo 'sh -c "echo 255 > /sys/devices/pwm-fan/target_pwm"' | sudo tee -a /etc/rc.local
  ```

#### Tại sao Qengineering + jetson_clocks = cặp bài trùng?
- Qengineering đã hack kernel nâng **mức trần** xung nhịp (overclock)
- `jetson_clocks` ép hệ thống chạy ở đúng mức trần đó
- Không gõ `jetson_clocks` → máy không bao giờ chạm tới mức overclock → phí bản Qengineering

**Mức độ: CỰC CAO** — thiếu nguồn/quạt khi chạy MAXN có thể sập nguồn hoặc hỏng phần cứng.

---

## Tổng hợp

| # | Issue | Mức độ | Trạng thái | Hành động |
|---|---|---|---|---|
| 1 | pip/wheel ở 2 tầng khác nhau | Thấp | Đã hiểu | Không cần fix |
| 2 | .venv bị hỏng (không pip, cô lập) | Trung bình | Xác nhận | Xóa tạo lại với `--system-site-packages` |
| 3 | OpenCV: Python pip thiếu CUDA (C++ đã có) | Trung bình | Xác nhận | Xóa pip opencv → dùng system binding 4.1.1 |
| 4 | Docker default runtime = runc | ~~Trung bình~~ | **ĐÃ FIX** | ~~Thêm default-runtime nvidia~~ ✅ |
| 5 | nvidia-container-toolkit cũ | Không cần fix | Xác nhận | Giữ nguyên |
| 6 | **Swap trên SD card** | **CỰC CAO** | Xác nhận trên SD | Giảm swappiness=10, headless, monitor |
| 7 | **MAXN cần nguồn 5V-4A + quạt** | **CỰC CAO** | Cần kiểm tra | Barrel Jack + jumper J48 + quạt max |

## Trước khi cài DeepStream — Checklist

- [x] **Issue #4:** Thêm `"default-runtime": "nvidia"` vào daemon.json → **ĐÃ LÀM**
- [x] **Issue #6:** Kiểm tra swap → trên SD card, đã set swappiness=10
- [x] Set headless mode: `sudo systemctl set-default multi-user.target` → **ĐÃ LÀM**
- [ ] **Issue #7:** Kiểm tra nguồn điện: có nguồn 5V-4A Barrel Jack chưa? Jumper J48?
- [ ] **Issue #7:** Kiểm tra quạt: có quạt tản nhiệt chưa? Cấu hình quay max?
- [ ] Set MAXN: `sudo nvpmodel -m 0 && sudo jetson_clocks` (CHỈ SAU KHI có nguồn + quạt)
- [ ] Pull DeepStream: `docker pull nvcr.io/nvidia/deepstream-l4t:6.0.1-samples`
