import cv2
import numpy as np
from ultralytics import YOLO
import supervision as sv

# # ==========================================
# # CẤU HÌNH THÔNG SỐ VÀ TOÁN HỌC PHỐI CẢNH
# # ==========================================
# MODEL_PATH = "best.onnx"
# VIDEO_PATH = "test_video.mp4"
# OUTPUT_PATH = "output_density_occupancy.mp4"

# # 1. Tập hợp điểm NGUỒN (Góc nhìn Camera xéo)
# SRC_ROI_VERTICES = np.array([
#     [350, 250],   # Trái trên
#     [650, 250],   # Phải trên
#     [1000, 700],  # Phải dưới
#     [100, 700]    # Trái dưới
# ], dtype=np.float32)

# # 2. Tập hợp điểm ĐÍCH (Góc nhìn từ trên trời - Bird's Eye View)
# # Tạo một bản đồ 2D giả lập mặt đường thẳng tắp. 
# # Kích thước 300x600 pixels (Tương đương tỷ lệ đường rộng 3m, dài 6m)
# BEV_WIDTH = 300
# BEV_HEIGHT = 600
# DST_BEV_VERTICES = np.array([
#     [0, 0],                       # Trái trên
#     [BEV_WIDTH, 0],               # Phải trên
#     [BEV_WIDTH, BEV_HEIGHT],      # Phải dưới
#     [0, BEV_HEIGHT]               # Trái dưới
# ], dtype=np.float32)

# # 3. Tính toán Ma trận Homography (CHÌA KHÓA CỦA BÀI TOÁN)
# # Ma trận M này sẽ "bẻ cong" mọi tọa độ từ Camera sang Bản đồ 2D
# PERSPECTIVE_MATRIX = cv2.getPerspectiveTransform(SRC_ROI_VERTICES, DST_BEV_VERTICES)
# TOTAL_BEV_PIXELS = BEV_WIDTH * BEV_HEIGHT

# ==========================================
# CẤU HÌNH THÔNG SỐ VÀ TOÁN HỌC PHỐI CẢNH
# ==========================================
MODEL_PATH = "best.onnx"
VIDEO_PATH = "test_video.mp4"
OUTPUT_PATH = "output_density_occupancy.mp4"

# 1. Tập hợp điểm NGUỒN - Sửa thành np.float32 để OpenCV không báo lỗi

# SRC_ROI_VERTICES = np.array([
#     [600, 400],   # Điểm 1: Góc trái trên
#     [1300, 400],  # Điểm 2: Góc phải trên
#     [2000, 950],  # Điểm 3: Góc phải dưới
#     [200, 975]    # Điểm 4: Góc trái dưới
# ], dtype=np.float32)

SRC_ROI_VERTICES = np.array([
    [750, 400],   # Điểm 1: Góc trái trên
    [980, 400],   # Điểm 2: Góc phải trên
    [1250, 1050],  # Điểm 3: Góc phải dưới (mở rộng ra do góc phối cảnh camera)
    [200, 1000]    # Điểm 4: Góc trái dưới
], dtype=np.float32)

# 2. Tập hợp điểm ĐÍCH (Bird's Eye View)
# Đổi thành 500x500 (Hoặc tỷ lệ nào xe trên minimap giữ đúng hình dáng nhất)
BEV_WIDTH = 500
BEV_HEIGHT = 500
# BEV_WIDTH = 1000
# BEV_HEIGHT =1000
DST_BEV_VERTICES = np.array([   
    [0, 0],                       
    [BEV_WIDTH, 0],               
    [BEV_WIDTH, BEV_HEIGHT],      
    [0, BEV_HEIGHT]               
], dtype=np.float32)

PERSPECTIVE_MATRIX = cv2.getPerspectiveTransform(SRC_ROI_VERTICES, DST_BEV_VERTICES)
TOTAL_BEV_PIXELS = BEV_WIDTH * BEV_HEIGHT

