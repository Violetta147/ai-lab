import cv2
import numpy as np
from ultralytics import YOLO
import supervision as sv

# ==========================================
# CẤU HÌNH THÔNG SỐ
# ==========================================
MODEL_PATH = "best.onnx"
VIDEO_PATH = "test_video.mp4"
OUTPUT_PATH = "output_density_absolute.mp4"

# # Tọa độ ROI đã được tinh chỉnh chuẩn xác
# ROI_VERTICES = np.array([
#     [350, 250],   # Trái trên
#     [650, 250],   # Phải trên
#     [1000, 700],  # Phải dưới
#     [100, 700]    # Trái dưới
# ], np.int32)

# ROI_VERTICES = np.array([
#     [600, 400],   # Điểm 1: Góc trái trên
#     [1300, 400],   # Điểm 2: Góc phải trên
#     [2000, 950],  # Điểm 3: Góc phải dưới (mở rộng ra do góc phối cảnh camera)
#     [200, 975]    # Điểm 4: Góc trái dưới
# ], np.int32)

ROI_VERTICES = np.array([
    [750, 400],   # Điểm 1: Góc trái trên
    [980, 400],   # Điểm 2: Góc phải trên
    [1250, 1050],  # Điểm 3: Góc phải dưới (mở rộng ra do góc phối cảnh camera)
    [200, 1000]    # Điểm 4: Góc trái dưới
], np.int32)


# ==========================================
# HÀM 1: TÍNH TOÁN MẬT ĐỘ THÔ (ABSOLUTE COUNT)
# ==========================================
# Mục tiêu học thuật: Tự tay duyệt qua các Bounding Box, tìm tọa độ Tâm (Centroid),
# và dùng thuật toán hình học của OpenCV (PointPolygonTest) để kiểm tra.
def calculate_absolute_density(detections, roi_polygon):
    """
    Hàm đếm số lượng phương tiện nằm hoàn toàn trong vùng ROI.
    
    Tham số:
        detections (sv.Detections): Danh sách các phương tiện phát hiện được trong frame.
        roi_polygon (np.array): Mảng tọa độ các đỉnh của đa giác ROI.
        
    Trả về:
        int: Tổng số xe nằm trong vùng.
    """
    count = 0
    # xyxy là mảng chứa tọa độ của tất cả các Bounding Box: [x_min, y_min, x_max, y_max]
    for bbox in detections.xyxy:
        x_min, y_min, x_max, y_max = bbox
        
        # 1. Tính toán tọa độ điểm Trọng tâm (Centroid) của hộp
        centroid_x = int((x_min + x_max) / 2)
        centroid_y = int((y_min + y_max) / 2)
        centroid_point = (centroid_x, centroid_y)
        
        # 2. Thuật toán Ray-Casting: Kiểm tra điểm có nằm trong đa giác không
        # measureDist=False: Trả về +1 nếu điểm ở trong, 0 nếu nằm trên cạnh, -1 nếu ở ngoài
        is_inside = cv2.pointPolygonTest(roi_polygon, centroid_point, False)
        
        if is_inside >= 0:
            count += 1
            
    return count

def main():
    print("[INFO] Khởi động Hàm 1: Đếm số lượng thô (Absolute Count)...")
    model = YOLO(MODEL_PATH)
    
    video_info = sv.VideoInfo.from_video_path(VIDEO_PATH)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(OUTPUT_PATH, fourcc, video_info.fps, (video_info.width, video_info.height))

    box_annotator = sv.BoxAnnotator(thickness=2)
    label_annotator = sv.LabelAnnotator(text_thickness=2, text_scale=0.5, text_color=sv.Color.BLACK)

    # Vẫn dùng thư viện để vẽ cái viền đa giác đỏ cho đẹp mắt
    polygon_zone = sv.PolygonZone(polygon=ROI_VERTICES)
    polygon_annotator = sv.PolygonZoneAnnotator(zone=polygon_zone, color=sv.Color.RED, thickness=2)

    cap = cv2.VideoCapture(VIDEO_PATH)

    cv2.namedWindow("Density: Absolute Count", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Density: Absolute Count", 1280, 720) 

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        results = model.track(frame, persist=True, tracker="bytetrack.yaml", conf=0.3, verbose=False)[0]

        total_count = 0

        if results.boxes.id is not None:
            detections = sv.Detections.from_ultralytics(results)
            
            # ==========================================
            # GỌI HÀM TÍNH TOÁN MẬT ĐỘ THÔ
            # ==========================================
            total_count = calculate_absolute_density(detections, ROI_VERTICES)

            # Dùng mặt nạ để lọc bớt xe ngoài đường, chỉ vẽ Box cho xe trong ROI để quan sát
            mask = polygon_zone.trigger(detections=detections)
            detections_in_roi = detections[mask]

            labels = [
                f"#{tracker_id} {results.names[class_id]}"
                for class_id, tracker_id 
                in zip(detections_in_roi.class_id, detections_in_roi.tracker_id)
            ]

            frame = box_annotator.annotate(scene=frame, detections=detections_in_roi)
            frame = label_annotator.annotate(scene=frame, detections=detections_in_roi, labels=labels)

            # --- VẼ THÊM ĐIỂM TRỌNG TÂM (CENTROID) ĐỂ DEMO THUẬT TOÁN CHO THẦY ---
            # Vẽ một dấu chấm tròn nhỏ xíu ở giữa mỗi chiếc xe để minh họa "Điểm neo"
            for bbox in detections_in_roi.xyxy:
                cx = int((bbox[0] + bbox[2]) / 2)
                cy = int((bbox[1] + bbox[3]) / 2)
                cv2.circle(frame, (cx, cy), radius=4, color=(0, 255, 255), thickness=-1)

        # # Vẽ đa giác màu đỏ
        # frame = polygon_annotator.annotate(scene=frame)

        # # Hiển thị kết quả của Hàm 1 lên màn hình
        # cv2.rectangle(frame, (10, 10), (450, 80), (0, 0, 0), -1)
        # cv2.putText(frame, f"Absolute Count (Method 1): {total_count}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # out.write(frame)
        # cv2.imshow("Density: Absolute Count", frame)

        # Vẽ đa giác màu đỏ
        frame = polygon_annotator.annotate(scene=frame)

        # ==========================================
        # BỔ SUNG TOÁN HỌC: TÍNH MẬT ĐỘ THỰC TẾ (k = N / L)
        # ==========================================
        # Giả sử chiều dài thực tế của đoạn đường trong đa giác đỏ là 15 mét
        # ROAD_LENGTH_KM = 0.015  # 15m = 0.015km
        ROAD_LENGTH_KM = 0.1    
        # N: Tổng xe (total_count)
        # L: Chiều dài (ROAD_LENGTH_KM)
        # k: Mật độ (density_k)
        density_k = 0
        if ROAD_LENGTH_KM > 0:
            density_k = total_count / ROAD_LENGTH_KM

        # Hiển thị kết quả hoàn chỉnh của Hàm 1 lên màn hình
        # Mở rộng bảng đen mờ để chứa thêm thông tin
        cv2.rectangle(frame, (10, 10), (450, 120), (0, 0, 0), -1)
        
        # In ra N (Số xe đếm được)
        cv2.putText(frame, f"Vehicles (N): {total_count}", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        # In ra k (Mật độ = Số xe / km)
        cv2.putText(frame, f"Density (k): {density_k:.1f} veh/km", (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        out.write(frame)
        cv2.imshow("Density: Absolute Count", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()
    print("[SUCCESS] Đã hoàn thành Hàm 1.")

if __name__ == "__main__":
    main()