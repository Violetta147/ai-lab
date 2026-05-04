# BUG 1
same image for 3 requests
first time: all classes -> working
second time: X class only -> working
third time: all classes -> failed still using the second's time X class even though the payload sent the server depends on user choice each request
# BUG 2
overlap threshold doesn't work no matter what %

# BOTTLENECK 1

Kafka Consumer Timeout 
Server cố gắng kết nối tới Kafka ở localhost:9092 nhưng Kafka không phản hồi (có thể Docker chưa chạy hoặc sai port). Thư viện aiokafka mặc định sẽ retry liên tục và block quá trình startup của FastAPI mất khoảng 40.3 giây trước khi bỏ cuộc. Chỉ sau khi Kafka timeout, API mới báo "All services started" và cho phép user truy cập

Cách sửa: 
vào backend/main.py, giảm timeout của Kafka consumer lúc startup xuống còn 10 giây
check if kafka is alive inside docker

# BOTTLENECK 2

Độ trễ kết nối RTSP (Mất 5-7 giây cho mỗi Camera)
Log:
camera_parking mất 5.2 giây để báo Connected (từ 22:17:50 đến 22:17:55).
nguyenxuanhieu mất 6.8 giây để báo Connected (từ 22:18:03 đến 22:18:10).
Vấn đề: Hàm cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG) nổi tiếng là rất chậm khi mở các luồng RTSP qua mạng vì nó phải chờ phân tích packet. Khi bạn có nhiều camera, việc đọc luồng này đang làm trì trệ luồng (thread) của VideoReaderService.
Cách sửa (Tùy chọn tối ưu thêm):
Đặt cờ bỏ qua buffer cho OpenCV để nó mở stream nhanh hơn:
Sửa cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

# EVIDENCE 
2026-05-04 22:17:48,742 [c2_backend] INFO:   Kafka: localhost:9092 (topic: c2_metadata)
2026-05-04 22:17:48,744 [c2_backend] INFO:   Cameras: 3 configured
2026-05-04 22:17:48,744 [c2_backend] INFO:     - camera_parking: rtsp://localhost:8554/camera_parking (enabled: True)
2026-05-04 22:17:48,744 [c2_backend] INFO:     - nguyenxuanhieu: rtsp://localhost:8554/nguyenxuanhieu (enabled: True)
2026-05-04 22:17:48,744 [c2_backend] INFO:     - muahe: rtsp://localhost:8554/muahe (enabled: False)
2026-05-04 22:17:48,746 [services.model_registry] INFO: Registered model: yolo_p2n_ft2 (3 classes, 5.4 MB)
2026-05-04 22:17:48,746 [c2_backend] INFO: Discovered 1 models
2026-05-04 22:17:48,746 [services.video_reader] INFO: Video reader service started (streams will be added by heartbeat)
2026-05-04 22:17:48,819 [services.heartbeat] INFO: Starting HeartbeatMonitor
2026-05-04 22:17:48,825 [services.kafka_consumer] INFO: Starting Kafka consumer: localhost:9092 topic=c2_metadata
2026-05-04 22:17:48,827 [aiokafka.consumer.subscription_state] INFO: Updating subscribed topics to: frozenset({'c2_metadata'})
2026-05-04 22:17:49,080 [aiokafka.cluster] WARNING: No broker metadata found in MetadataResponse -- ignoring.
2026-05-04 22:17:50,235 [services.video_reader] INFO: [camera_parking] Connecting to rtsp://localhost:8554/camera_parking...
2026-05-04 22:17:50,235 [services.video_reader] INFO: Stream added dynamically: camera_parking -> rtsp://localhost:8554/camera_parking
2026-05-04 22:17:50,236 [services.heartbeat] INFO: Heartbeat: stream added: camera_parking
2026-05-04 22:17:55,447 [services.video_reader] INFO: [camera_parking] Connected.
2026-05-04 22:18:03,796 [services.video_reader] INFO: [nguyenxuanhieu] Connecting to rtsp://localhost:8554/nguyenxuanhieu...
2026-05-04 22:18:03,796 [services.video_reader] INFO: Stream added dynamically: nguyenxuanhieu -> rtsp://localhost:8554/nguyenxuanhieu
2026-05-04 22:18:03,964 [services.heartbeat] INFO: Heartbeat: stream added: nguyenxuanhieu
2026-05-04 22:18:10,597 [services.video_reader] INFO: [nguyenxuanhieu] Connected.
2026-05-04 22:18:29,140 [c2_backend] WARNING: Kafka not available — running without metadata sync
2026-05-04 22:18:29,141 [ws.streamer] INFO: Stream processor started: camera_parking
2026-05-04 22:18:29,142 [ws.streamer] INFO: Stream processor started: nguyenxuanhieu
2026-05-04 22:18:29,142 [c2_backend] INFO: All services started. API: 0.0.0.0:8000