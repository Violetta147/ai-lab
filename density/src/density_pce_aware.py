import cv2
import numpy as np
from ultralytics import YOLO
import supervision as sv

# ==========================================
# CẤU HÌNH THÔNG SỐ
# ==========================================
MODEL_PATH = "best.onnx"
VIDEO_PATH = "test_video.mp4"
OUTPUT_PATH = "output_density_pce.mp4"

# # Tọa độ ROI (Kế thừa từ bản chuẩn của bạn)
# ROI_VERTICES = np.array([
#     [600, 400],   
#     [1300, 400],  
#     [2000, 950],  
#     [200, 975]    
# ], dtype=np.float32) # Giữ float32 nếu sau này bạn muốn tích hợp chung với BEV, còn ở hàm này int32 hay float32 đều chạy được.


# Tọa độ ROI (Kế thừa từ bản chuẩn của bạn)
ROI_VERTICES = np.array([
    [750, 400],   # Điểm 1: Góc trái trên
    [980, 400],   # Điểm 2: Góc phải trên
    [1250, 1050],  # Điểm 3: Góc phải dưới (mở rộng ra do góc phối cảnh camera)
    [200, 1000]    # Điểm 4: Góc trái dưới
], dtype=np.float32) # Giữ float32 nếu sau này bạn muốn tích hợp chung với BEV, còn ở hàm này int32 hay float32 đều chạy được.

# # Tọa độ ROI (Kế thừa từ bản chuẩn của bạn)
# ROI_VERTICES = np.array([
#     [784, 359],   # Điểm 1: Góc trái trên
#     [968, 359],   # Điểm 2: Góc phải trên
#     [1155, 748],  # Điểm 3: Góc phải dưới (mở rộng ra do góc phối cảnh camera)
#     [359, 748]    # Điểm 4: Góc trái dưới
# ], dtype=np.float32) # Giữ float32 nếu sau này bạn muốn tích hợp chung với BEV, còn ở hàm này int32 hay float32 đều chạy được.

# ==========================================
# HÀM 3: BỘ TỪ ĐIỂN HỆ SỐ QUY ĐỔI PCE
# ==========================================
# Lưu ý: Các key trong từ điển này PHẢI KHỚP CHÍNH XÁC 100% với 
# mảng names trong file data.yaml của bạn (bus, car, motor, truck)
PCE_WEIGHTS = {
    "motor": 0.5,
    "car": 1.0,
    "bus": 2.5,
    "truck": 2.5
}

# ==========================================
# NGƯỠNG ĐÁNH GIÁ ÙN TẮC (CONGESTION THRESHOLDS)
# ==========================================
# Dựa trên tổng điểm PCE trong vùng ROI để kết luận trạng thái.
# Các con số này cần tinh chỉnh dựa trên diện tích thực tế của ROI.
THRESHOLD_HEAVY = 15.0  
THRESHOLD_JAM = 25.0    

def calculate_pce_density(detections_in_roi, class_names_dict):
    """
    Hàm tính toán tổng mật độ PCE của các xe trong vùng ROI.
    
    Tham số:
        detections_in_roi: Dữ liệu xe đã được lọc (chỉ lấy xe nằm trong ROI).
        class_names_dict: Từ điển map ID class sang tên class của YOLO (VD: {0: 'bus', 1: 'car'...}).
        
    Trả về:
        float: Tổng điểm PCE.
        list: Danh sách nhãn dán chi tiết cho từng xe (để hiển thị).
    """
    total_pce = 0.0
    labels = []
    
    # Lặp qua từng xe trong ROI
    for class_id, tracker_id, conf in zip(detections_in_roi.class_id, detections_in_roi.tracker_id, detections_in_roi.confidence):
        # Lấy tên class (VD: 'motor', 'car')
        class_name = class_names_dict[class_id]
        
        # Tra bảng lấy hệ số PCE. Nếu model nhận diện ra class lạ, mặc định gán = 1.0
        pce_val = PCE_WEIGHTS.get(class_name, 1.0)
        
        # Cộng dồn vào tổng điểm PCE của khung hình
        total_pce += pce_val
        
        # Tạo nhãn hiển thị cho xe: "#ID Tên_xe (PCE: Điểm) Độ_tự_tin"
        labels.append(f"#{tracker_id} {class_name} (PCE:{pce_val}) {conf:.2f}")
        
    return total_pce, labels


