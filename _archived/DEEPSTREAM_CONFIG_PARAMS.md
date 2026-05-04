# Từ Điển Toàn Tập Tham Số Cấu Hình DeepStream
*(File này thống kê CHI TIẾT TOÀN BỘ các tham số (parameters) đã được sử dụng trong hệ thống mã nguồn `setup_deepstream_jetson.sh` của bạn. Dùng làm phụ lục tra cứu cho đồ án.)*

---

## 1. Các Biến Môi Trường (Environment Variables)
*Các thông số này được nạp bằng Bash script trên cùng để tùy biến nhanh hệ thống mà không cần chạm vào Lõi C/C++.*

| Biến (Variable) | Ý nghĩa (Description) | Ví dụ Tối ưu trong Đồ án |
| :--- | :--- | :--- |
| `LAPTOP_RTSP_URI` | Địa chỉ IP RTSP của máy trạm phát hình gốc (MediaMTX Laptop). | `rtsp://192.168.1.154:8554/...` |
| `JETSON_RTSP_PORT` | Số Port để xuất luồng Video Result trả ngược lại từ Jetson. | `8555` |
| `PRE_CLUSTER_THRESHOLD` | Ngưỡng độ tin cậy (Confidence) tối thiểu để giữ lại một nhận diện của AI. | `0.25` (Lọc rác, nhưng bắt nhạy xe) |
| `NMS_IOU_THRESHOLD` | Ngưỡng độ gộp chéo (Intersection Over Union). Chống vẽ đè 2 box lên cùng 1 xe. | `0.45` |
| `INFER_INTERVAL` | Ép GPU nghỉ ngơi, chỉ chạy AI Nhanh mỗi N frame. Đỡ nghẽn VRAM. | `1` (Nghĩa là quét AI 1 frame, nghỉ 1 frame) |
| `STREAMMUX_WIDTH/HEIGHT` | Độ phân giải của khung hình trước khi nhồi (mux) vào ống AI TensorRT. | `640x480` (Downscale để cứu Jetson Nano) |
| `TRACKER_TYPE` | Chọn thuật toán bám đuôi đối tượng. | `nvdcf` (Cao cấp nhất, bám ID tốt nhất) |
| `LC_X1, LC_Y1, LC_X2, LC_Y2` | Tọa độ Tuyệt đối tạo thành một Vạch Cản (màu Xanh trên màn hình). | `LC_Y=420` (Nằm sát máy quay) |
| `LC_DX1, LC_DY1...` | Tọa độ Tuyệt đối của Mũi tên Vector góc. Định nghĩa hướng đếm xe. | Vector chĩa xuống (Downwards) |

---

## 2. Thông Số Lõi Ống Kính AI (Config Infer Primary - YOLOv8)
*Cấu hình file `config_infer_primary.txt` kiểm soát mạng TensorRT và Lớp Custom Parser OSD.*

| Tham Số Lõi | Ý nghĩa (Description) | Ví dụ Tối ưu trong Đồ án |
| :--- | :--- | :--- |
| `custom-network-config` | Đường dẫn tới file trọng số AI YOLO chưa biên dịch. | `yolov8n.cfg` |
| `model-engine-file` | Đường dẫn bản AI đã nén biên dịch riêng (Hardware-specific). | `yolov8n_b1_gpu0_fp16.engine` (Ép chạy Float16 x2 tốc độ) |
| `network-type` | Phân loại Neural Network. | `0` (Object Detection - Nhận diện Vật thể) |
| `num-detected-classes`| Tổng số Class vật thể cần nhận dạng. | `4` (Car, Bus, Truck, Motor) |
| `interval` | Thông số kỹ thuật kéo từ `INFER_INTERVAL`. | `1` |
| `network-mode` | Chế độ tính toán số học. | `2` (Ép kiểu FP16/INT8 thay vì 32-bit tốn RAM) |
| `parse-bbox-func-name`| Khai báo hàm C/C++ để đọc vị trí từ mảng số của TensorRT. | `NvDsInferParseYolo` |
| `custom-lib-path` | Thư viện dịch mã YOLO (Do Nvds không build sẵn YOLO). | `libnvdsinfer_custom_impl_Yolo.so` |
| `border-color` | Nằm sâu trong `[class-attrs-0]`. Xâm nhập và Override màu OSD BoundingBox. | `0.0;1.0;0.0;1.0` (Hệ màu Float RGBA) |

