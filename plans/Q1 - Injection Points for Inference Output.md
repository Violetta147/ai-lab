# Q1 — Phân Tích Kiến Trúc Các Điểm Can Thiệp (Inject Points) Cho Luồng Live (Cập Nhật Bỏ MediaMTX)

> **Bối Cảnh Kỹ Thuật & Thách Thức Thực Tế**:
> Edge Server chạy trên thiết bị **Jetson Nano 4GB RAM (Không Swap)** kết nối trực tiếp USB Camera, thực hiện nhận diện bằng mô hình **YOLOv8n qua TensorRT FP16 (FPS đỉnh ~25-28 FPS)**.
> 
> Hệ thống đã loại bỏ MediaMTX (RTSP Server). Do đó, Jetson Nano phải tự chịu trách nhiệm truyền cả luồng video trực tiếp lẫn siêu dữ liệu (metadata) về Web Server, đồng thời xử lý lưu trữ các ảnh Active Learning.

---

## Chi Tiết Các Điểm Can Thiệp Hợp Lệ Cho Luồng Live

### Điểm Inject #1 — Ngay sau `model(frame)` (Trong `inference.py`, trước các bộ lọc) [ĐƯỢC CHỌN CHO LIVE]
- **Vị trí**: Nằm ngay sau khi YOLO trả về danh sách đối tượng nhận diện, trước khi chạy qua bất kỳ bộ lọc nào (Active Learning, Rule OOD).
- **Thiết kế**: Publish trực tiếp tọa độ (JSON) qua topic `traffic/live_tracking` VÀ frame ảnh (JPEG) qua topic `traffic/live_video`.
- **Lý do chọn**: Nhận dữ liệu ở tần số tối đa của luồng AI (~23 FPS), không bị ảnh hưởng bởi cooldown hay bộ lọc. Web Server sẽ có dữ liệu khung hình và tọa độ liên tục (vừa xử lý AI xong là đẩy đi ngay), giúp `SyncEngine` ở backend (đã được decouple) dễ dàng ghép nối với độ trễ cực thấp.

### Điểm Inject #5 — Tại vòng lặp chính của `main.py` (Đa luồng) [ĐƯỢC CHỌN CHO MLOps]
- **Vị trí**: Xoay quanh vòng lặp đọc khung hình từ Camera trong tệp `main.py`.
- **Thiết kế Đa Luồng 3 Tầng (3-Thread Architecture)**:
  1. **Luồng 1 (Main/Inference Thread)**: Đọc USB Camera, chạy YOLO, gửi Ảnh + JSON qua MQTT (Live). Lọc Active Learning và đẩy frame Hard-case vào RAM Queue.
  2. **Luồng 2 (Local Disk Writer Thread)**: Lấy frame từ RAM Queue, nén JPEG, ghi file `.jpg` và JSON vào đệm cục bộ `.\buffer`. Không block luồng 1.
  3. **Luồng 3 (Background Sync Thread)**: Chạy ngầm định kỳ quét thư mục `.\buffer`, upload ảnh lên MinIO, publish metadata lên MQTT (cho MLOps) và dọn dẹp.

---

## Khuyến Nghị Lộ Trình Triển Khai (Roadmap) Cho Luồng Live

### 🚀 Bước 1: Triển khai luồng Live Telemetry & Live Video (Ngắn hạn)
- **Hành động**: Triển khai Điểm Inject #1.
- **Cách làm**:
  1. Tại `inference.py`, ngay sau khi có kết quả `results`, publish danh sách tọa độ (QoS=0) lên `traffic/live_tracking`.
  2. Đồng thời publish luôn khung hình nén (JPEG) lên `traffic/live_video` (hoặc transport tương tự).
  3. Ở Web Server, `SyncEngine` (dùng IVideoSource và IMetadataSource) nhận cả 2 luồng này qua MQTT Consumer và ghép nối chúng.

### 🛠️ Bước 2: Tối ưu hóa đa luồng & Đệm cục bộ (Trung & Dài hạn - Bảo vệ Edge Server)
- **Hành động**: Triển khai Điểm Inject #5 (Kiến trúc đa luồng 3 tầng) để tách biệt luồng Live và luồng MLOps.
- **Cách làm**:
  1. Xây dựng luồng phụ 1 (Local Disk Writer) để ghi file JPEG + JSON MLOps xuống đĩa local đệm `.\buffer`.
  2. Xây dựng luồng phụ 2 (Background Sync) chạy quét đệm `.\buffer` định kỳ để đồng bộ lên MinIO/MQTT Server.
- **Kết quả**: Luồng chính luôn đạt FPS tối đa, hoàn toàn không bị block bởi quá trình I/O mạng hoặc đĩa chậm.
