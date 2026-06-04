# Phân Tích Hiệu Năng Live Tracking Trong Môi Trường Lab (Luồng Video Giao Thông Giả Lập Qua FFMPEG)

> **Bối Cảnh & Thiết Lập Demo**:
> - **Nguồn Video**: Sử dụng ffmpeg để stream liên tục một file video giao thông thực tế lên MediaMTX để giả lập luồng camera RTSP.
> - **Độ Phân Giải Thực Tế**: Video được scale về **640x640 pixels** (theo cấu hình tham số `-vf scale=640:640` của lệnh ffmpeg và `width=640, height=640` của DeepStream/YOLO).
> - **Đối Tượng**: Các phương tiện giao thông (ô tô, xe máy, xe buýt) di chuyển với tốc độ giả lập 60 km/h.
> - **Hạ Tầng**: Thiết bị Jetson Nano 4GB (GPU Maxwell 128 nhân, CPU 4 nhân ARM A57) kết nối với Laptop thông qua mạng Wi-Fi nội bộ hoặc bộ phát Wi-Fi 4G cầm tay trong nhà.
> - **Trạng thái Phần Cứng**: Đã được thiết lập chạy ở **chế độ nguồn tối đa (10W MAXN)** và **khóa xung nhịp cao nhất (overclocked via jetson_clocks)**.
> - **Bộ Nhớ Ảo (Swap)**: **Không sử dụng Swap** (hệ thống chỉ chạy hoàn toàn trên 4GB RAM vật lý).
> - **Hệ Thống Tản Nhiệt**: Tạm thời **không tính tới hiệu quả tản nhiệt của quạt chủ động** (giả định tản nhiệt thụ động hoặc không can thiệp quạt).
> - **Môi trường Runtime**: Sử dụng **Python 3.8** trên hệ điều hành JetPack.

---

## I. Phân Tích Toán Học Cho Xe Giao Thông Tại Độ Phân Giải 640x640

Tại độ phân giải 640x640 pixels, số lượng điểm ảnh ít hơn khoảng 5 lần so với Full HD (1920x1080). Do đó, kích thước bounding box và vận tốc pixel của xe trên màn hình sẽ nhỏ hơn tương ứng.

### 1. Thông số cơ sở
- **Độ phân giải luồng Video**: 640x640 pixels.
- **Kích thước trung bình của ô tô trên khung hình**: 50x50 pixels (W = 50 px).
- **Vận tốc thực tế của xe trong video**: 60 km/h (tương đương 16.67 m/s).
- **Tỷ lệ quy đổi trên ảnh**: 1 mét tương đương khoảng 11.1 pixels (ô tô dài 4.5m chiếm khoảng 50 pixels chiều dài).
- **Vận tốc pixel trên ảnh (v)**:
  16.67 * 11.1 = 185 pixels/giây.

---

### 2. Tính toán FPS tối thiểu để IoU Tracker (trên Laptop) không mất dấu xe

Mặc dù giá trị tuyệt đối của vận tốc (v) và kích thước box (W) thay đổi theo độ phân giải, tỷ số v/W là một đại lượng bất biến về tỷ lệ (185 / 50 = 3.7 s^-1):

1. **Với ngưỡng tương đồng lỏng (IoU Threshold = 0.3)**:
   FPS tối thiểu >= (v/W) * [(1 + 0.3) / (1 - 0.3)] = 3.7 * (1.3 / 0.7) = 3.7 * 1.857 = **6.87 FPS**
   *   **Kết luận**: Luồng truyền dữ liệu từ Jetson sang Laptop phải đạt **tối thiểu 7 FPS** để tracker không bị đứt track đối với xe chạy 60 km/h.

2. **Với ngưỡng tương đồng chặt chẽ (IoU Threshold = 0.5)**:
   FPS tối thiểu >= (v/W) * [(1 + 0.5) / (1 - 0.5)] = 3.7 * (1.5 / 0.5) = 3.7 * 3.0 = **11.1 FPS**
   *   **Kết luận**: Khi cần bám đuổi chính xác cao, tần số truyền tin phải đạt **tối thiểu 12 FPS**.

