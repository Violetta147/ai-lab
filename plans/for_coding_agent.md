# Tổng quan Hệ thống

Tài liệu này tóm tắt các thông số và cấu hình cơ bản của hệ thống.

## 📹 1. Nguồn Video
- **Tùy chọn 1:** USB Camera kết nối trực tiếp vào Jetson Nano.
- **Tùy chọn 2:** Đọc file video bằng OpenCV và nhận luồng video truyền từ `ffmpeg` qua mạng cục bộ.

## ⚙️ 2. Thông số Phần cứng & Thiết bị
- **Thiết bị:** NVIDIA Jetson Nano 4GB
  - **CPU:** 4 nhân
  - **GPU:** Kiến trúc Maxwell 128 cores
  - **Lưu trữ:** Thẻ nhớ SD 32GB
  - **Mạng:** Kết nối Wi-Fi
- **Quản lý Bộ nhớ:** 
  - Không sử dụng Swap memory.
  - Chỉ chạy toàn bộ trên RAM vật lý 4GB.
- **Chế độ Năng lượng & Hiệu năng:** Đã được thiết lập chạy ở chế độ `10W MAXN` và kích hoạt `jetson_clocks`.
- **Hệ thống Tản nhiệt:** *Chưa tính toán/lắp đặt.*

## 💻 3. Môi trường Phần mềm
- **JetPack Version:** 4.6
- **Python Version:** 3.8
- **Độ phân giải Xử lý:** 640x640

## 🚀 4. Hiệu năng Khối Xử lý Thị giác Máy tính (Computer Vision)
- **Tốc độ Khung hình (FPS):** Đạt 23 FPS cho công đoạn xử lý.


## 🏗️ 5. Thiết Kế Kiến Trúc Phần Mềm

Hệ thống được thiết kế đa luồng để đảm bảo **Luồng chính (Main Thread)** chỉ tập trung vào xử lý tính toán tốc độ cao, duy trì FPS ổn định.

### 🎯 A. Luồng Chính (Main Thread) - Xử Lý Cốt Lõi
1. **Thu nhận:** Đọc frame từ nguồn RTSP giả lập.
2. **Suy luận (Inference):** Chạy mô hình YOLOv8n TensorRT trên GPU.
3. **Sàng lọc:** Kiểm tra các bộ lọc Active Learning và Rule OOD.
4. **Xử lý MLOps:** Nếu phát hiện ảnh khó, sao chép (copy) khung hình trên RAM và đẩy vào Hàng Đợi RAM (`Queue`) theo cơ chế phi chặn (non-blocking).
5. **Truyền tải:** Gửi trực tiếp ảnh nén (JPEG) và JSON tọa độ (telemetry) qua MQTT lên Web Server.
   - 🛡️ *Cơ chế chống block:* Sử dụng MQTT client với vòng lặp bất đồng bộ (`loop_start()`) và `QoS = 0`. Nếu mất mạng, lệnh publish trả về ngay, không gây nghẽn luồng chính.

### 💾 B. Luồng Ghi Đĩa (Local Disk Writer Thread)
- **Nhiệm vụ:** Giải phóng RAM Queue nhanh nhất có thể bằng cách đẩy dữ liệu xuống bộ nhớ cục bộ.
  1. Lấy frame và metadata thô từ RAM Queue.
  2. Nén frame sang định dạng JPEG (`cv2.imencode`) bằng CPU.
  3. Ghi trực tiếp ảnh và JSON vào thư mục `.\buffer` trên thẻ nhớ Jetson.
- **Ý nghĩa:** Tốc độ ghi thẻ nhớ cực nhanh và độc lập với mạng lưới. Đảm bảo RAM Queue luôn trống, không block luồng chính kể cả khi mất kết nối mạng.

### ☁️ C. Luồng Đồng Bộ Ngầm (Background Sync Thread)
- **Nhiệm vụ:** Đảm bảo dữ liệu local được đẩy lên Server an toàn khi có mạng.
  1. Chạy ngầm định kỳ để quét thư mục `.\buffer`.
  2. Upload ảnh lên MinIO và gửi JSON qua MQTT nếu phát hiện file chưa đồng bộ.
  3. Xóa file local sau khi đồng bộ thành công.
- **Tự phục hồi (Resilience):** Khi mạng lỗi, luồng sẽ ghi nhận, kéo dài thời gian chờ (sleep) và bỏ qua chu kỳ hiện tại. Dữ liệu an toàn ở local và sẽ đồng bộ lại sau.

### ⚡ D. Tối Ưu Giải Phóng GIL (Python 3.8)
Kiến trúc 3 luồng này phát huy tối đa 4 nhân CPU của Jetson Nano vì Python liên tục **nhả GIL (Global Interpreter Lock)** ở các tác vụ nặng:
- Khi chạy YOLO (TensorRT C++ trên GPU).
- Khi nén JPEG (`cv2.imencode` C++).
- Khi I/O ghi file hoặc I/O mạng (MinIO/MQTT).
- **Nhường CPU (Thread Priority / Sleep):** Các luồng phụ được thiết kế với `time.sleep()` hợp lý hoặc độ ưu tiên thấp để không tranh chấp thời gian của 4 nhân CPU với luồng AI.
=> *Các luồng thực sự chạy song song hiệu quả.*