def main():
    print("[INFO] Khởi động Hàm 2: Tỷ lệ chiếm dụng diện tích (BEV Area Occupancy)...")
    model = YOLO(MODEL_PATH)
    
    video_info = sv.VideoInfo.from_video_path(VIDEO_PATH)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(OUTPUT_PATH, fourcc, video_info.fps, (video_info.width, video_info.height))

    box_annotator = sv.BoxAnnotator(thickness=2)
    polygon_zone = sv.PolygonZone(polygon=SRC_ROI_VERTICES.astype(np.int32))
    polygon_annotator = sv.PolygonZoneAnnotator(zone=polygon_zone, color=sv.Color.RED, thickness=2)

    cap = cv2.VideoCapture(VIDEO_PATH)
    cv2.namedWindow("Area Occupancy - Bird's Eye View", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Area Occupancy - Bird's Eye View", 1280, 720) 

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        results = model.track(frame, persist=True, tracker="bytetrack.yaml", conf=0.3, verbose=False)[0]
        
        # Khởi tạo một bức tranh canvas đen thui đại diện cho mặt đường nhìn từ trên cao
        bev_canvas = np.zeros((BEV_HEIGHT, BEV_WIDTH), dtype=np.uint8)

        if results.boxes.id is not None:
            detections = sv.Detections.from_ultralytics(results)
            
            # Chỉ lấy các xe nằm trong đa giác đỏ
            mask = polygon_zone.trigger(detections=detections)
            detections_in_roi = detections[mask]

            frame = box_annotator.annotate(scene=frame, detections=detections_in_roi)

            # ==========================================
            # LÕI TOÁN HỌC: TRẢI PHẲNG TỪNG BƯỚC (FLATTENING)
            # ==========================================
            for bbox in detections_in_roi.xyxy:
                x1, y1, x2, y2 = bbox
                
                # Trích xuất 4 góc của Bounding Box trên camera
                box_corners = np.array([
                    [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
                ], dtype=np.float32)
                
                # Dùng Ma trận Homography để bẻ Bounding Box này sang không gian BEV
                transformed_corners = cv2.perspectiveTransform(box_corners, PERSPECTIVE_MATRIX)
                
                # Ép kiểu về số nguyên để vẽ
                bev_polygon = np.int32(transformed_corners)
                
                # Vẽ hình đa giác vừa biến đổi lên mặt đường BEV bằng màu trắng (255)
                # Kỹ thuật vẽ chồng này tự động loại bỏ lỗi tính trùng diện tích khi xe che khuất nhau
                cv2.fillPoly(bev_canvas, bev_polygon, 255)

        # ==========================================
        # TÍNH TOÁN % DIỆN TÍCH (AREA OCCUPANCY)
        # ==========================================
        # Đếm số lượng điểm ảnh màu trắng trên tổng số điểm ảnh của bản đồ
        occupied_pixels = cv2.countNonZero(bev_canvas)
        occupancy_percentage = (occupied_pixels / TOTAL_BEV_PIXELS) * 100

        frame = polygon_annotator.annotate(scene=frame)

        # # --- GIAO DIỆN HIỂN THỊ CỰC ĐỈNH CHO DASHBOARD ---
        # # 1. In thông số % lên camera
        # cv2.rectangle(frame, (10, 10), (550, 80), (0, 0, 0), -1)
        
        # # Đổi màu cảnh báo dựa trên tỷ lệ % (ví dụ: >40% là kẹt cứng)
        # text_color = (0, 255, 0) # Xanh lá
        # if occupancy_percentage > 20: text_color = (0, 165, 255) # Cam
        # if occupancy_percentage > 40: text_color = (0, 0, 255)   # Đỏ
            
        # cv2.putText(frame, f"Area Occupancy: {occupancy_percentage:.1f}%", (20, 55), 
        #             cv2.FONT_HERSHEY_SIMPLEX, 1.2, text_color, 3)

        # # 2. VẼ BẢN ĐỒ MINIMAP (BIRD'S EYE VIEW) VÀO GÓC MÀN HÌNH CHÍNH
        # # Đổ màu đỏ cho các xe trên Minimap cho ngầu
        # colored_bev = cv2.cvtColor(bev_canvas, cv2.COLOR_GRAY2BGR)
        # colored_bev[np.where((colored_bev == [255, 255, 255]).all(axis=2))] = [0, 0, 255]
        
        # # Thu nhỏ minimap lại để không che hết video
        # minimap_resized = cv2.resize(colored_bev, (150, 300))
        
        # # Dán minimap vào góc trên bên phải của khung hình
        # h_frame, w_frame = frame.shape[:2]
        # frame[20:320, w_frame-170:w_frame-20] = minimap_resized
        # # Viết chữ cho Minimap
        # cv2.putText(frame, "BEV Radar", (w_frame-160, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 2)

        # --- GIAO DIỆN HIỂN THỊ CỰC ĐỈNH CHO DASHBOARD ---
        # 1. Phóng to bảng thông số để nhìn rõ trên video 4K
        cv2.rectangle(frame, (20, 20), (800, 120), (0, 0, 0), -1)
        
        text_color = (0, 255, 0) # Xanh lá
        if occupancy_percentage > 20: text_color = (0, 165, 255) # Cam
        if occupancy_percentage > 40: text_color = (0, 0, 255)   # Đỏ
            
        # Tăng text_scale lên 2.0 và thickness lên 4
        cv2.putText(frame, f"Area Occupancy: {occupancy_percentage:.1f}%", (40, 85), 
                    cv2.FONT_HERSHEY_SIMPLEX, 2.0, text_color, 4)

        # 2. Phóng to Minimap Radar cho hợp với khung hình lớn
        colored_bev = cv2.cvtColor(bev_canvas, cv2.COLOR_GRAY2BGR)
        colored_bev[np.where((colored_bev == [255, 255, 255]).all(axis=2))] = [0, 0, 255]
        
        # Phóng to minimap lên kích thước 300x300
        minimap_resized = cv2.resize(colored_bev, (300, 300))
        
        # Lấy tọa độ góc phải để dán minimap
        h_frame, w_frame = frame.shape[:2]
        # Dán minimap vào góc trên bên phải (cách lề 40px)
        frame[40:340, w_frame-340:w_frame-40] = minimap_resized
        
        # Viết chữ chú thích cho Minimap
        cv2.rectangle(frame, (w_frame-340, 40), (w_frame-340+180, 80), (0,0,0), -1)
        cv2.putText(frame, "BEV Radar", (w_frame-330, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2)

        out.write(frame)
        cv2.imshow("Area Occupancy - Bird's Eye View", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()
    print("[SUCCESS] Đã hoàn thành Hàm 2: Area Occupancy.")

if __name__ == "__main__":
    main()