3. **Hiện tượng khi bật Active Learning thưa thớt (Ví dụ: 2 giây gửi 1 lần -> FPS = 0.5)**:
   Khoảng cách di chuyển của xe giữa hai lần nhận tin:
   d = v / FPS = 185 / 0.5 = 370 pixels.
   Vì 370 px > 50 px (xe đã di chuyển xa gấp 7.4 lần kích thước của chính nó), diện tích giao nhau bằng 0 (IoU = 0).
   *   **Hậu quả**: IoU Tracker hoàn toàn thất bại. Mỗi lần nhận được metadata, hệ thống sẽ gán một ID mới cho xe, làm hỏng hoàn toàn thuật toán đếm lưu lượng và thống kê hành trình.

---

## II. Phân Tích Khả Năng Đáp Ứng Của Mạng Wi-Fi Nội Bộ (LAN) Ở Độ Phân Giải 640x640

Vì độ phân giải chỉ là 640x640, dung lượng ảnh nén JPEG sẽ giảm đi đáng kể so với ảnh Full HD.

### 1. Tính toán băng thông truyền ảnh và metadata ở 25 FPS
- Dung lượng 1 frame ảnh JPG (640x640 nén): **~25 KB** (nhẹ hơn gấp 4-5 lần so với ảnh Full HD).
- Metadata JSON: **~1.5 KB**.
- Tổng dung lượng truyền tải cho 1 frame: **~26.5 KB**.
- Băng thông upload cần thiết cho 1 camera chạy ở 25 FPS:
  26.5 KB * 25 FPS = 662.5 KB/s = **5.3 Mbps**.

**Đánh giá khả năng đáp ứng:**
- **Mạng Wi-Fi nội bộ (5GHz)**: Cực kỳ nhẹ nhàng. Băng thông **5.3 Mbps** chỉ chiếm khoảng **2%** năng lực của đường truyền Wi-Fi trong nhà.
- **Ý nghĩa**: Với độ phân giải 640x640, bạn có thể truyền liên tục cả ảnh lẫn metadata ở tốc độ 25 FPS mà không gặp bất kỳ trở ngại nào về băng thông mạng cục bộ.

---

## III. Sức Nặng Của Python 3.8 Và Rủi Ro Quá Nhiệt (Thermal Throttling)

Do bạn đã **kích hoạt chế độ nguồn tối đa 10W (MAXN)** và **khóa xung nhịp cao nhất (jetson_clocks)**, hiệu năng cơ sở của hệ thống ban đầu sẽ đạt mức tối đa. Tuy nhiên, khi **tạm thời không tính tới hiệu quả của quạt tản nhiệt**, rủi ro quá nhiệt (Thermal Throttling) sẽ xảy ra rất nhanh khi chạy liên tục.

### 1. Hiệu Năng Đỉnh Ban Đầu (Khi Chip Còn Mát < 70°C)

Khi mới khởi động và chip chưa bị nóng, xung nhịp CPU được giữ ở mức 1.43 GHz và GPU ở 921 MHz:
- **YOLOv8n Inference (TensorRT FP16)**: Đạt ổn định **~25 ms**.
- **Đọc khung hình và tiền xử lý OpenCV**: **~5 ms**.
- **Nén JPEG CPU và JSON Serialization (Python 3.8)**: **~5 ms**.
- **Thời gian block I/O truyền tin mạng LAN**: **~8 ms**.

