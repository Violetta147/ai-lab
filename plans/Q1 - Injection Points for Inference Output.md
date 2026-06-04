# Q1 — Phân Tích Kiến Trúc Các Điểm Can Thiệp (Inject Points) Trên Edge Server

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
> 4. **Lỗi KeyError & Phân mảnh Đĩa**: Giao thức lưu đệm file JSON cũ bị KeyError khi đồng bộ lại lúc có mạng. Đồng thời, ghi hàng ngàn file nhỏ làm phân mảnh thẻ SD. Cần chuyển đổi sang SQLite WAL (Write-Ahead Logging) để tăng tốc độ ghi đĩa, giảm hao mòn đĩa và đảm bảo tính nguyên tử (atomic transaction).

---

## Bản Đồ Luồng Dữ Liệu Cải Tiến Với Các Điểm Inject Tiềm Năng

Dưới đây là sơ đồ minh họa pipeline hiện tại với các điểm inject được đánh dấu từ ① đến ⑤:

```text
                        [ Khung hình video từ Camera / RTSP ]
                                          │
                                          ▼
                         ┌──────────────────────────────────┐
                         │  ① model(frame) -> results       │ <── Điểm Inject #1 (Dữ liệu thô nhất, không lọc)
                         └──────────────────────────────────┘
                                          │
                                          ▼
                         ┌──────────────────────────────────┐
                         │  ② ActiveLearning / OOD Filters  │ <── Điểm Inject #2 (Phân loại: Ảnh khó vs. Bình thường)
                         └──────────────────────────────────┘
                                          │
                                         (Nếu Đạt Điều Kiện Lọc / AL Hit)
                                          │
                                          ▼
                         ┌──────────────────────────────────┐
                         │  ③ Build detections_list         │ <── Điểm Inject #3 (Dữ liệu đã được định dạng/serialize)
                         └──────────────────────────────────┘
                                          │
                                          ▼
                         ┌──────────────────────────────────┐
                         │  ④ Save Buffer & Upload (MinIO)  │ <── Điểm Inject #4 (Lớp Transport / Truyền thông)
                         │     + Publish Metadata (MQTT)    │
                         └──────────────────────────────────┘
                                          │
                          (Trong vòng lặp chính của Edge Server)
                                          │
                                          ▼
                         ┌──────────────────────────────────┐
                         │  ⑤ main.py process loop          │ <── Điểm Inject #5 (Lớp điều khiển / Đa luồng)
                         └──────────────────────────────────┘
```

---

## Phân Tích Chi Tiết 5 Điểm Inject

---

### Điểm Inject #1 — Ngay sau `model(frame)` (Trong `inference.py`, trước các bộ lọc)

#### 1. Vị trí mã nguồn
Nằm ngay sau khi YOLO trả về danh sách đối tượng nhận diện, trước khi chạy qua Active Learning Filter hoặc Rule Based OOD Filter:
```python
# edge_server/inference.py (khoảng dòng 39-44)
results = model(frame, conf=inference_confidence_threshold)
for result in results:
    boxes = result.boxes
    if len(boxes) == 0:
        continue
    # ──> INJECT TẠI ĐÂY
```

#### 2. Dữ liệu khả dụng tại điểm này
- `result` (`ultralytics.engine.results.Results`): Đối tượng chứa toàn bộ bounding boxes (`xyxy`, `xywh`), classes, confidences của frame hiện tại trên bộ nhớ.
- `frame` (`numpy.ndarray`): Mảng ảnh gốc thô chưa qua nén hay biến đổi.

#### 3. Các phương án thiết kế (Design Options)

| Phương án | Chi Tiết Kỹ Thuật | Ưu điểm | Nhược điểm | Tác Động Tài Nguyên |
|---|---|---|---|---|
| **A1. Raw Inference Callback** | Đăng ký callback từ `main.py` dạng `on_raw_inference(frame, result)` và gọi trước bộ lọc. | Tách biệt logic xử lý thô khỏi pipeline chính; linh hoạt đăng ký nhiều handler. | Cần thay đổi chữ ký (signature) hàm `process_and_send`. | **RAM**: Thấp.<br>**CPU**: Thấp (chạy tuần tự). |
| **A2. Live MQTT Streamer** | Gửi trực tiếp tọa độ thô của frame lên một topic MQTT riêng (ví dụ `traffic/live_raw`) không kèm ảnh. | Cực tốt cho Live Tracking; Server có dữ liệu liên tục ở mọi khung hình có xe. | Làm tăng số lượng tin nhắn qua mạng nếu FPS quá cao. | **Network**: ~10-20 KB/s (chỉ gửi text). |
| **A3. Local IPC / WebSocket** | Đẩy qua WebSocket/IPC local cho ứng dụng hiển thị trực tiếp tại biên (Local Monitor UI). | Hiển thị thời gian thực tại biên mà không chịu độ trễ mạng Internet. | Phụ thuộc vào giao tiếp local; tăng độ phức tạp của app biên. | **CPU**: Tăng nhẹ do serialize JSON. |

