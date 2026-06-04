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
- **Ý nghĩa**: Với độ phân giải 640x640, bạn có thể truyền liên tục cả ảnh lẫn metadata ở tốc độ 23-25 FPS thực tế mà không gặp bất kỳ trở ngại nào về băng thông mạng cục bộ.

---

## III. Sức Nặng Hệ Thống Và Rủi Ro Quá Nhiệt (Thermal Throttling)

Do bạn đã **kích hoạt chế độ nguồn tối đa 10W (MAXN)** và **khóa xung nhịp cao nhất (jetson_clocks)**, hiệu năng cơ sở của hệ thống ban đầu sẽ đạt mức tối đa. Tuy nhiên, khi **tạm thời không tính tới hiệu quả của quạt tản nhiệt**, rủi ro quá nhiệt (Thermal Throttling) sẽ xảy ra rất nhanh khi chạy liên tục.

### 1. Hiệu Năng Thực Tế Ban Đầu (Khi Chip Còn Mát < 70°C)

*   **Hiệu năng trần thực tế (Practical Ceiling)**: Khi chạy pipeline thực tế (ví dụ: DeepStream hoặc OpenCV tuần tự kết hợp I/O), hiệu năng tối đa đạt được trên Jetson Nano là **~23 FPS** (tương đương ~43 ms cho mỗi khung hình).
*   **Nguyên nhân giới hạn ở 23 FPS**: Mặc dù thời gian chạy mô hình TensorRT FP16 chỉ mất ~25 ms, việc giải mã video (Video Decoding), chuyển đổi hệ màu, co giãn kích thước ảnh (resizing) cùng với chi phí đồng bộ hóa bộ nhớ giữa CPU và GPU (Unified Memory Bus overhead) đã tiêu tốn thêm ít nhất 15-18 ms, giới hạn tần số xử lý tối đa ở 23 FPS ngay cả khi đã bất đồng bộ hóa hoàn toàn I/O mạng.

### 2. Sự Suy Giảm Hiệu Năng Thực Tế Do Quá Nhiệt (Không Có Quạt Chủ Động)

Khi chạy nhận dạng liên tục ở mức trần 23 FPS, GPU và CPU của Jetson Nano hoạt động gần hết công suất. Không có quạt tản nhiệt, nhiệt độ chip sẽ nhanh chóng vượt qua ngưỡng **75°C** chỉ sau **3 - 5 phút** hoạt động.

Lúc này, cơ chế an toàn phần cứng của Jetson sẽ tự động hạ xung nhịp CPU và GPU xuống mức thấp nhất để tự làm mát. Hiệu năng thực tế sẽ bị kéo sụt nghiêm trọng:

| Tác vụ | Trạng thái mát đầu tiên (< 70°C) | Trạng thái quá nhiệt (> 75°C - Throttling) |
|---|---|---|
| **YOLOv8n Inference (TensorRT FP16)** | ~25 ms | **~50 - 65 ms** (Xung GPU bị giảm) |
| **Đọc khung hình & xử lý OpenCV** | ~5 ms | **~12 ms** |
| **Nén JPEG CPU & JSON Serialize** | ~5 ms | **~15 ms** (Xung CPU bị giảm) |
| **Thời gian block I/O (MinIO + MQTT)** | ~8 ms | **~15 ms** |
| **Tổng thời gian xử lý 1 frame** | **~43 ms** | **~92 - 107 ms** |
| **FPS thực tế đạt được** | **~23.0 FPS (Giới hạn thực tế)** | **~9.3 - 10.8 FPS** |

*   **Hậu quả**: Khi không có quạt tản nhiệt chủ động bảo vệ, sau vài phút chạy thử, FPS của bản demo sẽ tự động tụt sâu xuống **dưới 10 FPS**. Ở tốc độ này, monitor hiển thị box trên Laptop sẽ bị giật lắc nghiêm trọng, và bộ tracker bắt đầu mất dấu xe liên tục (nhảy ID).

