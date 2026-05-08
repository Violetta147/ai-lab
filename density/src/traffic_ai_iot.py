import cv2
import json
import time
import paho.mqtt.client as mqtt
from ultralytics import YOLO
from flask import Flask, Response

app = Flask(__name__)

# 1. Cấu hình MQTT
broker = "broker.hivemq.com"
topic = "khoa_pbl5/traffic_data"
client = mqtt.Client()
client.connect(broker, 1883, 60)

# KÍCH HOẠT LUỒNG CHẠY NGẦM ĐỂ THỰC SỰ GỬI TIN NHẮN ĐI (Lỗi cũ nằm ở đây)
client.loop_start() 

print("Đang nạp mô hình AI best.pt...")
model = YOLO('best.pt')

print("Đang bật Camera...")
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

def generate_frames():
    while True:
        success, frame = cap.read()
        if not success:
            break

        results = model(frame, stream=True)
        
        for r in results:
            # Ép kiểu toàn bộ danh sách ID về số nguyên (int) để đếm chính xác
            classes = [int(c) for c in r.boxes.cls.tolist()]
            
            # Đếm theo đúng ma trận: 0=bus, 1=car, 2=motor, 3=truck
            bus_count = classes.count(0)
            car_count = classes.count(1)
            moto_count = classes.count(2)
            truck_count = classes.count(3)
            
            payload = {
                "counts": {
                    "car": car_count, 
                    "moto": moto_count, 
                    "truck": truck_count, 
                    "bus": bus_count
                },
                "congestion": 0,
                "alert": "none" 
            }
            # Gửi lên Cloud
            client.publish(topic, json.dumps(payload))
            
            res_frame = r.plot()
            ret, buffer = cv2.imencode('.jpg', res_frame)
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print("--- HỆ THỐNG EDGE AI & IOT ĐÃ KHỞI ĐỘNG CHUẨN ---")
    app.run(host='0.0.0.0', port=5000, threaded=True)   