# Dàn ý Báo cáo Đồ án: Hệ thống Nhận diện và Đếm Xe Real-time với DeepStream trên Edge Device (Jetson Nano)

Bản báo cáo này được thiết kế theo tư duy giải quyết vấn đề (Problem-Solving) và Kỹ thuật Hệ thống (Systems Engineering), giúp Giảng viên thấy được cái nhìn tổng quan về kiến trúc và năng lực làm chủ hệ thống thay vì sa đà vào các dòng code cấu hình.

---

## 1. Đặt vấn đề (Problem Statement)
* **Bối cảnh:** Việc áp dụng AI vào phân tích giao thông theo thời gian thực (real-time) tại biên (Edge) đang là xu hướng. Tuy nhiên, các thiết bị Edge như Jetson Nano có giới hạn nghiêm ngặt về sức mạnh tính toán (CPU/GPU) và bộ nhớ.
* **Vấn đề cốt lõi:** Các pipeline xử lý video truyền thống (viết bằng Python/OpenCV bình thường) gặp giới hạn lớn về thắt cổ chai (bottleneck) giữa CPU và GPU. Dữ liệu liên tục phải copy qua lại giữa bộ nhớ chính và bộ nhớ đồ hoạ dẫn đến độ trễ cực lớn, rớt khung hình (drop frames) và không thể chạy Real-time.
* **Mục tiêu đề tài:** Thiết kế và tối ưu hoá một phần mềm pipeline GPU-to-GPU khép kín ứng dụng công nghệ NVIDIA DeepStream. Yêu cầu hệ thống phải nhận diện được đa phương tiện (YOLOv8), theo dõi vết liên tục (Tracking) và đếm lưu lượng xe chạy theo hướng cố định tự động với hiệu năng tối đa trên phần cứng giới hạn.

## 2. Tại sao chọn NVIDIA DeepStream so với Tự Code Python? (Why DeepStream?)
Chốt lại ở một từ: **Hiệu năng (Performance)**.

Việc tự ghép nối các thư viện (như OpenCV đọc frame + YOLO/TensorRT detect + ByteTracker) bằng Python rất tốt để R&D, nhưng khi deploy thực tế — đặc biệt là trên các thiết bị edge nhúng như dòng NVIDIA Jetson — DeepStream vượt trội hoàn toàn vì 3 lý do cốt lõi sau:

1. **Zero-copy Memory (Giải quyết tắc nghẽn bộ nhớ):** Tự code thường dính "nút thắt cổ chai" khi phải copy dữ liệu qua lại liên tục giữa RAM (CPU quản lý) và VRAM (GPU quản lý) trong từng phân đoạn. DeepStream giữ cấu trúc toàn bộ pipeline (Decode video -> Tiền xử lý -> YOLO Inference -> Tracking -> Vẽ OSD -> Encode) giới hạn hoàn toàn trên phần cứng GPU, giảm triệt để độ trễ.
2. **Tận dụng tối đa lõi phần cứng (Hardware Acceleration):** Pipeline DeepStream gọi trực tiếp vào các vi mạch phần cứng chuyên dụng của NVIDIA thay vì ép CPU làm việc cật lực: dùng NVDEC để giải mã luồng video, lõi Tensor (TensorRT) đỉnh cao để chạy AI Inference, và khối NVENC để nén/stream đầu ra. CPU gần như được giải phóng hoàn toàn và mát mẻ.
3. **Quản lý đa luồng (Multi-stream) cực mạnh:** Được xây dựng vững chắc trên nền tảng Dataflow GStreamer bằng C/C++, kiến trúc DeepStream có thể xử lý song song và mượt mà hàng chục luồng camera RTSP cùng lúc. Nếu tự code đa luồng bằng Python, lập trình viên sẽ rất dễ đụng tường rào GIL (Global Interpreter Lock) và làm crash / nghẽn đứng CPU.

## 3. Kiến trúc Giải pháp (Solution Architecture)
* **Luồng dữ liệu mạng (Network Flow):** 
  * Thay vì cắm trực tiếp camera (có thể gây thiếu ổn định phần cứng), hệ thống triển khai một máy chủ trung gian phần mềm **MediaMTX (RTSP Server)**. Laptop đóng vai trò truyền luồng video lên server thông qua giao thức TCP (đảm bảo chống thất thoát dữ liệu - Packet Loss).
  * Jetson Nano đóng vai trò là khối Edge AI, chỉ cần lấy luồng RTSP về để xử lý và đẩy luồng kết quả (kể cả metadata render hình) ngược trở lại cho phía Client xem.
* **Kiến trúc Pipeline lõi (DeepStream Framework):** Hệ thống xây dựng một luồng xử lý qua các Block chuyên biệt, tối ưu trên GPU GStreamer:
  1. `RTSP Source` & `Hardware Decode`: Nhận và giải mã H.264 trực tiếp trên nhân phần cứng thay vì CPU.
  2. `Streammux`: Gom luồng và cân bằng, chuẩn hóa độ phân giải làm đầu vào cho khâu CPT.
  3. `nvinfer (YOLOv8 TensorRT)`: Cốt lõi Engine AI dùng mô hình đã được tăng tốc bằng TensorRT (FP16/INT8) nhằm xử lý nhận diện vật thể siêu mịn, siêu tốc độ.
  4. `nvtracker (NvDCF)`: Block xử lý theo dõi hướng đi, ID của từng xe qua các chuỗi biến thiên thời gian.
  5. `nvdsanalytics`: Module phân tích logic cấp cao dựa trên toạ độ xe từ Tracker để tính toán vượt vạch/tác vụ đếm (Line-crossing).
  6. `nvdsosd` & `Sink`: Trích xuất Metadata thông tin và chèn vào lưới điểm ảnh (On-Screen-Display) và nén đưa ngược lại thành RTSP IP.