#### 4. Ví dụ Code Mẫu (Phương án A1 - Dual-stream Callback)
```python
from typing import Callable
from ultralytics.engine.results import Results
import cv2

# Định nghĩa kiểu callback
RawInferenceCallback = Callable[[cv2.typing.MatLike, Results], None]

def process_and_send(
    frame: cv2.typing.MatLike,
    model: YOLO,
    minio_client: Minio,
    mqtt_client_instance: mqtt_client.Client,
    camera_id: str,
    active_learning_filter: ActiveLearningFilter,
    publish_gate: PublishGate,
    rule_ood_filter: RuleBasedOodFilter,
    on_raw_inference: RawInferenceCallback | None = None, # Thêm tham số callback
) -> None:
    # ...
    results = model(frame, conf=inference_confidence_threshold)
    for result in results:
        boxes = result.boxes
        if len(boxes) == 0:
            continue
            
        # Gọi callback cho mọi khung hình có vật thể
        if on_raw_inference is not None:
            try:
                on_raw_inference(frame, result)
            except Exception as e:
                log(f"Error in raw inference callback: {e}")
                
        # Tiếp tục chạy bộ lọc Active Learning & OOD phía dưới...
```

---

### Điểm Inject #2 — Bên trong khối bộ lọc, thêm nhánh quyết định (Trong `inference.py`)

#### 1. Vị trí mã nguồn
Nằm tại phần rẽ nhánh khi bộ lọc Active Learning/OOD trả về kết quả âm tính (`continue`), hoặc khi Publish Gate chặn gửi ảnh:
```python
# edge_server/inference.py (khoảng dòng 57-66)
# Nếu cả 2 bộ lọc đều không báo động thì bỏ qua
if not al_hit and not rule_ood_hit:
    # ──> INJECT TẠI ĐÂY (Thay vì bỏ qua hoàn toàn, định tuyến gửi metadata)
    continue

# Kiểm tra Publish Gate (Tần suất gửi ảnh)
should_publish, gate_reason = publish_gate.should_publish(frame)
if not should_publish:
    # ──> INJECT TẠI ĐÂY (Frame bị chặn ảnh nhưng vẫn có thể gửi tọa độ)
    continue
```

#### 2. Dữ liệu khả dụng tại điểm này
- `al_hit` / `rule_ood_hit` (`bool`): Đánh giá xem ảnh có thuộc tập Active Learning/OOD không.
- `should_publish` (`bool`): Quyết định của Publish Gate (cooldown, trùng phash).
- `result` (`Results`) và `frame` (`numpy.ndarray`).

#### 3. Các phương án thiết kế (Design Options)

| Phương án | Chi Tiết Kỹ Thuật | Ưu điểm | Nhược điểm | Tác Động Tài Nguyên |
|---|---|---|---|---|
| **B1. Filter Decision Router** | Thay thế khối logic `continue` bằng bộ định tuyến quyết định (`FilterDecisionRouter`) với 3 trạng thái. | Kiểm soát tập trung luồng đi của ảnh và metadata; giải quyết triệt để bài toán Live + MLOps. | Cần tái cấu trúc (refactor) lại cấu trúc điều hướng if/else trong `inference.py`. | **RAM**: Thấp.<br>**CPU**: Thấp. |
| **B2. Cấu hình `LIVE_STREAM_ONLY`** | Thêm cấu hình toàn cục. Nếu bật, bỏ qua bộ lọc và luôn gửi metadata nhẹ; nếu tắt, giữ nguyên logic gốc. | Rất dễ triển khai (chỉ mất ~5 dòng code). | Thiếu linh hoạt; không thể chạy đồng thời cả hai chế độ (MLOps + Live). | **Network**: Thay đổi theo cấu hình. |

