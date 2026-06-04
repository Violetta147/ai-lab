# Mô tả Trình tự Hoạt động và các Vấn đề Tồn tại của Pipeline

Tài liệu này phân tích chi tiết quy trình vận hành của pipeline theo trình tự thời gian (Chronological Order) từ biên (Jetson Nano) đến server (data_pipeline & c2_center) và liệt kê các mâu thuẫn/câu hỏi lớn cần làm rõ.

---

## I. Trình tự Hoạt động theo Thời gian (Timeline)

### Bước 1: Thu phát luồng Video (Liên tục, Thời gian thực)
*   **Video Nguồn (Demo)**: Hiện tại, hệ thống sử dụng lệnh `ffmpeg` để truyền luồng video **chỉ cho Jetson Nano** (thay thế cho Camera thực tế để dễ test). Hoàn toàn không còn sử dụng MediaMTX để phân phối mạng.
*   **edge_server** (chạy trên Jetson Nano): Đọc luồng video trực tiếp qua OpenCV VideoCapture.

### Bước 2: Xử lý tại Biên & Lọc Dữ liệu (Local Inference & Active Learning - Từng khung hình trên Jetson)
*   **Chạy AI (Inference)**: `edge_server` trên Jetson chạy model YOLOv8n trên từng khung hình đọc được từ RTSP để phát hiện vật thể.
*   **Bộ lọc Active Learning và OOD**:
    *   Với mỗi khung hình có vật thể, hệ thống kiểm tra xem nó có phải là "ảnh khó" hoặc bất thường (Out-of-Distribution) không.
    *   **Trường hợp ảnh bình thường**: Khung hình bị bỏ qua ngay lập tức. Không có dữ liệu nào được ghi hay gửi đi.
    *   **Trường hợp ảnh kích hoạt bộ lọc (Uncertainty hoặc OOD)**:
        *   *Kiểm tra Publish Gate*: Đảm bảo không vượt quá giới hạn gửi ảnh (quota) và không trùng lặp (phash).
        *   *Lưu đệm JPG*: Khung hình được nén JPEG và lưu tạm vào thư mục `./buffer` cục bộ dưới dạng file ảnh.
        *   *Lưu đệm JSON*: Metadata nhận diện (gồm tọa độ dạng `xyxy`, camera_id, timestamp, trigger_reason) được ghi tạm vào file `.json` cục bộ.
*   **Đồng bộ lên Server (Sync Buffer)**:
    *   Tiến trình ngầm trên Jetson kiểm tra kết nối mạng:
        1.  Upload file ảnh JPG từ thư mục đệm lên MinIO Server (bucket `raw-data`).
        2.  Nếu upload ảnh thành công, nó gửi payload metadata JSON tương ứng lên MQTT Broker (topic `traffic/detections`). Sau đó xóa các file đệm cục bộ.
        3.  Nếu mất mạng, dữ liệu nằm im trong thư mục `./buffer` và sẽ được gửi lại khi có mạng.

### Bước 3: Đón nhận và Gán ID Vật thể trên Server (Asynchronous & Real-time - Phía Server)
*   **Nhận tin thô**: Dịch vụ `tracking_bridge` (thuộc `data_pipeline` trên server) subscribe topic `traffic/detections` và đón nhận JSON metadata.
*   **Gán tracking_id**: 
    *   Dữ liệu được đưa vào `PerCameraTracker` (sử dụng thuật toán so khớp IoU giữa các khung hình liên tiếp của cùng một camera).
    *   Gán ID duy nhất và liên tục cho các phương tiện di chuyển.
*   **Phát tin đã xử lý**: `tracking_bridge` publish kết quả đã có `tracking_id` lên MQTT topic `traffic/tracked`.

### Bước 4: Lưu trữ MLOps song song (Không đồng bộ - Phía Server)
*   Đồng thời, dịch vụ `mqtt_to_postgres_subscriber` cũng lắng nghe topic `traffic/detections`.
*   Khi phát hiện payload có chứa đường dẫn ảnh `image_url` (tức là ảnh khó đã được upload lên MinIO), nó sẽ ghi bản ghi này vào cơ sở dữ liệu PostgreSQL với trạng thái `NEW`.

### Bước 5: Đồng bộ Khung hình & Metadata hiển thị Web (Phía `c2_center` Backend)
*   Bộ consumer MQTT của `c2_center` liên tục nhận luồng ảnh JPEG từ `traffic/live_video` và dữ liệu metadata từ `traffic/live_tracking` (hoặc `traffic/tracked`).
*   **SyncEngine**:
    *   `SyncEngine` giữ nguyên thuật toán đồng bộ thời gian (Clock Drift logic) làm cốt lõi vì đây là logic luôn luôn đúng.
    *   Thay vì tìm trong hàng đợi RTSP, nó gom cặp khung hình ảnh (JPEG) từ MQTT khớp nhất với timestamp của metadata.
*   **Analytics**: Chạy các thuật toán đếm xe, đo mật độ chiếm dụng đường hoặc vẽ heatmap trên khung hình đã đồng bộ.

### Bước 6: Hiển thị giao diện người dùng (Thời gian thực - Client Web)
*   `WsStreamer` nén ảnh đã vẽ bounding box sang base64 và đẩy qua kênh WebSocket cùng với thống kê lưu lượng.
*   Trình duyệt (React Frontend) hiển thị luồng video nhận diện thời gian thực lên màn hình của người dùng.

### Bước 7: Tự động huấn luyện lại Model (Offline, Chu kỳ dài)
*   Celery Workers định kỳ quét PostgreSQL, lấy các mẫu ảnh khó từ MinIO đưa vào CVAT để gán nhãn lại.
*   Tiến hành training tự động để sinh ra model `.engine` tối ưu hơn, sau đó gửi lệnh cập nhật OTA qua MQTT cho Jetson Nano tải về và nóng tải (hot-reload) model mà không cần dừng dịch vụ.

---

## II. Các Mâu thuẫn và Câu hỏi Lớn (Gaps & Contradictions)

Nội dung code thực tế trên Jetson Nano cho thấy nhiều điểm đi ngược lại với các giả định thiết kế ban đầu của hệ thống. Dưới đây là các câu hỏi quan trọng cần xác nhận:


### Câu hỏi 3: Lỗi sai lệch tọa độ bounding box (`xyxy` vs `xywh`)
*   **Mâu thuẫn**: Jetson gửi tọa độ dạng `[x1, y1, x2, y2]` (xyxy). Server nhận được lại tự động chạy hàm `_xywh_to_xyxy()`.
*   **Vấn đề**: Tọa độ hộp nhận diện bị nhân rộng sai lệch hoàn toàn trên Web và hỏng thuật toán tracking.
*   **Câu hỏi**: Đồng ý cho phép sửa file `iou_tracker.py` trên server để nhận trực tiếp tọa độ `xyxy` từ Jetson mà không convert?

### Câu hỏi 4: Lỗi crash đồng bộ offline khi có mạng trở lại (KeyError Bug trên Jetson)
*   **Mâu thuẫn**: Code lưu đệm JSON của Jetson không ghi trường `raw_image_url` hay `predicted_image_url`, nhưng code đọc đệm khi có mạng lại cố tình truy xuất hai trường này.
*   **Vấn đề**: Jetson sẽ bị crash tiến trình đồng bộ đệm và không thể gửi lại dữ liệu cũ khi khôi phục kết nối.
*   **Câu hỏi**: Có cần vá lỗi này trong file `edge_server/buffer_store.py` để đảm bảo tính năng chạy offline của Jetson hoạt động đúng?
