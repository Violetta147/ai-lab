# Q1 — Phân Tích Kiến Trúc Các Điểm Can Thiệp (Inject Points) Cho Luồng Live

> **Bối Cảnh Kỹ Thuật & Thách Thức Thực Tế**:
> Edge Server chạy trên thiết bị **Jetson Nano 4GB RAM (Không Swap)**, thực hiện nhận diện bằng mô hình **YOLOv8n qua TensorRT FP16 (FPS đỉnh ~25-28 FPS)**.
> Pipeline hiện tại đi qua một luồng duy nhất:
> `YOLO → Bộ lọc Active Learning + OOD → Publish Gate (Cooldown/Trùng phash) → Nén JPEG & Ghi file đệm JSON cục bộ → Tải lên MinIO & MQTT`.
>
> Thiết kế này tối ưu cho **MLOps** (chỉ thu thập ảnh khó để phục vụ re-training) nhưng phát sinh 4 vấn đề lớn:
> 1. **Live Tracking Bị Mất Dấu (ID Nhảy Liên Tục)**: IoU Tracker chạy trên Web Server yêu cầu cập nhật liên tục từ Jetson. Nếu chỉ gửi khi có AL/OOD hit hoặc bị Publish Gate chặn cooldown (ví dụ 6s mới gửi 1 lần), khoảng dịch chuyển của xe giữa 2 lần gửi là quá lớn khiến IoU giữa các khung hình = 0.
>    - *Toán học thực tế (Xe chạy 60 km/h, ảnh 640x640)*: Để bám đuổi với IoU Threshold = 0.3, cần tối thiểu **7 FPS**. Với IoU Threshold = 0.5, cần tối thiểu **12 FPS**.
> 2. **Rủi ro Quá nhiệt (Thermal Throttling)**: Jetson Nano chạy ở chế độ nguồn tối đa 10W (MAXN) và khóa xung nhịp cao nhất. Khi không có quạt tản nhiệt chủ động, nhiệt độ chip vượt 75°C sau 3-5 phút làm sụt giảm xung nhịp CPU/GPU, FPS thực tế tụt từ ~23-28 FPS xuống **dưới 10 FPS**. Do đó cần giải phóng luồng chính khỏi các tác vụ nén JPEG (tốn CPU) và block I/O mạng bằng cơ chế đa luồng bất đồng bộ.
> 3. **Tràn bộ nhớ RAM (OOM Killer)**: Do Jetson chỉ có 4GB RAM vật lý không có Swap. Nếu luồng bất đồng bộ sử dụng hàng đợi quá lớn, khi mất kết nối mạng, hàng đợi sẽ tích lũy ảnh và gây tràn RAM. Cần giới hạn hàng đợi ở mức cực thấp (`maxsize = 10` đến `15`, chiếm <20MB RAM) để đảm bảo an toàn.
> 4. **Lỗi KeyError & Đầy Dung Lượng Đĩa Cục Bộ**: Giao thức lưu đệm file JSON cũ bị KeyError khi đồng bộ lại lúc có mạng. Đồng thời, mất mạng kéo dài có thể gây đầy dung lượng đĩa cục bộ. Cần tối ưu hóa quy trình kiểm soát dữ liệu của buffer file, sửa lỗi logic KeyError, đồng thời bổ sung cơ chế kiểm soát giới hạn dung lượng thư mục đệm cục bộ (Local Disk Safety Limit) để bảo vệ Jetson.

---

## Bản Đồ Luồng Dữ Liệu Cải Tiến Với Các Điểm Inject Tiềm Năng

Dưới đây là sơ đồ minh họa pipeline hiện tại với các điểm inject được đánh dấu từ ① đến ⑤:

```text
                        [ Khung hình video từ Camera / RTSP ]
                                          │
                                          ▼
                         ┌──────────────────────────────────┐
                         │  ① model(frame) -> results       │ <── Điểm Inject #1 (Dữ liệu thô nhất, không lọc) [ĐƯỢC CHỌN CHO LIVE]
                         └──────────────────────────────────┘
                                          │
                                          ▼
                         ┌──────────────────────────────────┐
                         │  ② ActiveLearning / OOD Filters  │ <── Điểm Inject #2 [ĐÃ LOẠI BỎ CHO LIVE]
                         └──────────────────────────────────┘
                                          │
                                         (Nếu Đạt Điều Kiện Lọc / AL Hit)
                                          │
                                          ▼
                         ┌──────────────────────────────────┐
                         │  ③ Build detections_list         │ <── Điểm Inject #3 [ĐÃ LOẠI BỎ CHO LIVE]
                         └──────────────────────────────────┘
                                          │
                                          ▼
                         ┌──────────────────────────────────┐
                         │  ④ Save Buffer & Upload (MinIO)  │ <── Điểm Inject #4 [ĐÃ LOẠI BỎ CHO LIVE]
                         │     + Publish Metadata (MQTT)    │
                         └──────────────────────────────────┘
                                          │
                          (Trong vòng lặp chính của Edge Server)
                                          │
                                          ▼
                         ┌──────────────────────────────────┐
                         │  ⑤ main.py process loop          │ <── Điểm Inject #5 (Lớp điều khiển / Đa luồng) [ĐƯỢC CHỌN CHO LIVE]
                         └──────────────────────────────────┘
```