---

## IV. Phân Tích Cơ Chế Đa Luồng (Multi-threading) Trên Jetson Nano

### 1. Thiết Kế Hệ Thống Đa Luồng Với Đệm Cục Bộ (3-Thread Local Buffer Architecture)
Để giải quyết triệt để nguy cơ hệ thống bị treo hoặc sụt giảm FPS khi xảy ra nghẽn mạng/mất mạng, chúng ta cấu trúc chương trình thành 3 luồng chạy song song hoàn toàn độc lập:

```text
 ┌────────────────────────────────────────────────────────┐
 │ 1. LUỒNG CHÍNH (Main / Inference Thread)                │  <-- Giữ FPS tối đa (~23 FPS)
 │    [Đọc Frame] ──> [Inference YOLO] ──> [Chạy Bộ Lọc]  │
 └──────────────────────────┬─────────────────────────────┘
                            │ (Chỉ khi Active Learning kích hoạt)
                            ▼
                 [ Hàng Đợi RAM (Queue) ] (maxsize = 10)
                            │
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │ 2. LUỒNG GHI ĐĨA (Local Disk Writer Thread)            │  <-- Không phụ thuộc vào mạng
 │    [Nén JPEG] ──> [Ghi File JPEG & JSON ra .\buffer]   │
 └──────────────────────────┬─────────────────────────────┘
                            │ (Lưu trữ an toàn trên Jetson SD/SSD)
                            ▼
                  [ Thư mục .\buffer ]
                            │
                            ▼ (Quét đồng bộ ngầm khi có mạng)
 ┌────────────────────────────────────────────────────────┐
 │ 3. LUỒNG ĐỒNG BỘ (Background Sync Thread)              │  <-- Xử lý bất đồng bộ
 │    [Đọc file] ──> [Upload MinIO] ──> [Gửi MQTT] ──> [Xóa]│
 └────────────────────────────────────────────────────────┘
```

#### A. Luồng chính (Inference Thread) - Đảm bảo hiệu năng thời gian thực
- **Nhiệm vụ**: Chỉ làm các tác vụ tính toán cực kỳ nhanh để giữ FPS cao nhất:
  1. Đọc frame từ nguồn RTSP giả lập.
  2. Inference mô hình YOLOv8n TensorRT trên GPU.
  3. Kiểm tra các bộ lọc Active Learning và Rule OOD.
  4. Nếu có phát hiện cần lưu: Copy khung hình trên RAM và đẩy phi chặn (non-blocking) vào Hàng Đợi RAM (`Queue`).
  5. Gửi telemetry realtime siêu nhẹ (chỉ chứa tọa độ JSON, không kèm ảnh) qua MQTT lên Laptop.
- **Cơ chế chống block**: MQTT client trên luồng này được khởi chạy bằng vòng lặp bất đồng bộ (`loop_start()`) và gửi tin nhắn với mức `QoS = 0`. Khi mạng bị nghẽn hoặc mất kết nối, lệnh publish sẽ trả về ngay lập tức chứ không chặn luồng chính.

#### B. Luồng ghi đĩa (Local Disk Writer Thread) - Tránh nghẽn hàng đợi RAM
- **Nhiệm vụ**: Giải phóng hàng đợi RAM nhanh nhất có thể bằng cách làm việc hoàn toàn với lưu trữ cục bộ:
  1. Lắng nghe và lấy các phần tử (Frame + Metadata thô) từ RAM Queue.
  2. Nén frame sang JPEG (`cv2.imencode`) bằng CPU.
  3. Ghi trực tiếp file ảnh JPEG và file metadata JSON tương ứng vào thư mục cục bộ `.\buffer` trên Jetson.
- **Ý nghĩa**: Vì ghi trực tiếp lên bộ nhớ SSD/thẻ nhớ của Jetson cực kỳ nhanh và không phụ thuộc vào trạng thái mạng, hàng đợi RAM sẽ được giải phóng ngay lập tức. Ngay cả khi mất mạng hoàn toàn, RAM Queue không bao giờ bị đầy hay block ngược lại luồng chính.