---

## ⚠️ 6. Rủi Ro Bộ Nhớ (Strict RAM Limit = 4GB, Không Swap)

Việc quản lý RAM 4GB là yếu tố **sống còn** để tránh hệ thống bị Linux OOM Killer (Out Of Memory) đóng băng.

### 📊 Ước Tính Phân Bổ RAM
| Thành Phần | Dung Lượng (Ước Tính) | Ghi Chú |
| :--- | :--- | :--- |
| **Hệ Điều Hành & Dịch Vụ** | ~800 MB - 1 GB | Nếu chạy giao diện GUI Desktop |
| **Python & Thư Viện Core** | ~200 MB | |
| **PyTorch / TensorRT** | ~1.2 GB - 1.5 GB | Trọng số YOLOv8n + CUDA |
| **OpenCV Buffer (RTSP)** | ~150 MB | Đệm stream camera |
| **RAM Queue** | ~18.3 MB | Với `maxsize=15` (1.22 MB/frame) |
| **Tổng Cộng Dự Kiến** | **~2.4 GB - 3.0 GB** | Sát ngưỡng giới hạn 4GB |

> **Nhận xét:** Dung lượng dư dả rất ít. Nếu chạy thêm IDE, Trình duyệt hoặc stream nhiều camera, RAM sẽ tràn và Linux gửi `Kill (Exit Code 137)` đóng tiến trình.

### 🛡️ Giải Pháp Tối Ưu Bộ Nhớ Bắt Buộc

1. **Chạy Chế Độ Headless (Tắt GUI):**
   Tiết kiệm ngay `~500 MB - 800 MB` RAM vật lý.
   ```bash
   sudo systemctl set-default multi-user.target # Chuyển sang dòng lệnh
   # reboot lại để áp dụng
   ```
   *(Bật lại GUI: `sudo systemctl set-default graphical.target`)*

2. **Siết Chặt RAM Queue (`maxsize = 10` đến `15`):**
   - Rất quan trọng khi tốc độ ghi đĩa bất ngờ chậm lại.
   - Nếu Queue đầy, luồng chính tự động **drop (bỏ qua)** ảnh mới để bảo vệ an toàn RAM.

3. **Giới Hạn Bộ Đệm Cục Bộ (Local Disk Safety Limit):**
   - Đặt hạn mức cho thư mục `.\buffer` (VD: max 500MB - 1GB).
   - Nếu đầy đĩa do mất mạng lâu, tạm ngưng ghi file mới cho đến khi luồng đồng bộ dọn bớt không gian.

4. **Chủ Động Dọn Dẹp RAM (Garbage Collection):**
   - Luôn dùng `del` và `gc.collect()` định kỳ sau khi xử lý xong frame lớn.
   ```python
   import gc
   
   # Ví dụ sau khi xử lý hoặc upload xong
   del frame_copy
   gc.collect()
   ```

## 🌐 7. Kiến Trúc Backend & MLOps Server (Đã Triển Khai)

Các luồng xử lý trên server đã được xây dựng và giải quyết hoàn chỉnh theo thiết kế:

1. **Gán ID Vật Thể (Real-time):** Dịch vụ `tracking_bridge` (thuộc `data_pipeline`) đã được triển khai, nhận tin thô từ Jetson, dùng thuật toán IoU gán `tracking_id` liên tục và phát lại lên MQTT.
2. **Lưu Trữ MLOps Song Song:** Dịch vụ `mqtt_to_postgres_subscriber` hoạt động độc lập, lắng nghe dữ liệu từ topic MQTT và ghi các bản ghi chứa ảnh khó (`image_url`) vào PostgreSQL phục vụ quá trình huấn luyện lại.
3. **Đồng Bộ Khung Hình & Metadata (C2 Center):** `SyncEngine` đã được tích hợp trong Backend, sử dụng thuật toán đồng bộ thời gian để ghép nối chính xác ảnh JPEG với metadata nhận diện.
4. **Hiển Thị Client Web (Thời Gian Thực):** `WsStreamer` xử lý ảnh đã nhận diện (vẽ bounding box) nén sang Base64 và truyền tải mượt mà qua WebSocket xuống React Frontend cùng thống kê lưu lượng.
5. **Tự Động Huấn Luyện (Offline, Chu Kỳ Dài):** Hệ thống tích hợp Celery Workers (như `cvat_automation_service`, `train_engine`, `ota_deploy`) định kỳ lấy ảnh khó từ MinIO, tự động gán nhãn lại qua CVAT, huấn luyện model mới và hỗ trợ hot-reload OTA cho Jetson.
