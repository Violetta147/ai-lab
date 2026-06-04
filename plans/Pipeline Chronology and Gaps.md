# Mô tả Trình tự Hoạt động và các Vấn đề Tồn tại của Pipeline

Tài liệu này phân tích chi tiết quy trình vận hành của pipeline theo trình tự thời gian (Chronological Order) từ biên (Jetson Nano) đến server (data_pipeline & c2_center) và liệt kê các mâu thuẫn/câu hỏi lớn cần làm rõ.

---

## I. Trình tự Hoạt động theo Thời gian (Timeline)

### Bước 1: Thu phát luồng Video (RTSP Stream - Liên tục, Thời gian thực)
*   **Video Nguồn (Demo)**: Hiện tại, hệ thống sử dụng lệnh `ffmpeg` để stream một file video có sẵn lên MediaMTX, thay thế cho IP Camera thực tế để dễ dàng test và debug.
*   **MediaMTX**: Nhận luồng RTSP từ `ffmpeg` và phân phối lại cho hai bên:
    1.  **edge_server** (chạy trên Jetson Nano): Đọc luồng video qua OpenCV VideoCapture.
    2.  **c2_center** (Web Server): Bộ đọc RtspVideoReader liên tục kéo các khung hình từ MediaMTX với tốc độ khoảng 25 FPS và xếp vào một hàng đợi bộ đệm trượt (sliding queue) tối đa 150 khung hình trên RAM.

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
*   Bộ consumer MQTT của `c2_center` liên tục nhận dữ liệu đã được gán ID từ topic `traffic/tracked`.
*   **SyncEngine**:
    *   Khi có metadata mới, `SyncEngine` tính toán độ lệch đồng hồ (clock drift) giữa Jetson và Server.
    *   Nó "quay ngược thời gian" tìm trong hàng đợi video RTSP ra khung hình khớp nhất với timestamp của metadata.
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

### Câu hỏi 1: Mục tiêu hiển thị Web là "Live Bounding Box liên tục" hay "Chỉ hiển thị khi có sự kiện"?
*   **Mâu thuẫn**: `c2_center` (Web Server) được thiết kế với `SyncEngine` chạy ở tốc độ 15-25 FPS để hiển thị bounding box xe chạy mượt mà theo thời gian thực. Tuy nhiên, `edge_server` trên Jetson mặc định bật `ACTIVE_LEARNING_ENABLED = True` nên **chỉ gửi dữ liệu cực kỳ thưa thớt** (chỉ khi có ảnh mờ, lóa, hoặc model bị phân vân).
*   **Vấn đề**: Hầu hết thời gian Web sẽ không nhận được metadata mới. Bounding box trên web sẽ bị đóng băng (freeze) hoặc biến mất, khiến trải nghiệm giám sát live bị hỏng.
*   **Câu hỏi**: Bạn muốn điều chỉnh Jetson để gửi liên tục (tắt Active Learning cho luồng live) hay Web chỉ hiển thị box nhảy cóc khi có sự kiện khó?

### Câu hỏi 2: Làm sao để bộ IoU Tracker hoạt động khi dữ liệu gửi lên thưa thớt?
*   **Mâu thuẫn**: Bộ IoU Tracker trên server (`iou_tracker.py`) tính toán khoảng cách overlap giữa các khung hình liên tiếp để gán ID. Nếu Jetson chỉ gửi dữ liệu thưa thớt (ví dụ 6 giây gửi 1 lần do cooldown), khoảng cách dịch chuyển của xe giữa 2 lần gửi là quá lớn. IoU giữa hai frame sẽ luôn bằng `0.0`.
*   **Vấn đề**: Bộ tracker sẽ liên tục tạo ID mới cho cùng một chiếc xe (ID nhảy liên tục), làm hỏng toàn bộ các chỉ số thống kê (đếm xe qua vạch, đo tốc độ).
*   **Câu hỏi**: Có nên tách luồng metadata làm đôi: Một luồng gửi tọa độ thô liên tục (không kèm ảnh) để Web tracking mượt mà, và một luồng riêng chỉ gửi ảnh khó lên MinIO phục vụ MLOps?

### Câu hỏi 3: Lỗi sai lệch tọa độ bounding box (`xyxy` vs `xywh`)
*   **Mâu thuẫn**: Jetson gửi tọa độ dạng `[x1, y1, x2, y2]` (xyxy). Server nhận được lại tự động chạy hàm `_xywh_to_xyxy()`.
*   **Vấn đề**: Tọa độ hộp nhận diện bị nhân rộng sai lệch hoàn toàn trên Web và hỏng thuật toán tracking.
*   **Câu hỏi**: Đồng ý cho phép sửa file `iou_tracker.py` trên server để nhận trực tiếp tọa độ `xyxy` từ Jetson mà không convert?

### Câu hỏi 4: Lỗi crash đồng bộ offline khi có mạng trở lại (KeyError Bug trên Jetson)
*   **Mâu thuẫn**: Code lưu đệm JSON của Jetson không ghi trường `raw_image_url` hay `predicted_image_url`, nhưng code đọc đệm khi có mạng lại cố tình truy xuất hai trường này.
*   **Vấn đề**: Jetson sẽ bị crash tiến trình đồng bộ đệm và không thể gửi lại dữ liệu cũ khi khôi phục kết nối.
*   **Câu hỏi**: Có cần vá lỗi này trong file `edge_server/buffer_store.py` để đảm bảo tính năng chạy offline của Jetson hoạt động đúng?