---

## 3. Khối Theo Dõi Vết Cấp Cao (NvTracker)
*Cấu hình quy định sức mạnh của con mắt nhúng bắt dính các vật thể khi chúng di chuyển hoặc che khuất (Occlusion).*

| Tham Số Tracker | Ý nghĩa (Description) | Chú giải / Ứng dụng |
| :--- | :--- | :--- |
| `tracker-width` | Kích thước rổ phân lớp cho GPU vẽ điểm tụ. Ảnh hưởng trực tiếp hiệu năng. | `640` (Bằng Mux Width) |
| `tracker-height` | Phải luôn là bội số chia hết cho 32. | `384` |
| `ll-lib-file` | Thư viện chứa logic mã C++ của thuật toán lõi hệ thống bám ID. | Thay đổi thư viện Tracker (`IOU/NvSort/NvDCF`). Chúng ta chỉ định xài bản `nvmultiobjecttracker.so`. |
| `ll-config-file`| Truy xuất cấu hình tính điểm rác riêng của Tracker NvDCF. | Kéo về `config_tracker_NvDCF_perf.yml` để tăng max FPS. |

---

## 4. Bơm Xử Lý Toán Học và Phân Tích (NvDsAnalytics)
*Cấu hình khai báo trong `config_nvdsanalytics.txt`.*

| Tham số Phân tích | Ý nghĩa (Description) | Ứng dụng đặc thù |
| :--- | :--- | :--- |
| `enable` | Cờ công tắc bật tắt Module tính toán đồ họa toán học (Logic đếm xe). | `1` (Bật) |
| `line-crossing-Entry`| Tích hợp nhét nguyên dàn tham số (Vector chéo + Vạch ngang) vào chuỗi String C++. | Theo chuỗi quy luật NVIDIA yêu cầu. |
| `class-id` | Ép vạch ngang này chỉ được đếm một số loại xe duy nhất. | `-1` (Nghĩa là đếm tất cả mọi thứ băng qua vạch) |
| `mode` | Quy định mức độ khắt khe về góc độ của chiếc xe khi cắt qua vạch so với Vector hướng (Direction). | `loose` (Chống trượt khung đếm cực mạnh cho xe xéo làn). |
| `display-font-size` | Cỡ chữ cái biến OSD In-Screen. | `12` |

---

## 5. Khối Dây Chuyền Ống Cứng (Master Pipeline App Config)
*Nối tất cả các khối trên gộp thành 1 mạng kiến trúc Node bằng Graph Architecture GStreamer (`deepstream_app_config.txt`).*

| Pipeline Plugin Block | Các Tham số quan trọng bên trong Khối Nhánh Thẻ |
| :--- | :--- |
| **`[source0]`** | `type=4` (RTSP Đầu vào). `cudadec-memtype=0`: Giữ VRAM, cấm CPU Copy dữ liệu giải mã (Sức mạnh Cốt lõi của Zero-Copy). |
| **`[streammux]`** |  `batched-push-timeout`: Độ thả trễ (Microsecond) gom frame bắt AI phải tự đùn Data đi nếu mạng bị delay packet. |
| **`[osd]`** | `process-mode=1` hoặc `0`: Ép vẽ chữ và hộp đồ họa bằng Card màn hình (GPU) hoặc ép chuyển giao xử lý chữ sang VIC/CPU để làm mịn Front. |
| **`[sink0]`** | Nhồi luồng ra. `type=4` (RTSP out). Gọi khối phần cứng NVENC `enc-type=0` (H.264) để giải nén UDP Bitrate cực thấp, bắn thẳng về Laptop không trễ mạng. |