def main():
    print("[INFO] Khởi động Hàm 3: Ước lượng Mật độ PCE (PCE-Aware)...")
    model = YOLO(MODEL_PATH)
    
    video_info = sv.VideoInfo.from_video_path(VIDEO_PATH)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(OUTPUT_PATH, fourcc, video_info.fps, (video_info.width, video_info.height))

    # Cấu hình công cụ vẽ: Vẽ viền mỏng hơn chút để dễ nhìn xe khi đông
    box_annotator = sv.BoxAnnotator(thickness=2)
    label_annotator = sv.LabelAnnotator(text_thickness=2, text_scale=0.6, text_color=sv.Color.BLACK)

    # Đa giác ROI
    polygon_zone = sv.PolygonZone(polygon=ROI_VERTICES.astype(np.int32))
    polygon_annotator = sv.PolygonZoneAnnotator(zone=polygon_zone, color=sv.Color.RED, thickness=3)

    cap = cv2.VideoCapture(VIDEO_PATH)

    cv2.namedWindow("PCE Density Estimation", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("PCE Density Estimation", 1280, 720) 

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        results = model.track(frame, persist=True, tracker="bytetrack.yaml", conf=0.3, verbose=False)[0]

        total_pce = 0.0

        if results.boxes.id is not None:
            detections = sv.Detections.from_ultralytics(results)
            
            # 1. Dùng Mask để lọc xe trong vùng ROI trước
            mask = polygon_zone.trigger(detections=detections)
            detections_in_roi = detections[mask]

            # 2. Gọi Hàm 3 tính điểm PCE
            # results.names là một dictionary map từ class_id sang class_name của model YOLO
            total_pce, custom_labels = calculate_pce_density(detections_in_roi, results.names)

            # 3. Vẽ Box và Nhãn dán PCE lên các xe
            frame = box_annotator.annotate(scene=frame, detections=detections_in_roi)
            frame = label_annotator.annotate(scene=frame, detections=detections_in_roi, labels=custom_labels)

        # ==========================================
        # # ĐÁNH GIÁ TRẠNG THÁI ÙN TẮC VÀ ĐỔI MÀU ROI
        # # ==========================================
        # if total_pce >= THRESHOLD_JAM:
        #     status_text = "TRAFFIC JAM (Kẹt xe cứng)"
        #     status_color = (0, 0, 255) # Đỏ BGR
        #     poly_color = sv.Color.RED
        # elif total_pce >= THRESHOLD_HEAVY:
        #     status_text = "HEAVY (Ùn ứ)"
        #     status_color = (0, 165, 255) # Cam BGR
        #     poly_color = sv.Color(255, 165, 0)
        # else:
        #     status_text = "NORMAL (Thông thoáng)"
        #     status_color = (0, 255, 0) # Xanh lá BGR
        #     poly_color = sv.Color.GREEN

        # # Đổi màu đa giác theo trạng thái
        # polygon_annotator.color = poly_color
        # frame = polygon_annotator.annotate(scene=frame)

        # # ==========================================
        # # VẼ DASHBOARD HIỂN THỊ LÊN MÀN HÌNH
        # # ==========================================
        # cv2.rectangle(frame, (20, 20), (700, 180), (0, 0, 0), -1) # Bảng đen mờ
        
        # cv2.putText(frame, f"Absolute Count (N): {len(detections_in_roi if results.boxes.id is not None else [])}", 
        #             (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
        
        # cv2.putText(frame, f"Total PCE Point: {total_pce:.1f}", 
        #             (40, 110), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
        
        # cv2.putText(frame, f"Status: {status_text}", 
        #             (40, 160), cv2.FONT_HERSHEY_SIMPLEX, 1.2, status_color, 3)

        # out.write(frame)
        # cv2.imshow("PCE Density Estimation", frame)

        # ==========================================
        # TOÁN HỌC: TÍNH MẬT ĐỘ PCE THỰC TẾ (k_pce = Tổng PCE / L)
        # ==========================================
        # Khai báo chiều dài đoạn đường thực tế trong khung ROI (Ví dụ: 15 mét)
        # Thông số này cần được "hiệu chuẩn" (calibrate) một lần khi lắp camera thực tế
        # ROAD_LENGTH_KM = 0.015 
        ROAD_LENGTH_KM = 0.1;
        pce_density = 0.0
        if ROAD_LENGTH_KM > 0:
            pce_density = total_pce / ROAD_LENGTH_KM

        # ==========================================
        # ĐÁNH GIÁ TRẠNG THÁI DỰA TRÊN MẬT ĐỘ PCE/KM (Chuẩn quốc tế)
        # ==========================================
        # Thay vì dùng Threshold cố định cho khung ảnh, ta dùng Threshold cho 1km
        # Các ngưỡng dưới đây có thể tùy chỉnh:
        # > 1500 PCE/km: Kẹt xe nặng
        # > 800 PCE/km: Ùn ứ
        if pce_density >= 1500.0:
            status_text = "TRAFFIC JAM (Ket xe)"
            status_color = (0, 0, 255) # Đỏ
            polygon_annotator.color = sv.Color.RED
        elif pce_density >= 800.0:
            status_text = "HEAVY (Un u)"
            status_color = (0, 165, 255) # Cam
            polygon_annotator.color = sv.Color(255, 165, 0)
        else:
            status_text = "NORMAL (Thong thoang)"
            status_color = (0, 255, 0) # Xanh lá
            polygon_annotator.color = sv.Color.GREEN

        # Vẽ đa giác đã đổi màu
        frame = polygon_annotator.annotate(scene=frame)

        # ==========================================
        # VẼ DASHBOARD HIỂN THỊ LÊN MÀN HÌNH
        # ==========================================
        cv2.rectangle(frame, (20, 20), (750, 220), (0, 0, 0), -1) 
        
        cv2.putText(frame, f"Absolute Count: {len(detections_in_roi if results.boxes.id is not None else [])} vehicles", 
                    (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        
        cv2.putText(frame, f"Total PCE Points: {total_pce:.1f} PCE", 
                    (40, 110), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
        
        cv2.putText(frame, f"Density (k): {pce_density:.1f} PCE/km", 
                    (40, 160), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 255), 2)

        cv2.putText(frame, f"Status: {status_text}", 
                    (40, 210), cv2.FONT_HERSHEY_SIMPLEX, 1.2, status_color, 3)

        out.write(frame)
        cv2.imshow("PCE Density Estimation", frame)

        # ... (Phần còn lại giữ nguyên) ...
        

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()
    print("[SUCCESS] Đã hoàn thành Hàm 3: Ước lượng PCE.")

if __name__ == "__main__":
    main()