---

## Chi Tiết Điểm Can Thiệp Hợp Lệ Cho Luồng Live

### Điểm Inject #1 — Ngay sau `model(frame)` (Trong `inference.py`, trước các bộ lọc)

#### 1. Vị trí mã nguồn
Nằm ngay sau khi YOLO trả về danh sách đối tượng nhận diện, trước khi chạy qua bất kỳ bộ lọc nào (Active Learning, Rule OOD) hay cổng Publish Gate:
```python
# edge_server/inference.py (khoảng dòng 39-44)
results = model(frame, conf=inference_confidence_threshold)
for result in results:
    boxes = result.boxes
    if len(boxes) == 0:
        continue
    # ──> INJECT LIVE TELEMETRY TẠI ĐÂY
```

#### 2. Dữ liệu khả dụng tại điểm này
- `result` (`ultralytics.engine.results.Results`): Đối tượng chứa toàn bộ bounding boxes (`xyxy`), classes, confidences của frame hiện tại trên RAM.
- `frame` (`numpy.ndarray`): Mảng ảnh gốc thô chưa qua nén.

#### 3. Phương án thiết kế lựa chọn (Chosen Design Option)
- **Live MQTT Streamer (A2)**: Publish trực tiếp tọa độ của các xe phát hiện được trên frame qua một topic MQTT riêng (ví dụ `traffic/live_tracking`) siêu nhẹ.
  * **Tại sao được chọn**: Nhận dữ liệu ở tần số tối đa của luồng AI (~23 FPS), không bị ảnh hưởng bởi cooldown hay bộ lọc. Web Server sẽ có dữ liệu tọa độ liên tục để duy trì IoU Tracker hoạt động ổn định.
  * **Cơ chế truyền thông**: Sử dụng MQTT QoS = 0, không chờ xác nhận gửi từ Broker. Luồng chính sẽ gửi tin nhắn dạng "fire-and-forget", nếu có mất mạng tạm thời cũng không block vòng lặp chính.

#### 4. Ví dụ Code Mẫu (Phương án A2 - Live MQTT Streamer)
```python
import json
import time

def process_and_send(
    frame: cv2.typing.MatLike,
    model: YOLO,
    minio_client: Minio,
    mqtt_client_instance: mqtt_client.Client,
    camera_id: str,
    active_learning_filter: ActiveLearningFilter,
    publish_gate: PublishGate,
    rule_ood_filter: RuleBasedOodFilter,
) -> None:
    # 1. Chạy Model Inference
    results = model(frame, conf=inference_confidence_threshold)
    
    for result in results:
        boxes = result.boxes
        if len(boxes) == 0:
            continue
            
        # ──> INJECT CHO LIVE TRACKING: Gửi ngay tọa độ thô, bỏ qua mọi bộ lọc
        detections_list = []
        for box in boxes:
            b = box.xyxy[0].tolist()  # Định dạng [x1, y1, x2, y2] chuẩn xyxy
            detections_list.append({
                "class": model.names[int(box.cls[0])],
                "conf": float(box.conf[0]),
                "bbox": [int(b[0]), int(b[1]), int(b[2]), int(b[3])]
            })
            
        live_payload = {
            "camera_id": camera_id,
            "timestamp": time.time(),
            "detections": detections_list
        }
        
        # Publish phi chặn (non-blocking) với QoS = 0 lên topic live
        try:
            mqtt_client_instance.publish(
                "traffic/live_tracking",
                json.dumps(live_payload),
                qos=0
            )
        except Exception as e:
            log(f"Failed to publish live telemetry: {e}")

    # 2. Tiếp tục chạy bộ lọc Active Learning & OOD cho luồng MLOps ở phía dưới...
```

---

