import cv2
import time
import io
import json
from paho.mqtt import client as mqtt_client
from ..config import BUCKET_RAW_DATA, MQTT_BROKER, MQTT_PORT, MQTT_TOPIC
from ..utils.minio_handler import MinioHandler


def main():
    """Giả lập Jetson Edge gửi dữ liệu ảnh + metadata lên hệ thống.
    
    Quy trình cho mỗi frame:
        1. Upload ảnh lên MinIO (raw-data bucket)
        2. Gửi JSON metadata qua MQTT (camera_id, image_url, detections...)
    """
    # 1. Khởi tạo MinIO
    minio = MinioHandler()
    minio.ensure_bucket(BUCKET_RAW_DATA)

    # 2. Khởi tạo MQTT
    print(f"🔌 Attempting to connect to Broker: {MQTT_BROKER} Port: {MQTT_PORT}")
    print(f"📡 Target Topic: {MQTT_TOPIC}")
    client_id = f'python-mqtt-test-{int(time.time())}'

    # Tương thích với paho-mqtt bản 2.0+
    try:
        mqtt = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION1, client_id)
    except AttributeError:
        mqtt = mqtt_client.Client(client_id)

    try:
        mqtt.connect(MQTT_BROKER, MQTT_PORT)
        mqtt.loop_start()  # Cần loop để xử lý network events
        print(f"✅ Connected to MQTT Broker: {MQTT_BROKER}")
    except Exception as e:
        print(f"❌ Failed to connect MQTT: {e}")
        return

    # 3. Mở Video giả lập
    video_path = "video_giao_thong_2.mp4"
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"❌ Could not open video: {video_path}")
        mqtt.disconnect()
        return

    print("🚀 [Simulating Jetson] Starting data push to MinIO & MQTT...")
    upload_count = 0
    max_uploads = 3  # Test 3 ảnh

    try:
        while cap.isOpened() and upload_count < max_uploads:
            ret, frame = cap.read()
            if not ret:
                print("📼 End of video reached.")
                break

            img_name = f"edge_test_{int(time.time() * 1000)}.jpg"

            # A. Đẩy ảnh lên MinIO
            _, img_encoded = cv2.imencode('.jpg', frame)
            img_bytes = img_encoded.tobytes()
            minio.upload_file(
                BUCKET_RAW_DATA, img_name,
                io.BytesIO(img_bytes), length=len(img_bytes)
            )
            print(f"📷 [1/2] Uploaded image to MinIO: {img_name}")

            # B. Gửi JSON qua MQTT
            payload = {
                "camera_id": "CAM_01",
                "image_url": img_name,
                "timestamp": time.time(),
                "trigger_reason": "Uncertainty_High",
                "detections": [
                    {"class": "car", "conf": 0.92, "bbox": [100, 200, 150, 250]},
                    {"class": "motor", "conf": 0.45, "bbox": [500, 300, 50, 80]},
                ],
            }

            publish_result = mqtt.publish(MQTT_TOPIC, json.dumps(payload), qos=1)
            publish_result.wait_for_publish(timeout=5)
            print(f"📡 [2/2] Published MQTT message for: {img_name}")

            upload_count += 1
            time.sleep(2)

    finally:
        cap.release()
        mqtt.loop_stop()
        mqtt.disconnect()

    print(f"🎉 [Simulation Done] Uploaded {upload_count} frames. Check your Database and MinIO!")


if __name__ == "__main__":
    main()
