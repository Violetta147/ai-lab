# Risk Analysis of Chosen Injection Points (Phân Tích Rủi Ro Các Điểm Can Thiệp Được Chọn)

Tài liệu này phân tích chi tiết các rủi ro kỹ thuật, tác động hệ thống và các biện pháp giảm thiểu (Mitigation Strategies) đối với 2 điểm can thiệp (Injection Points) được lựa chọn cho luồng Live và MLOps trên Edge Server (Jetson Nano 4GB).

---

## 1. Bản Đồ Tổng Quan Rủi Ro

| Điểm Inject | Chức Năng | Các Rủi Ro Chính | Mức Độ Nghiêm Trọng | Khả Năng Xảy Ra | Biện Pháp Khắc Phục Chủ Chốt |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Point #1 (Sau Model)** | Gửi Live Telemetry & Video qua MQTT | - Chi phí serialize JSON | **Thấp** | **Thấp** | - QoS = 0 phi chặn<br>- Nén gọn Payload JSON |
| **Point #5 (Vòng lặp Main)** | Kiến trúc Đa luồng 3 Tầng (Điều phối Luồng 1, 2, 3) | - Tràn RAM gây OOM Killer<br>- Tranh chấp CPU làm sụt FPS<br>- Đầy ổ đĩa cục bộ | **Cao** | **Trung bình** | - Giới hạn cứng Queue RAM (`maxsize=10`)<br>- Nhả GIL & Phân chia nhân CPU<br>- Thiết lập giới hạn dung lượng ổ đĩa (Safety Disk Limit) |

---

## 2. Phân Tích Chi Tiết & Biện Pháp Giảm Thiểu

### 2.1. Điểm Can Thiệp #1 — Gửi Live Telemetry Ngay Sau Model (MQTT QoS = 0)

Điểm can thiệp này đảm bảo tần suất gửi tọa độ cao (15-25 FPS) để thuật toán IoU Tracker trên Web Server không bị mất dấu xe. Tuy nhiên, nó mang lại một số rủi ro về truyền thông mạng:

#### Rủi ro 1: Nghẽn Mạng LAN/4G & Quá Tải MQTT Broker (ĐÃ CHỨNG MINH KHÔNG ĐÁNG KỂ)
*   **Mô tả trước đây**: Lo ngại rằng gửi liên tục ảnh nén JPEG và JSON tọa độ ở tốc độ 25 FPS qua MQTT sẽ làm nghẽn băng thông mạng hoặc quá tải Broker.
*   **Kết quả phân tích**: Theo tính toán thực tế, ở độ phân giải 640x640, tổng băng thông truyền tải 25 FPS (cả ảnh JPEG ~25KB và JSON) chỉ tốn **~5.3 Mbps** (chiếm khoảng 2% công suất mạng Wi-Fi LAN thông thường). MQTT Broker hoàn toàn có thể xử lý lượng tải này một cách rất nhẹ nhàng. Rủi ro này xem như đã được giải quyết bằng việc chọn thiết kế độ phân giải hợp lý.
*   **Biện pháp dự phòng**:
    *   **Cơ chế truyền phi chặn (Non-blocking QoS = 0)**: Vẫn cấu hình MQTT gửi tin `QoS = 0` (Fire-and-forget). Nếu đứt cáp mạng, MQTT tự động drop gói tin và không block vòng lặp chính.
    *   **Đồng bộ phía Client (Web)**: Web Frontend tự drop các gói tin cũ (trễ > 200ms) để tránh giật hình.

#### Rủi ro 2: Lệch Pha Thời Gian Giữa Ảnh và Tọa Độ (ĐÃ ĐƯỢC GIẢI QUYẾT TRIỆT ĐỂ)
*   **Mô tả trước đây**: Trước đây `SyncEngine` phải ghép khung hình RTSP (từ MediaMTX) với metadata MQTT (từ Jetson), đòi hỏi đồng bộ NTP chặt chẽ để bù trừ độ trễ mạng khác biệt giữa 2 luồng.
*   **Cách giải quyết (Theo kiến trúc mới)**: Bằng việc loại bỏ MediaMTX và gửi **cả khung hình nén (JPEG) lẫn siêu dữ liệu (JSON)** trực tiếp qua MQTT từ Jetson ở Điểm Inject #1, cả hai gói tin đều mang chung một `timestamp` gốc được tạo ra tại cùng một tíc tắc trên Jetson. 
*   **Kết quả**: `SyncEngine` ở backend chỉ cần chờ và gom 2 gói tin có cùng `timestamp` lại với nhau, hoàn toàn triệt tiêu rủi ro Clock Drift. Không còn bắt buộc đồng bộ NTP khắt khe hay thuật toán bù trượt (drift correction) phức tạp nữa.