## Các Điểm Can Thiệp ②, ③, ④ — KHÔNG PHÙ HỢP CHO LIVE TRACKING (ĐÃ LOẠI BỎ)

Để đáp ứng được yêu cầu tối thiểu **7 - 12 FPS** nhằm đảm bảo thuật toán IoU Tracker trên Web Server không bị mất dấu vật thể, các điểm can thiệp nằm sau bộ lọc hoặc cổng Publish Gate đều không khả thi:
- **Điểm Inject ② (Trong bộ lọc)**: Việc can thiệp rẽ nhánh tại đây sẽ làm nhiễu loạn logic của bộ lọc Active Learning và OOD, đồng thời nếu bộ lọc trả về `continue` (bỏ qua frame bình thường), luồng Live sẽ mất hoàn toàn dữ liệu của các xe chạy bình thường.
- **Điểm Inject ③ & ④ (Sau bộ lọc & Lớp Transport)**: Chỉ nhận được dữ liệu thưa thớt (trung bình 6 giây một lần) khi có sự kiện Active Learning kích hoạt. Gửi dữ liệu ở tần suất này sẽ làm IoU giữa các khung hình kề nhau bằng 0, khiến tracker thất bại hoàn toàn.

---

### Điểm Inject #5 — Tại vòng lặp chính của `main.py` (Lớp điều khiển tiến trình / Đa luồng)

#### 1. Vị trí mã nguồn
Nằm ngay trong vòng lặp đọc khung hình từ RTSP/Camera trong tệp `main.py`:
```python
# edge_server/main.py (khoảng dòng 107-133)
while capture.isOpened():
    ok, frame = capture.read()
    # ...
    sync_buffer_to_server(...)
    process_and_send(...) # <-- Gọi xử lý
    # ──> INJECT TẠI ĐÂY (Đồng phối hợp đa luồng)
```

#### 2. Dữ liệu khả dụng tại điểm này
- `frame` (`numpy.ndarray`): Ảnh thô lấy từ luồng RTSP của camera.
- Các biến điều phối kết nối: `minio_client`, `mqtt_client_instance`, v.v.

#### 3. Thiết kế Đa Luồng 3 Tầng (3-Thread Architecture)
Để đảm bảo luồng Live Telemetry từ Điểm Inject #1 chạy liên tục ở FPS tối đa (~23 FPS) không bao giờ bị nghẽn bởi các tác vụ I/O mạng hoặc ghi đĩa của MLOps (Active Learning), hệ thống được thiết kế theo mô hình 3 luồng song song:

1. **Luồng 1 (Main/Inference Thread)**:
   - Đọc frame từ RTSP, chạy YOLO, lọc Active Learning.
   - Gửi ngay lập tức tọa độ thô (Realtime Telemetry) qua MQTT QoS = 0 phi chặn (non-blocking) lên Web Server.
   - Nếu frame đạt chuẩn Active Learning: Copy frame và đẩy vào RAM Queue.
2. **Luồng 2 (Local Disk Writer Thread)**:
   - Lấy frame từ RAM Queue, nén JPEG, ghi file `.jpg` và JSON vào thư mục đệm cục bộ `.\buffer` trên Jetson.
   - Hoàn toàn không đụng tới mạng nên tốc độ ghi cực nhanh, đảm bảo RAM Queue luôn trống.
3. **Luồng 3 (Background Sync Thread)**:
   - Chạy ngầm định kỳ quét thư mục `.\buffer`, upload ảnh lên MinIO, publish metadata lên MQTT và xóa file local sau khi đồng bộ thành công.
   - Nếu mất mạng hoặc nghẽn mạng, luồng này sẽ tạm dừng đồng bộ và thử lại sau, hoàn toàn không làm gián đoạn Luồng 1 gửi Live Telemetry.