#### 4. Ví dụ Code Mẫu (Phương án B1 - Filter Decision Router)
```python
from enum import Enum

class FilterDecision(Enum):
    DISCARD = "discard"              # Bỏ qua hoàn toàn (không có vật thể)
    METADATA_ONLY = "metadata_only"  # Chỉ gửi tọa độ qua MQTT thô (Live tracking)
    SEND_FULL = "send_full"          # Upload MinIO + gửi MQTT đầy đủ (MLOps)

class FilterDecisionRouter:
    def __init__(self, live_tracking_enabled: bool = True):
        self.live_tracking_enabled = live_tracking_enabled

    def decide(
        self, al_hit: bool, rule_ood_hit: bool, should_publish: bool
    ) -> FilterDecision:
        # Nhánh 1: Được cả bộ lọc và Gate chấp thuận -> Gửi ảnh + metadata đầy đủ
        if (al_hit or rule_ood_hit) and should_publish:
            return FilterDecision.SEND_FULL
            
        # Nhánh 2: Ảnh bình thường HOẶC ảnh khó bị Gate chặn (cooldown) nhưng vẫn có vật thể
        if self.live_tracking_enabled:
            return FilterDecision.METADATA_ONLY
            
        return FilterDecision.DISCARD

# Áp dụng trong inference.py:
# decision = router.decide(al_hit, rule_ood_hit, should_publish)
# if decision == FilterDecision.DISCARD:
#     continue
# elif decision == FilterDecision.METADATA_ONLY:
#     publish_lightweight_metadata(...) # Gửi MQTT nhanh
#     continue
```

---

### Điểm Inject #3 — Sau khi tuần tự hóa (serialize) `detections_list` (Trong `inference.py`)

#### 1. Vị trí mã nguồn
Nằm ngay sau khi toạ độ và nhãn từ YOLO (`result.boxes`) được chuyển đổi thành danh sách các dictionary Python:
```python
# edge_server/inference.py (khoảng dòng 76-84)
detections_list = []
for box in boxes:
    b = box.xyxy[0].tolist()
    detections_list.append({
        "class": model.names[int(box.cls[0])],
        "conf": float(box.conf[0]),
        "bbox": [int(b[0]), int(b[1]), int(b[2]), int(b[3])]
    })
# ──> INJECT TẠI ĐÂY
```

#### 2. Dữ liệu khả dụng tại điểm này
- `detections_list` (`list[dict]`): Dạng dữ liệu chuẩn hóa dạng JSON `[{"class": "car", "conf": 0.85, "bbox": [x1, y1, x2, y2]}, ...]`.
  - *Lưu ý sửa lỗi hệ tọa độ*: Định dạng box xuất ra phải thống nhất là `[x1, y1, x2, y2]` (xyxy) để tránh việc Server chạy hàm convert `_xywh_to_xyxy()` bị sai lệch tọa độ hiển thị và hỏng IoU tracker.
- `raw_image_name` (`str`): Tên file ảnh đã được định dạng duy nhất.

#### 3. Các phương án thiết kế (Design Options)

| Phương án | Chi Tiết Kỹ Thuật | Ưu điểm | Nhược điểm | Tác Động Tài Nguyên |
|---|---|---|---|---|
| **C1. Output Sink Adapter (Strategy Pattern)** | Khởi tạo interface `OutputSink` với các lớp cụ thể: `MinioMqttSink`, `LiveTrackingMqttSink`, `LocalLogSink`. | Cực kỳ tuân thủ nguyên lý thiết kế SOLID (Open-Closed Principle); dễ viết unit test độc lập cho từng Sink. | Cần tạo thêm nhiều class mới và cấu trúc lại hàm gửi tin. | **RAM**: Tăng nhẹ do quản lý các đối tượng Adapter. |
| **C2. Middleware Pipeline** | Cho phép dữ liệu đi qua một mảng các hàm xử lý tuần tự `[func1, func2, ...]`. | Dễ dàng bật/tắt các middleware thông qua config file (ví dụ: tắt ghi log cục bộ). | Khó kiểm soát thứ tự xử lý và lỗi phát sinh từ middleware. | **Latency**: Phụ thuộc vào hiệu năng của từng middleware. |

#### 4. Ví dụ Code Mẫu (Phương án C1 - Output Sink Adapter)
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
import json

@dataclass
class InferencePayload:
    camera_id: str
    timestamp: float
    trigger_reason: str
    detections: list[dict]
    frame: cv2.typing.MatLike
    image_name: str | None = None