**Đánh giá tốc độ xử lý ban đầu:**
*   **Ở chế độ Đơn luồng tuần tự**: Tổng thời gian xử lý 1 frame là $5 + 25 + 5 + 8 = \mathbf{43\text{ ms}} \implies$ Đạt tốc độ **~23 FPS** (khá mượt).
*   **Ở chế độ Đa luồng bất đồng bộ (Async Threaded Worker)**: Giải phóng thời gian block I/O của luồng chính $\implies T_{\text{main}} = 5\text{ms (Đọc)} + 25\text{ms (AI)} + 5\text{ms (MQTT)} = \mathbf{35\text{ ms}} \implies$ Đạt tối đa **28.5 FPS**.

---

### 2. Sự Suy Giảm Hiệu Năng Thực Tế Do Quá Nhiệt (Không Có Quạt Chủ Động)

Khi chạy nhận dạng liên tục 23 - 28 FPS, GPU và CPU của Jetson Nano hoạt động gần hết công suất. Không có quạt tản nhiệt, nhiệt độ chip sẽ nhanh chóng vượt qua ngưỡng **75°C** chỉ sau **3 - 5 phút** hoạt động.

Lúc này, cơ chế an toàn phần cứng của Jetson sẽ tự động hạ xung nhịp CPU và GPU xuống mức thấp nhất để tự làm mát. Hiệu năng thực tế sẽ bị kéo sụt nghiêm trọng:

| Tác vụ | Trạng thái mát đầu tiên (< 70°C) | Trạng thái quá nhiệt (> 75°C - Throttling) |
|---|---|---|
| **YOLOv8n Inference (TensorRT FP16)** | ~25 ms | **~50 - 65 ms** (Xung GPU bị giảm) |
| **Đọc khung hình & xử lý OpenCV** | ~5 ms | **~12 ms** |
| **Nén JPEG CPU & JSON Serialize** | ~5 ms | **~15 ms** (Xung CPU bị giảm) |
| **Thời gian block I/O (MinIO + MQTT)** | ~8 ms | **~15 ms** |
| **Tổng thời gian xử lý 1 frame** | **~43 ms** | **~92 - 107 ms** |
| **FPS thực tế đạt được** | **~23.2 FPS** | **~9.3 - 10.8 FPS** |

*   **Hậu quả**: Khi không có quạt tản nhiệt chủ động bảo vệ, sau vài phút chạy thử, FPS của bản demo sẽ tự động tụt sâu xuống **dưới 10 FPS**. Ở tốc độ này, monitor hiển thị box trên Laptop sẽ bị giật lắc nghiêm trọng, và bộ tracker bắt đầu mất dấu xe liên tục (nhảy ID).

---

## IV. Phân Tích Cơ Chế Đa Luồng (Multi-threading) Trên Jetson Nano

Để hiểu tại sao cần đa luồng và **đa luồng thực sự xử lý cái gì**, chúng ta cần so sánh luồng công việc giữa kiến trúc đơn luồng tuần tự và đa luồng bất đồng bộ.

### 1. Pipeline Đơn Luồng (Single-Thread) Bị Nghẽn Bởi Tác Vụ I/O & CPU Nén Ảnh
Trong thiết kế đơn luồng, Jetson Nano xử lý tuần tự từng bước cho mỗi khung hình (Frame):
```text
[Đọc Frame] ──> [Inference YOLO] ──> [Bộ Lọc] ──> [Nén JPEG] ──> [Upload MinIO (Mạng)] ──> [Gửi MQTT (Mạng)]
  (5 ms)           (25 ms)            (2 ms)        (3 ms)           (5 ms - Chờ phản hồi)       (5 ms - Chờ PUBACK)
```
- **Vấn đề**: Trong thời gian Jetson Nano nén JPEG (tốn CPU) và tải ảnh lên MinIO hoặc chờ phản hồi xác nhận gửi từ MQTT (tốn I/O mạng), **luồng chính bị đóng băng (Blocked)**. Camera vẫn tiếp tục truyền frame mới nhưng Jetson không thể đọc, dẫn đến việc rớt khung hình (Frame Drop) và FPS thực tế bị giảm xuống còn 15-23 FPS.