#### 4. Ví dụ Code Mẫu (Kiến Trúc Đa Luồng)
```python
import queue
import threading
import time
import cv2
import gc
from .logger import log
from .buffer_store import LocalFileBufferStore

# Giới hạn hàng đợi RAM Queue ở mức thấp (maxsize = 10) để tránh tràn RAM (OOM)
jobs_queue = queue.Queue(maxsize=10)
exit_event = threading.Event()

def local_disk_writer_worker(q: queue.Queue, buffer_store: LocalFileBufferStore):
    """Worker Thread 1: Chuyên lấy frame từ Queue RAM, nén JPEG và ghi vào .\buffer cục bộ (Không đụng tới mạng)."""
    while not exit_event.is_set():
        try:
            item = q.get(timeout=1.0)
        except queue.Empty:
            continue
            
        if item is None: 
            break
            
        try:
            frame = item.get("frame")
            image_name = item.get("image_name")
            metadata = item.get("metadata")
            
            # Ghi cục bộ (nhả GIL khi imencode và ghi file đĩa)
            buffer_store.save_payload(frame, image_name, metadata)
            
            # Giải phóng RAM ngay lập tức
            del frame
            gc.collect()
        except Exception as e:
            log(f"Disk Writer worker error: {e}")
        finally:
            q.task_done()

def background_sync_worker(buffer_store: LocalFileBufferStore, minio_client, mqtt_client):
    """Worker Thread 2: Chạy ngầm quét thư mục .\buffer và đồng bộ lên Server bất đồng bộ khi có kết nối mạng."""
    while not exit_event.is_set():
        try:
            # Đồng bộ định kỳ (ví dụ: fput_object lên MinIO và publish JSON lên MQTT)
            # Xóa các file local thành công để giải phóng dung lượng đĩa
            # Nếu mất mạng, luồng này ghi log lỗi và sẽ tự động retry ở chu kỳ tiếp theo.
            pass
        except Exception as e:
            log(f"Background Sync error: {e}")
        time.sleep(5.0) # Chu kỳ nghỉ dài để tránh tốn tài nguyên CPU
```

---

## Bảng So Sánh Tổng Hợp Lựa Chọn Thiết Kế Cho Luồng Live

| Điểm Inject | Giải pháp phù hợp nhất | Độ khó kỹ thuật | Ưu tiên | Trạng thái | Giải quyết lỗi/thiếu sót nào |
|---|---|---|---|---|---|
| **#1 (Sau Model)** | **A2** - Live MQTT Streamer | Thấp | Cao | **ĐƯỢC CHỌN** | **Đồng bộ Tracker**: Đảm bảo gửi tọa độ liên tục (15-25 FPS) để IoU Tracker trên Web Server không bị mất dấu. |
| **#2 (Trong Bộ Lọc)** | - | - | - | **ĐÃ LOẠI BỎ** | Không khả thi (bỏ sót xe bình thường, vi phạm Separation of Concerns). |
| **#3 (Sau Serialize)** | - | - | - | **ĐÃ LOẠI BỎ** | Không khả thi (tần suất thưa thớt 6s/lần do bị bộ lọc/gate chặn). |
| **#4 (Lớp Transport)** | - | - | - | **ĐÃ LOẠI BỎ** | Không khả thi (chỉ phục vụ đồng bộ file offline). |
| **#5 (Vòng lặp Main)** | **E1** - Kiến trúc Đa luồng 3 Tầng | Cao | Cao | **ĐƯỢC CHỌN** | **Chống nghẽn mạng**: Đảm bảo luồng chính (Main Thread) không bao giờ bị block khi mất kết nối mạng. |

---

## Khuyến Nghị Lộ Trình Triển Khai (Roadmap) Cho Luồng Live

### 🚀 Bước 1: Triển khai luồng Live Telemetry (Ngắn hạn - Cứu IoU Tracker)
- **Hành động**: Triển khai Điểm Inject #1 để gửi tọa độ thô không qua bộ lọc.
- **Cách làm**:
  1. Thêm cấu hình `LIVE_TRACKING_ENABLED = True` trong `config.py`.
  2. Tại `inference.py`, ngay sau khi có kết quả `results` từ model YOLO, duyệt qua các box và publish trực tiếp danh sách tọa độ siêu nhẹ qua MQTT lên Web Server.
  3. Cấu hình MQTT client ở luồng chính hoạt động phi chặn (QoS=0).

### 🛠️ Bước 2: Tối ưu hóa đa luồng & Đệm cục bộ (Trung & Dài hạn - Bảo vệ Edge Server)
- **Hành động**: Triển khai Điểm Inject #5 (Kiến trúc đa luồng 3 tầng) để tách biệt luồng Live và luồng MLOps.
- **Cách làm**:
  1. Xây dựng luồng phụ 1 (Local Disk Writer) để ghi file JPEG + JSON của các ảnh Active Learning được duyệt xuống đĩa local đệm `.\buffer`.
  2. Xây dựng luồng phụ 2 (Background Sync) chạy quét đệm `.\buffer` định kỳ để đồng bộ lên MinIO/MQTT Server.
- **Kết quả**: Luồng chính gửi Live Telemetry luôn đạt FPS tối đa (~23 FPS), hoàn toàn không bị ảnh hưởng bởi I/O mạng của luồng MLOps.