#### C. Luồng đồng bộ ngầm (Background Sync Thread) - Đồng bộ dữ liệu bất đồng bộ
- **Nhiệm vụ**: Tự động đồng bộ các file trong thư mục `.\buffer` lên Server khi có mạng:
  1. Chạy ngầm theo chu kỳ định kỳ (ví dụ mỗi 2 - 5 giây).
  2. Quét thư mục `.\buffer`. Nếu phát hiện file chưa đồng bộ, tiến hành upload ảnh lên MinIO và gửi JSON lên MQTT.
  3. Sau khi upload và gửi thành công, tiến hành xóa các file local tương ứng.
- **Cơ chế tự phục hồi**: Nếu gặp lỗi kết nối (mất mạng, MinIO/MQTT Server không phản hồi), luồng này sẽ ghi nhận lỗi, sleep lâu hơn (ví dụ 5-10 giây) và bỏ qua chu kỳ hiện tại. Dữ liệu vẫn được giữ an toàn tại local và sẽ được đồng bộ lại ở chu kỳ tiếp theo khi mạng ổn định.

#### D. Giải phóng GIL (Global Interpreter Lock) trong Python 3.8
Mặc dù Python có cơ chế GIL (chỉ cho phép 1 luồng CPU chạy mã Python tại một thời điểm), kiến trúc 3 luồng này hoạt động cực kỳ hiệu quả trên Jetson Nano (4 nhân CPU) vì:
- Khi chạy nhận diện YOLO (gọi thư viện C++/TensorRT trên GPU), Python sẽ **nhả GIL**.
- Khi OpenCV nén JPEG (`cv2.imencode` chạy bằng thư viện C++ tối ưu), Python cũng **nhả GIL**.
- Khi luồng ghi đĩa thực hiện I/O ghi file và luồng đồng bộ thực hiện I/O mạng (MinIO/MQTT), Python tiếp tục **nhả GIL**.
- Do đó, các tác vụ này có thể song song hóa thực tế trên nhiều nhân CPU khác nhau.

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
   - Mặc dù Luồng ghi đĩa cục bộ dọn hàng đợi cực nhanh, việc giới hạn `maxsize` ở mức thấp là bắt buộc để ngăn chặn tích tụ RAM trong trường hợp tốc độ ghi đĩa gặp sự cố phần cứng đột xuất.
   - Khi Queue bị đầy (`maxsize=10`), luồng chính sẽ tạm thời bỏ qua (drop) việc đẩy ảnh mới vào Queue để bảo vệ an toàn cho dung lượng RAM (tránh OOM Killer).

3. **Cơ chế bảo vệ dung lượng đĩa đệm cục bộ (Local Disk Safety Limit)**:
   - Trong trường hợp mất mạng kéo dài, thư mục `.\buffer` sẽ liên tục tích lũy file và có nguy cơ làm đầy ổ đĩa của Jetson.
   - Cần triển khai cơ chế kiểm tra dung lượng thư mục `.\buffer` định kỳ (ví dụ: tối đa 500MB hoặc 1GB). Khi vượt quá giới hạn an toàn này, hệ thống sẽ tạm thời ngừng ghi file mới vào đĩa cho đến khi kết nối mạng được khôi phục và luồng đồng bộ dọn bớt thư mục đệm.
3. **Giải phóng RAM chủ động trong code Python**:
   - Sau khi luồng phụ lấy ảnh từ Queue và nén xong, hoặc gửi xong, hãy sử dụng từ khóa `del` để giải phóng biến và gọi `gc.collect()` định kỳ để Python dọn dẹp RAM ngay lập tức.
     ```python
     import gc
     
     # Sau khi upload MinIO thành công
     del frame_copy
     gc.collect()
     ```
