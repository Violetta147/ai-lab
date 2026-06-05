# Kế hoạch cấu hình tự động CVAT (CVAT Automation Plan)

Kế hoạch này tập trung vào việc khởi tạo Project/Cloud Storage tự động cho CVAT và tích hợp với code mới nhất từ repository `data_pipeline`, nơi đã giải quyết vấn đề network (`mlops_traffic_net`) thông qua submodule `cvat` mới cập nhật.

## User Review Required

> [!IMPORTANT]
> - Hệ thống đã ghi nhận các commit mới của bạn (bao gồm `chore: bump cvat submodule for alerts and mlops network` và hardening CVAT client).
> - Vấn đề Network và tự động tạo MinIO buckets đã được xử lý trong code base mới. Chúng ta **KHÔNG CẦN** (và không nên) chỉnh sửa file `docker-compose.yml` của CVAT bằng tay nữa để tránh conflict với submodule.
> - Kế hoạch giờ đây sẽ chỉ tập trung vào việc fetch code mới nhất, build lại các container bị ảnh hưởng, và khởi tạo các thiết lập CVAT (Project, Cloud Storage, lấy ID) nếu code pipeline hiện tại chưa tự động hóa phần này.

## Open Questions

> [!WARNING]
> - Code mới (`harden CVAT client`) đã bao gồm tính năng **tự động tạo CVAT Project và Cloud Storage** chưa, hay vẫn cần một file script riêng biệt (vd `setup_cvat_env.py`) để làm việc này một lần lúc ban đầu? Tôi sẽ giữ phần tạo script này trong kế hoạch như một giải pháp dự phòng an toàn.

## Proposed Changes

---

### Môi trường & Codebase (Infrastructure Layer)

Cập nhật code và khởi động lại các thành phần với cấu hình network mới.

#### [MODIFY] Khởi tạo Git Submodule & Cập nhật Docker
- Pull code mới nhất, đảm bảo chạy lệnh `git submodule update --init --recursive` thành công để lấy thư mục `cvat` mới nhất.
- Chạy lại các container với `docker-compose up -d --build` ở cả `core-backbone` và `cvat` (nếu cần thiết) để nhận cấu hình mạng `mlops_traffic_net`.

#### [MODIFY] `d:\datas\Final.yolov8\.env`
- Tạo/Cập nhật các thông số ID cho CVAT để pipeline có thể sử dụng:
  - `CVAT_PROJECT_ID`
  - `CVAT_CLOUD_STORAGE_ID`

---

### Khởi tạo Resource Tự Động (Auto-Provisioning)

Nếu codebase mới chưa tự động tạo project, chúng ta sẽ chạy một script cấu hình 1 lần.

#### [NEW] `d:\datas\Final.yolov8\data_pipeline\setup_cvat_env.py`
- Viết bằng Python sử dụng thư viện `requests`.
- **Nhiệm vụ:**
  1. Đăng nhập CVAT bằng `admin:admin`.
  2. Tạo service account `django:Rmr2612+` (nếu chưa có).
  3. Tạo Project `Traffic Detection` với các label cần thiết. Lấy ID.
  4. Tạo Cloud Storage `minio_raw_data` liên kết trực tiếp `http://minio:9000` với bucket `raw-data`. Lấy ID.
  5. Cập nhật thẳng `CVAT_PROJECT_ID` và `CVAT_CLOUD_STORAGE_ID` vào file `.env` của pipeline.

## Verification Plan

### Manual Verification
- Xác nhận submodule `cvat` đã trỏ đúng version và folder không còn trống.
- Chạy thử `python data_pipeline/setup_cvat_env.py` (nếu cần).
- Mở UI CVAT để xác nhận: user `django` đã được tạo, Project đã có, Cloud Storage đã được kết nối (trạng thái xanh lá).
- Restart pipeline `docker restart pipeline-worker-1`.
- Kiểm tra log pipeline xem lỗi `404` đã biến mất, CVAT kết nối thành công và data được push lên UI.