---

### 2. Pipeline Đa Luồng Chia Tách Trách Nhiệm (Multi-threaded Pipeline)
Chúng ta chia nhỏ hệ thống thành hai luồng chạy song song độc lập, giao tiếp với nhau qua một hàng đợi RAM (**Thread-safe Queue**):

```text
LUỒNG CHÍNH (Inference Thread) - Chạy ở tốc độ tối đa (25-30 FPS)
[Đọc Frame] ──> [Inference YOLO] ──> [Gửi MQTT Tọa Độ Nhẹ] ──> [Đẩy Frame + Metadata vào Queue RAM]
                                                                        │
                                                                        ▼
                                                             [ Hàng Đợi (Queue RAM) ]
                                                                        │
                                                                        ▼
LUỒNG PHỤ (Worker / I/O Thread) - Chạy ngầm (Background)
                                            [Lấy từ Queue] ──> [Nén JPEG] ──> [Upload MinIO]
```

#### A. Luồng chính (Inference Thread) xử lý những gì?
- **Nhiệm vụ**: Chỉ làm các tác vụ cực kỳ nhanh để giữ FPS cao nhất:
  1. Đọc frame từ RTSP.
  2. Inference mô hình YOLOv8n TensorRT trên GPU.
  3. Gửi tin nhắn MQTT thô siêu nhẹ (chỉ chứa tọa độ JSON, không kèm ảnh) sang Laptop để Laptop vẽ bounding box ngay lập tức lên giao diện monitor.
  4. Nếu bộ lọc Active Learning kích hoạt (cần lưu ảnh khó): Copy khung hình trên RAM và đẩy vào Queue.
- **Thời gian xử lý**: Chỉ tốn khoảng **30 - 35ms** $\implies$ Không bao giờ bị block, đảm bảo luồng Live Tracking trên Laptop hiển thị mượt mà liên tục ở 25-30 FPS.

#### B. Luồng phụ (Worker / I/O Thread) xử lý những gì?
- **Nhiệm vụ**: Chuyên xử lý các tác vụ nặng, chậm và dễ bị nghẽn mạng:
  1. Lắng nghe và lấy ảnh từ Queue RAM khi Luồng chính đẩy vào.
  2. Nén ảnh sang JPEG (`cv2.imencode`).
  3. Kết nối mạng cục bộ để tải ảnh JPEG lên MinIO Server.
  4. Sau khi tải ảnh thành công, cập nhật trạng thái hoặc gửi link ảnh lên Server để lưu trữ MLOps.
- **Ý nghĩa**: Dù mạng Wi-Fi cục bộ có bị chập chờn hay MinIO phản hồi chậm (tốn 100ms), luồng chính vẫn chạy mượt ở 30 FPS. Chỉ có ảnh lưu trữ trên MinIO bị trễ nhẹ vài mili-giây, hoàn toàn không ảnh hưởng đến trải nghiệm người xem.

#### C. Giải phóng GIL (Global Interpreter Lock) trong Python 3.8
Mặc dù Python có cơ chế GIL (chỉ cho phép 1 luồng CPU chạy mã Python tại một thời điểm), đa luồng ở đây vẫn hoạt động rất hiệu quả vì:
- Khi chạy nhận diện YOLO (gọi thư viện C++/TensorRT trên GPU), Python sẽ **nhả GIL**.
- Khi OpenCV nén JPEG (`cv2.imencode` chạy bằng thư viện C++ tối ưu), Python cũng **nhả GIL**.
- Khi luồng phụ thực hiện gửi nhận dữ liệu qua Socket mạng (đợi MinIO upload), Python tiếp tục **nhả GIL**.
- Do đó, hai luồng này có thể chạy song song thực tế trên các nhân CPU khác nhau của Jetson Nano mà không bị GIL cản trở.

---

## V. Rủi Ro Bộ Nhớ Khi Không Sử Dụng Swap (Strict RAM Limit = 4GB)

