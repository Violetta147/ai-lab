import cv2
import time
import os

# Tắt cảnh báo rác của GStreamer
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"

def run_camera():
    # C270 thường là video0, dùng CAP_V4L2 để ổn định nhất
    CAM_ID = 0 
    cap = cv2.VideoCapture(CAM_ID, cv2.CAP_V4L2)

    # Thiết lập độ phân giải HD (16:9) cho màn hình rộng hơn
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    # Kiểm tra xem camera có mở được không
    if not cap.isOpened():
        print("Lỗi: Không tìm thấy Webcam!")
        return

    print("Đang chạy camera... Nhấn 'q' để thoát.")

    # Các biến để tính FPS
    prev_frame_time = 0
    new_frame_time = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # --- BẮT ĐẦU TÍNH FPS ---
        new_frame_time = time.time()
        # FPS = 1 / (Thời gian hiện tại - Thời gian khung hình trước)
        fps = 1 / (new_frame_time - prev_frame_time)
        prev_frame_time = new_frame_time
        
        # Định dạng số FPS (lấy 1 chữ số thập phân)
        fps_text = f"FPS: {fps:.1f}"

        # Vẽ chữ FPS lên khung hình
        # Thông số: (ảnh, chữ, tọa độ, font, cỡ chữ, màu BGR, độ dày)
        cv2.putText(frame, fps_text, (20, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)
        # ------------------------

        # Hiển thị kết quả
        cv2.imshow("Jetson Nano - Traffic Monitor", frame)

        # Nhấn 'q' để thoát
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_camera()
