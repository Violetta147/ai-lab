import cv2

# Pipeline này được tối ưu riêng cho camera CSI trên Jetson Nano
def gstreamer_pipeline(
    sensor_id=0,
    capture_width=1920,
    capture_height=1080,
    display_width=1280,
    display_height=720,
    framerate=15,
    flip_method=2,
):
    return (
        "nvarguscamerasrc sensor-id=%d ! "
        "video/x-raw(memory:NVMM), width=(int)%d, height=(int)%d, framerate=(fraction)%d/1 ! "
        "nvvidconv flip-method=%d ! "
        "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
        "videoconvert ! "
        "video/x-raw, format=(string)BGR ! appsink"
        % (
            sensor_id,
            capture_width,
            capture_height,
            framerate,
            flip_method,
            display_width,
            display_height,
        )
    )

def show_camera():
    # flip_method=0 là bình thường, nếu hình bị ngược bạn đổi thành 2
    window_title = "Jetson Nano Camera Test"
    video_capture = cv2.VideoCapture(gstreamer_pipeline(flip_method=2), cv2.CAP_GSTREAMER)
    
    if video_capture.isOpened():
        print("Đang mở camera... Nhấn Q trong cửa sổ hình ảnh để thoát.")
        try:
            while True:
                ret_val, frame = video_capture.read()
                if not ret_val:
                    break
                
                cv2.imshow(window_title, frame)
                
                # Thoát khi nhấn phím 'q'
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        finally:
            video_capture.release()
            cv2.destroyAllWindows()
    else:
        print("Lỗi: Không thể mở camera bằng GStreamer!")

if __name__ == "__main__":
    show_camera()