class OutputSink(ABC):
    @abstractmethod
    def emit(self, payload: InferencePayload) -> None:
        pass

class CompositeSink(OutputSink):
    """Composite Pattern: Phát tin nhắn tới tất cả các Sink được đăng ký."""
    def __init__(self, sinks: list[OutputSink]):
        self.sinks = sinks
        
    def emit(self, payload: InferencePayload) -> None:
        for sink in self.sinks:
            try:
                sink.emit(payload)
            except Exception as e:
                log(f"Error in sink {sink.__class__.__name__}: {e}")

class MqttLiveTrackingSink(OutputSink):
    def __init__(self, mqtt_client, topic: str = "traffic/live_tracking"):
        self.mqtt_client = mqtt_client
        self.topic = topic

    def emit(self, payload: InferencePayload) -> None:
        # Gửi dữ liệu siêu nhẹ, không chứa thuộc tính image_url của MinIO
        light_metadata = {
            "camera_id": payload.camera_id,
            "timestamp": payload.timestamp,
            "detections": payload.detections
        }
        self.mqtt_client.publish(self.topic, json.dumps(light_metadata))

class LocalCsvSink(OutputSink):
    def __init__(self, output_path: str = "./buffer/inference.csv"):
        self.output_path = output_path

    def emit(self, payload: InferencePayload) -> None:
        with open(self.output_path, "a", encoding="utf-8") as f:
            for det in payload.detections:
                # Ghi log CSV: timestamp, class, confidence, box
                bbox_str = "-".join(map(str, det["bbox"]))
                f.write(f"{payload.timestamp},{det['class']},{det['conf']},{bbox_str}\n")
```

---

### Điểm Inject #4 — Tại lớp truyền dẫn và lưu đệm offline (Trong `buffer_store.py`)

#### 1. Vị trí mã nguồn
Nằm tại phần tích hợp I/O của hệ thống (`upload_buffer_file` và `publish_detection`), điều khiển cách dữ liệu được vận chuyển lên Server và lưu trữ đệm khi mất kết nối.

#### 2. Dữ liệu khả dụng tại điểm này
- File ảnh JPEG cục bộ nằm trong `./buffer/`.
- File JSON chứa metadata của nhận diện.

#### 3. Các phương án thiết kế (Design Options)

| Phương án | Chi Tiết Kỹ Thuật | Ưu điểm | Nhược điểm | Tác Động Tài Nguyên |
|---|---|---|---|---|
| **D1. SQLite WAL Buffer Store** | Thay thế hàng ngàn file `.json` nhỏ bằng một tệp SQLite cục bộ chạy ở chế độ ghi trước nhật ký (Write-Ahead Logging). | Tránh phân mảnh ổ cứng Edge; sửa đổi mang tính nguyên tử (atomic), loại bỏ lỗi mất file / lỗi KeyError khi sync. | Tăng thêm một thư viện dependency (`sqlite3` - tích hợp sẵn trong Python). | **Disk I/O**: Giảm tới 80% số lần đọc/ghi đĩa.<br>**Độ bền thiết bị**: Tăng tuổi thọ thẻ nhớ SD. |
| **D2. Transport Protocol Adapter** | Trừu tượng hóa cách truyền tin. Cho phép chuyển đổi linh hoạt giữa MQTT, HTTP API (S3 Upload) hoặc gRPC. | Dễ dàng triển khai trên các hạ tầng khác nhau (ví dụ: đẩy thẳng lên AWS IoT Core). | Phức tạp hóa lớp truyền thông của hệ thống. | **Băng thông**: Tối ưu hóa theo giao thức (ví dụ gRPC tiết kiệm hơn MQTT JSON). |

#### 4. Ví dụ Code Mẫu (Phương án D1 - SQLite WAL Buffer Queue)
```python
import sqlite3
import json