## 4. Các bài toán kỹ thuật hóc búa đã giải quyết (Key Challenges Solved)
Thay vì báo cáo quá trình suôn sẻ, phần này nhấn mạnh năng lực giải quyết các rào cản thực tế khi làm việc với hệ thống nhúng:

* **Bài toán 1: Tràn tải GPU (Bottleneck) gây sập hệ thống hoặc Video đóng băng:**
  * **Khó khăn:** Khi để cấu hình độ phân giải trung bình cao (720p hoặc 1080p), thiết bị Jetson Nano bị quá tải bộ đệm Streaming. Việc chạy NvDCF (Tracker dùng thuật toán GPU nặng) nuốt trọn tài nguyên dẫn đến mất hình và đứng Video stream hoàn toàn ở giữa luồng phân tích thuật toán.
  * **Giải quyết:** Bài toán cân bằng lại tài nguyên (Trade-off). Hạ độ phân giải nội bộ của luồng phân tích (Streammux) xuống mức 640x480 để tiết kiệm điểm ảnh (pixel) cần xử lý, đồng thời thiết lập `INFER_INTERVAL = 1` (chỉ kích hoạt bộ gie mạng Neural mỗi hai frame xen kẽ). Quá trình Tracking sẽ đảm nhiệm việc nội suy (interpolate) chuyển động ở các frame bị bỏ qua, hệ quả là video giữ mượt mà ở 30 FPS với cấu hình nhẹ bằng một nửa nhưng tỷ lệ chệch khung bằng không.
* **Bài toán 2: Hụt đếm xe và sai chệch hướng vượt vạch báo cáo (Flickering ID logic & Analytics Vectors):**
  * **Khó khăn:** Ban đầu việc đếm bị chập chờn dẫn tới sai số lưu lượng xe. Hệ thống dùng Tracker IO (nhẹ nhưng nhạy sóng AI). Khi AI lỡ bị nghẽn giật hình trong 1 vài giây đi qua vạch, chiếc xe bị rớt ID và mang trên mình 1 ID mới toanh. Do tính liên tục bị gãy, bộ đếm `nvdsanalytics` tự động xóa nhận diện xe tại vạch kẻ và đếm sai hướng.
  * **Giải quyết:** Can thiệp đổi sang Tracker hạng nặng là **NvDCF** để tận dụng độ bám dính siêu tinh tính theo hướng của chiếc xe (che khuất vẫn nhận ID). Đặc biệt mấu chốt, **tối ưu hóa vị trí vạch đếm OSD**: Đưa vạch đếm xuống điểm vàng Camera (Y=420) thay vì Y=350. Tại vị trí cận viễn điểm này kích thước chiếc Pixel/Xe lớn nhất, AI bắt tracking đạt độ chính xác lên đến 99,9% không thể bị lỗi đứt gãy. Cộng với thiết đặt nới mở biên độ hướng góc quét (`mode=loose`), chiếc xe chạy xiên mép đều được đếm đủ trúng số lượng.
* **Bài toán 3: Xung đột kiến trúc Render Box Labeling (Tính thẩm mỹ và UI UX OSD):**
  * **Khó khăn:** DeepStream quản trị màu sắc phần phân tầng hộp nhận diện rất sâu. Phần mềm tham chiếu cấu hình (App) ở ngoài không thể đè lên lớp thư viện AI (Inference layer) ở lõi. Hậu quả là màn hình xe báo đỏ toàn phần không có độ chia tách class hình xe theo tư duy của mô hình YOLOv8.
  * **Giải quyết:** Luồn lách API cấu hình, Mapping thuộc tính màu sắc trực tiếp dưới dạng số nguyên dấu phẩy động Float thẳng vào module Cấu hình lõi `[primary-gie]` của DeepStream, cho phép bóc tách màu từng lớp đa dạng (Bus, Car, Truck, Motor) xuyên lớp thư viện C/C++ nhằm mang lại kết quả UI cực kỳ thẩm mỹ và chuẩn nghiệp vụ đồ họa.

## 5. Hướng phát triển trong tương lai (Future Works)
* **Gia tăng năng lực đa biến cảnh cho AI:** Thu thập thêm dữ liệu (Data Augmentation & Real-world Data) tập trung ở các điều kiện ánh sáng ngoài trời đa dạng hơn (ban đêm, sương mù, mưa to) hoặc bị che khuất nặng (Heavy Occulsion) để Retrain phiên bản YOLOv8 mạnh mẽ hơn.
* **Mở rộng khả năng Đa luồng (Multi-stream Monitoring):** Nâng cấp cấp độ Pipeline DeepStream để xử lý Data-mining cùng lúc 2-4 luồng RTSP camera IP độc lập tại giao lộ, kiểm soát gánh tải toàn bộ nút nhờ số bước batch Size Pipeline của Engine TensorRT.
* **Tích hợp IoT Message Broker & Dashboard BI:** Triển khai thêm các Interface chuyên nghiệp IoT như Plugin `nvmsgconv` (Deepstream Data converter) và `nvmsgbroker` để bắn siêu dữ liệu phân tích (metadata) lượng lưu lượng đếm xe dạng thô JSON qua giao thức Kafka hoặc MQTT lên Server/Cloud đám mây, tiến tới hình thành một hệ sinh thái xây dựng biểu đồ thống kê Web Dashboard (Business Intelligence) phục vụ Cảnh sát giao thông quản lý tự động hoá thay vì chỉ nhìn vào luồng camera thủ công nhức mắt.