#### Rủi ro 3: Chi Phí CPU Cho Việc Serialize Dữ Liệu
*   **Mô tả**: Chạy hàm `json.dumps()` cho 15-25 frame mỗi giây sẽ tiêu tốn tài nguyên CPU xử lý chuỗi trên Jetson Nano.
*   **Tác động**: Góp phần tăng nhiệt độ CPU, đẩy nhanh quá trình quá nhiệt (Thermal Throttling) của Jetson Nano.
*   **Biện pháp giảm thiểu**:
    *   **Nén gọn cấu trúc Payload**: Rút gọn tối đa kích thước dữ liệu JSON gửi đi bằng cách dùng các key viết tắt (ví dụ: `{"c": "car", "b": [10, 20, 100, 150]}` thay vì `{"class_name": "car", "bounding_box": [...]}`).
    *   **Sử dụng JSON Parser tốc độ cao**: Thay thế thư viện `json` mặc định của Python bằng `orjson` hoặc `ujson` được viết bằng C/Rust để tăng tốc độ tuần tự hóa lên gấp 3-5 lần.

---

### 2.2. Điểm Can Thiệp #5 — Kiến Trúc Đa Luồng 3 Tầng Tại Vòng Lặp Main

Kiến trúc đa luồng điều phối 3 luồng chạy song song:
1. **Luồng 1 (Main/Inference Thread)**: Đọc frame, chạy YOLO, thực hiện **gửi Live Telemetry qua MQTT (Điểm Inject #1)**, và đẩy ảnh Active Learning vào RAM Queue.
2. **Luồng 2 (Disk Writer Thread)**: Chuyên lấy frame từ RAM Queue, nén JPEG và ghi file xuống đĩa cục bộ.
3. **Luồng 3 (Background Sync Thread)**: Chạy ngầm quét thư mục đệm cục bộ, upload ảnh lên MinIO và **publish metadata MLOps qua MQTT** (topic `traffic/detections`).

Như vậy, cả Point #1 và Point #5 đều liên quan đến việc gửi tin MQTT:
- **Luồng 1 (Point #5) gửi Live Telemetry (Point #1)** liên tục ở tần số cao (~23 FPS) lên topic `traffic/live_tracking`. Rủi ro nghẽn mạng của Point #1 ảnh hưởng trực tiếp đến Luồng 1 của Point #5.
- **Luồng 3 (Point #5) gửi MLOps Telemetry** một cách thưa thớt lên topic `traffic/detections`.

Rủi ro tại Điểm Can Thiệp #5 liên quan mật thiết đến tài nguyên RAM, CPU và bộ nhớ đĩa của Jetson Nano:

#### Rủi ro 1: Tràn Bộ Nhớ RAM Gây Crash Hệ Thống (OOM Killer)
*   **Mô tả**: Mỗi frame thô (numpy array) từ camera có dung lượng khoảng **1.22 MB** trên RAM. Nếu tốc độ ghi đĩa của Luồng 2 (Disk Writer Thread) bị nghẽn (do thẻ nhớ bị phân mảnh hoặc quá tải ghi), trong khi Luồng 1 liên tục đẩy ảnh Active Learning vào Queue RAM, hàng đợi này sẽ phình to rất nhanh. Vì Jetson Nano 4GB **không sử dụng Swap**, RAM sẽ bị cạn kiệt lập tức.
*   **Tác động**: Linux Kernel sẽ tự động kích hoạt **OOM Killer** để tắt tiến trình Python ngay lập tức (Exit Code 137).
*   **Biện pháp giảm thiểu**:
    *   **Thiết lập giới hạn cứng cho RAM Queue**: Bắt buộc khởi tạo hàng đợi với `maxsize = 10` (tiêu thụ tối đa ~12.2 MB RAM cho ảnh thô). 
    *   **Cơ chế Drop phi chặn (Non-blocking queue put)**: Trong vòng lặp chính của Luồng 1, sử dụng phương thức `queue.put_nowait()` hoặc đặt timeout cực ngắn. Nếu hàng đợi đã đầy 10 phần tử, hệ thống lập tức bỏ qua (drop) ảnh Active Learning hiện tại và ghi log cảnh báo, tuyệt đối không được phép block luồng chính hoặc tích lũy RAM vô hạn.
    *   **Thu dọn rác chủ động**: Sau khi Luồng 2 lấy ảnh ra khỏi Queue và nén xong, gọi lệnh giải phóng biến `del frame` và kích hoạt bộ dọn rác `gc.collect()` định kỳ.

#### Rủi ro 2: Tranh Chấp Tài Nguyên CPU Làm Sụt Giảm FPS Luồng AI (CPU Contention)
*   **Mô tả**: Jetson Nano chỉ có 4 nhân CPU ARM A57 hiệu năng thấp. Khi Luồng 2 chạy nén JPEG bằng CPU liên tục (CPU-bound) và Luồng 3 thực hiện kết nối mạng, các luồng này sẽ tranh giành thời gian xử lý của nhân CPU với Luồng 1 (luồng chính đang chạy OpenCV đọc camera và chuẩn bị dữ liệu cho TensorRT).
*   **Tác động**: Làm suy giảm nhẹ hiệu năng xử lý của Luồng 1, kéo FPS của AI và luồng Live xuống thấp (ví dụ từ 23 FPS xuống dưới 15 FPS).
*   **Biện pháp giảm thiểu**:
    *   **Nhả GIL hiệu quả**: Thư viện OpenCV C++ (`cv2.imencode`) và thư viện TensorRT GPU tự động nhả khóa GIL của Python trong lúc xử lý tính toán nặng. Điều này giúp các nhân CPU khác của Jetson chạy song song hoàn toàn độc lập với luồng chính Python.
    *   **Đặt độ ưu tiên luồng (Thread Priority)**: Cấu hình độ ưu tiên (nice value) thấp hơn cho Luồng 2 và Luồng 3, hoặc sử dụng `time.sleep()` hợp lý trong vòng lặp của các luồng phụ để nhường tài nguyên CPU tối đa cho Luồng 1.

#### Rủi ro 3: Đầy Dung Lượng Lưu Trữ Cục Bộ Khi Mất Mạng Kéo Dài
*   **Mô tả**: Khi thiết bị Jetson Nano bị mất kết nối mạng Internet kéo dài (vài giờ hoặc vài ngày), Luồng 3 (Background Sync Thread) không thể tải ảnh lên MinIO. Tuy nhiên, Luồng 2 vẫn liên tục nén và ghi file ảnh JPG + JSON mới vào thư mục cục bộ `.\buffer`.
*   **Tác động**: Ổ đĩa của Jetson Nano bị đầy 100%, dẫn đến lỗi hệ thống không thể ghi file mới, crash ứng dụng hoặc thậm chí gây hỏng hệ điều hành JetPack.
*   **Biện pháp giảm thiểu**:
    *   **Giới hạn an toàn dung lượng đĩa cục bộ (Local Disk Safety Limit)**: Trước khi Luồng 2 thực hiện ghi file xuống thư mục `.\buffer`, hệ thống cần kiểm tra tổng dung lượng của thư mục này hoặc kiểm tra dung lượng trống của ổ đĩa (qua lệnh `shutil.disk_usage`). 
    *   **Ngưỡng dừng**: Nếu dung lượng thư mục đệm vượt quá **500 MB** hoặc dung lượng trống của đĩa còn dưới **10%**, Luồng 2 sẽ tạm ngừng ghi file mới xuống đĩa, chỉ giữ lại tính năng gửi Live Telemetry (MQTT QoS=0) của Luồng 1 cho đến khi kết nối mạng được khôi phục và Luồng 3 dọn sạch thư mục đệm.