class SQLiteBufferQueue:
    def __init__(self, db_path: str = "./buffer/edge_buffer.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            # Kích hoạt chế độ WAL để tăng hiệu năng ghi đĩa bất đồng bộ
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS buffer_payloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_name TEXT,
                    metadata TEXT,
                    status TEXT DEFAULT 'PENDING',
                    created_at REAL
                )
            """)

    def push(self, image_name: str, metadata: dict) -> None:
        # Sửa lỗi KeyError: Đảm bảo metadata luôn ghi nhận trường 'image_url' đúng quy chuẩn
        if "image_url" not in metadata and image_name:
            metadata["image_url"] = image_name
            
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO buffer_payloads (image_name, metadata, created_at) VALUES (?, ?, ?)",
                (image_name, json.dumps(metadata), metadata.get("timestamp", 0.0))
            )
            
    def fetch_pending(self, limit: int = 10) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, image_name, metadata FROM buffer_payloads WHERE status='PENDING' ORDER BY id ASC LIMIT ?",
                (limit,)
            )
            # Tránh KeyError: Sử dụng .get() để fallback an toàn
            return [
                {
                    "id": row[0], 
                    "image_name": row[1], 
                    "metadata": json.loads(row[2])
                } for row in cursor.fetchall()
            ]

    def delete_processed(self, payload_ids: list[int]) -> None:
        if not payload_ids:
            return
        with sqlite3.connect(self.db_path) as conn:
            placeholders = ",".join("?" for _ in payload_ids)
            conn.execute(f"DELETE FROM buffer_payloads WHERE id IN ({placeholders})", payload_ids)
```

---

### Điểm Inject #5 — Tại vòng lặp chính của `main.py` (Lớp điều khiển tiến trình)

#### 1. Vị trí mã nguồn
Nằm ngay trong vòng lặp đọc khung hình từ RTSP/Camera trong tệp `main.py`:
```python
# edge_server/main.py (khoảng dòng 107-133)
while capture.isOpened():
    ok, frame = capture.read()
    # ...
    sync_buffer_to_server(...)
    process_and_send(...) # <-- Gọi xử lý
    # ──> INJECT TẠI ĐÂY (Chạy song song hoặc thêm một Pipeline xử lý khác)
```

#### 2. Dữ liệu khả dụng tại điểm này
- `frame` (`numpy.ndarray`): Ảnh thô lấy từ luồng RTSP của camera.
- Các biến điều phối kết nối: `minio_client`, `mqtt_client_instance`, v.v.

#### 3. Các phương án thiết kế (Design Options)

| Phương án | Chi Tiết Kỹ Thuật | Ưu điểm | Nhược điểm | Tác Động Tài Nguyên |
|---|---|---|---|---|
| **E1. Async Threaded Workers** | Đọc video ở luồng chính, chạy nhận diện và đẩy kết quả vào hàng đợi `queue.Queue`. Một luồng worker khác lo việc truyền thông (I/O). | Tối ưu hóa FPS; luồng chính không bị block bởi tốc độ tải ảnh lên MinIO hoặc publish MQTT. | Cần xử lý đồng bộ luồng, đóng luồng an toàn (graceful shutdown) và tránh tràn RAM. | **CPU**: Tăng do xử lý đa luồng.<br>**Latency**: Giảm độ trễ khung hình rất nhiều. |
| **E2. Multi-model Pipeline Registry** | Chạy hai pipeline độc lập (ví dụ: Một model YOLO chạy live tracking ở 25 FPS và một model chạy active learning ở 5 FPS). | Tách biệt hoàn toàn về tần suất xử lý và độ tự tin (confidence threshold) mong muốn. | Tải GPU cực kỳ lớn do phải chạy inference nhiều lần trên cùng một phần cứng. | **GPU/RAM**: Tăng gấp đôi. Thường không khả thi trên Jetson Nano. |

#### 4. Ví dụ Code Mẫu (Phương án E1 - Async Threaded Worker & Bounded Queue)
```python
import queue
import threading
import time
import cv2
import gc

# Bắt buộc giới hạn queue (maxsize = 15) để tránh tràn bộ nhớ RAM (OOM) 
# vì mỗi frame ảnh 640x640x3 dạng numpy chiếm ~1.22 MB RAM. 15 frames = ~18.3 MB.
inference_queue = queue.Queue(maxsize=15)
exit_event = threading.Event()

def mqtt_io_worker(jobs_queue: queue.Queue, mqtt_client, minio_client):
    """Worker Thread chuyên nén JPEG và thực hiện các I/O mạng nặng ngầm dưới background."""
    while not exit_event.is_set():
        try:
            # Chờ lấy công việc trong 1 giây
            payload = jobs_queue.get(timeout=1.0)
        except queue.Empty:
            continue
            
        if payload is None: 
            break
            
        try:
            frame_copy = payload.get("frame")
            # 1. Thực hiện nén JPEG bằng C++ (nhả GIL)
            ok, img_encoded = cv2.imencode(".jpg", frame_copy)
            if not ok:
                continue
                
            # 2. Upload ảnh lên MinIO
            # 3. Publish metadata JSON qua MQTT
            mqtt_client.publish("traffic/live_tracking", json.dumps(payload["metadata"]))
            
            # Giải phóng RAM ngay lập tức để tránh OOM Killer
            del frame_copy, img_encoded
            gc.collect()
        except Exception as e:
            log(f"Worker processing error: {e}")
        finally:
            jobs_queue.task_done()
```

---

## Bảng So Sánh Tổng Hợp Lựa Chọn Thiết Kế

| Điểm Inject | Giải pháp phù hợp nhất | Độ khó kỹ thuật | Ưu tiên | Giải quyết lỗi/thiếu sót nào |
|---|---|---|---|---|
| **#1 (Sau Model)** | **A2** - Live MQTT Streamer | Thấp | Cao | **Đồng bộ Tracker**: Đảm bảo IoU Tracker không mất dấu vật thể (IoU = 0). |
| **#2 (Trong Bộ Lọc)** | **B1** - Filter Decision Router | Trung bình | Cao | **Tách biệt luồng**: Tách luồng MLOps (Cần ảnh khó) và luồng Live (Chỉ cần tọa độ). |
| **#3 (Sau Serialize)** | **C1** - Output Sink Adapter | Trung bình | Trung bình | **Coordinate System**: Vá lỗi định dạng coordinate mismatch (`xyxy` vs `xywh`). |
| **#4 (Lớp Transport)** | **D1** - SQLite WAL Buffer | Trung bình | Cao | **Độ tin cậy biên**: Khắc phục triệt để lỗi KeyError và phân mảnh thẻ SD. |
| **#5 (Vòng lặp Main)** | **E1** - Async Threaded Worker | Cao | Trung bình | **Thermal Throttling**: Nâng cao FPS và chống nghẽn nghẹt I/O khi quá nhiệt. |

---

## Khuyến Nghị Lộ Trình Triển Khai (Roadmap)

### 🚀 Bước 1: Khắc phục ngắn hạn (Khẩn cấp - Sửa lỗi mất dấu Tracker & Mất mạng crash)
- **Hành động**: Áp dụng **B1 / B2** trong Điểm Inject #2 để cứu bộ tracker, kết hợp vá lỗi `image_url` KeyError trong `buffer_store.py`.
- **Cách làm**:
  1. Thêm cấu hình `LIVE_TRACKING_ENABLED = True` trong `config.py`.
  2. Tại `inference.py`, thay vì `continue` bỏ qua các ảnh bình thường, chuyển hướng ghi nhận `detections_list` thô.
  3. Publish danh sách `detections_list` thô này qua MQTT topic `traffic/live` (chỉ chứa tọa độ, hoàn toàn không nén JPEG và không upload MinIO).
- **Kết quả**: Server nhận được tọa độ liên tục ở 15-25 FPS để IoU Tracker hoạt động chính xác. Băng thông mạng vẫn ở mức cực thấp vì không upload ảnh liên tục.

### 🛠️ Bước 2: Tối ưu hóa kiến trúc (Trung hạn - Tái cấu trúc bền vững)
- **Hành động**: Áp dụng **C1 (Output Sink Adapter)** phối hợp với **D1 (SQLite WAL Buffer)**.
- **Cách làm**:
  1. Tách toàn bộ logic lưu đệm file JPG/JSON hiện tại của `buffer_store.py` sang một lớp `SQLiteBufferStore`.
  2. Chuyển đổi mã nguồn gửi tin MQTT/MinIO trong `inference.py` thành các `OutputSink` độc lập.
- **Kết quả**: Code sạch, dễ bảo trì, loại bỏ hoàn toàn các lỗi crash do KeyError và phân mảnh file trên Jetson Nano khi chạy offline thời gian dài.

### ⚡ Bước 3: Nâng cao hiệu năng (Dài hạn - Bất đồng bộ hóa)
- **Hành động**: Áp dụng **E1 (Async Threaded Workers)**.
- **Cách làm**: Tách biệt hoàn toàn luồng đọc Camera & Chạy AI với luồng xử lý I/O mạng/ghi đĩa.
- **Kết quả**: Pipeline chạy đạt FPS tối đa của phần cứng, không bị trồi sụt khung hình khi mạng chập chờn.
