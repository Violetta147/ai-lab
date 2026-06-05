# MQTT OTA Architecture & Data Flow Notes

## 1. Mục đích của các hàm TODO (subscribe, loop_start, loop_stop) trong Edge Server C++
Các hàm giả (stubs) và `TODO` trong `MqttClient` ban đầu được tạo ra để chuẩn bị cho tính năng **Cập nhật OTA (Over-The-Air)** và nhận lệnh điều khiển từ xa.

Trong Data Pipeline (Backend), file `data_pipeline/pipeline/utils/mqtt_handler.py` đã có sẵn logic gửi lệnh cập nhật model:
```python
def send_ota_update(self, camera_id, version, model_url):
    """Gửi lệnh cập nhật model xuống thiết bị qua MQTT."""
    topic = f"traffic/cmd/{camera_id}"
    # ...
```
Tuy nhiên, hiện tại **C++ Edge Server** chưa có cơ chế đa luồng (background threading) để lắng nghe topic `traffic/cmd/{camera_id}` này. Do chưa có nhu cầu sử dụng thực tế và áp dụng triết lý YAGNI (You Aren't Gonna Need It), các hàm `subscribe` và TODO này đã được quyết định xóa bỏ để tránh nhầm lẫn. Khi tính năng OTA được phát triển chính thức, luồng Subscribe MQTT sẽ được thiết kế và bổ sung lại một cách an toàn.

## 2. Luồng dữ liệu: Từ Edge Server đến C2_Center Frontend
Trong file `GETTING_STARTED.md`, luồng dữ liệu được ghi tóm tắt là *"picked up by the data_pipeline and shown on the c2_center frontend"*. Tuy nhiên, về mặt kỹ thuật chi tiết, dữ liệu không đi tắt (bypass) qua Backend.

Luồng đi thực tế diễn ra như sau:
1. **Edge Server (C++)**: Gửi JSON telemetry và video frames lên **MQTT Broker** (thông qua topic `traffic/detections`).
2. **Data Pipeline (Python)**: Đóng vai trò là Subscriber, lắng nghe MQTT Broker. Khi có tin nhắn, Pipeline sẽ trích xuất thông tin (URL hình ảnh, bbox) và **Lưu trữ thẳng vào PostgreSQL Database** (`traffic_db`).
3. **C2_Center Backend**: (API Server) Truy vấn dữ liệu từ **PostgreSQL**, hoặc nhận dữ liệu real-time thông qua WebSocket/Redis từ hệ thống.
4. **C2_Center Frontend**: Giao diện Web gọi API/WebSocket từ Backend để hiển thị kết quả cuối cùng cho người dùng.

Như vậy, Data Pipeline đóng vai trò cầu nối, thu thập dữ liệu thô và ghi vào DB, sau đó Backend C2_Center mới lấy dữ liệu đó để phục vụ cho Frontend.