Vì hệ thống **không sử dụng Swap**, việc quản lý bộ nhớ RAM vật lý 4GB trên Jetson Nano là yếu tố sống còn để tránh bị crash tiến trình do trình diệt tiến trình thiếu bộ nhớ của Linux (**OOM - Out Of Memory Killer**).

### 1. Phân bổ dung lượng RAM của hệ thống (Ước lượng)
- **Hệ điều hành OS (Ubuntu 18.04) & Dịch vụ nền**: chiếm khoảng **~800 MB - 1 GB** (nếu chạy giao diện GUI Desktop).
- **Bộ nạp Python 3.8 & các thư viện cơ bản**: chiếm khoảng **~200 MB**.
- **PyTorch/TensorRT Runtime & CUDA memory allocation**: chiếm khoảng **~1.2 GB - 1.5 GB** khi khởi tạo mô hình YOLOv8n.
- **Bộ nhớ đệm camera/RTSP (OpenCV frame buffer)**: chiếm khoảng **~150 MB**.
- **Bộ nhớ RAM Queue cho đa luồng**:
  - Mỗi ảnh 640x640x3 dạng numpy array thô trên RAM tốn khoảng:
    $$640 \times 640 \times 3 \text{ bytes} \approx 1.22 \text{ MB/frame}$$
  - Nếu giới hạn hàng đợi ở mức thấp (ví dụ: `maxsize = 15`), lượng RAM tiêu thụ tối đa chỉ khoảng **~18.3 MB**.
- **Tổng dung lượng RAM tiêu thụ dự kiến**: Khoảng **~2.4 GB - 3.0 GB**.

*   **Đánh giá**: Mức tiêu thụ nằm sát ngưỡng giới hạn 4GB. Nếu bạn chạy thêm các tiến trình khác trên Jetson (như trình duyệt web, IDE Code, hoặc stream nhiều camera đồng thời), RAM sẽ bị tràn ngay lập tức và Linux sẽ tự động gửi tín hiệu `Kill (Exit Code 137)` để đóng app Python.

---

### 2. Các giải pháp tối ưu bộ nhớ bắt buộc khi chạy Không Swap

Để đảm bảo chương trình không bị OOM Killer dừng hoạt động giữa chừng:

1. **Chạy Jetson ở chế độ Headless (Tắt GUI Desktop)**:
   Tắt giao diện đồ họa của hệ điều hành sẽ giúp giải phóng ngay lập tức **~500 MB - 800 MB RAM** vật lý để cấp cho Python:
   ```bash
   sudo systemctl set-default multi-user.target # Chuyển sang chế độ gõ lệnh (Headless)
   # reboot lại để áp dụng
   ```
   *(Để bật lại GUI khi cần: `sudo systemctl set-default graphical.target`)*.
2. **Cấu hình hàng đợi RAM Queue cực kỳ chặt chẽ (`maxsize = 10` hoặc `15`)**:
   - Tuyệt đối không để `maxsize` quá lớn (ví dụ 100 hay 150). Nếu mạng bị mất kết nối tạm thời, hàng đợi tích lũy quá nhiều frame ảnh thô sẽ làm cạn kiệt RAM rất nhanh.
   - Khi Queue bị đầy (`maxsize=10`), luồng chính sẽ tạm thời block việc đẩy ảnh khó mới vào Queue (chỉ tiếp tục gửi MQTT metadata nhẹ) để tự bảo vệ RAM.
3. **Giải phóng RAM chủ động trong code Python**:
   - Sau khi luồng phụ lấy ảnh từ Queue và nén xong, hoặc gửi xong, hãy sử dụng từ khóa `del` để giải phóng biến và gọi `gc.collect()` định kỳ để Python dọn dẹp RAM ngay lập tức.
     ```python
     import gc
     
     # Sau khi upload MinIO thành công
     del frame_copy
     gc.collect()
     ```
