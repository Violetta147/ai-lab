import cv2
import time

# Phiên bản đơn giản: không threading, cap.read() block tự nhiên → ít tốn CPU
print("--- ĐO FPS + HIỂN THỊ CAMERA (nhấn 'q' để thoát) ---")

cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

interval = 1.0
start_time = time.time()
counter = 0
fps_display = 0.0

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        counter += 1

        elapsed = time.time() - start_time
        if elapsed >= interval:
            fps_display = counter / elapsed
            counter = 0
            start_time = time.time()

        cv2.putText(frame, f"FPS: {fps_display:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2, cv2.LINE_AA)
        cv2.imshow("Webcam - Jetson Nano", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except KeyboardInterrupt:
    pass

finally:
    cap.release()
    cv2.destroyAllWindows()
    print("\nĐã thoát.")