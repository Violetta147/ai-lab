import cv2
import numpy as np
from ultralytics import YOLO
import supervision as sv
import math

# ==========================================
# CẤU HÌNH THÔNG SỐ CƠ BẢN
# ==========================================
MODEL_PATH = "best.onnx"
VIDEO_PATH = "test_video.mp4"
OUTPUT_PATH = "output_density_fundamental.mp4"

# ==========================================
# THIẾT LẬP VÙNG PHÁT HIỆN ẢO (VIRTUAL DETECTION ZONE)
# ==========================================
# Dựa trên ảnh camera của bạn, ta tạo 2 vạch song song

# # Vạch VÀO (Entry Line) - Nằm ở xa camera hơn (y nhỏ hơn)
# ENTRY_START = sv.Point(600, 400)
# ENTRY_END = sv.Point(1300, 400)

# # Vạch RA (Exit Line) - Nằm gần camera hơn (y lớn hơn)
# EXIT_START = sv.Point(200, 975)
# EXIT_END = sv.Point(2000, 950)

# Vạch VÀO (Entry Line) - Nằm ở xa camera hơn (y nhỏ hơn)
ENTRY_START = sv.Point(582, 507)
ENTRY_END = sv.Point(1048, 507)

# Vạch RA (Exit Line) - Nằm gần camera hơn (y lớn hơn)
EXIT_START = sv.Point(308, 830)
EXIT_END = sv.Point(1130, 830)

# KHOẢNG CÁCH THỰC TẾ (D) GIỮA 2 VẠCH (Tính bằng KM)
# Cần đo đạc thực tế 1 lần. Ở đây giả sử 2 vạch cách nhau 20 mét (0.02 km)
# ZONE_DISTANCE_KM = 0.02 

ZONE_DISTANCE_KM = 0.03; 

# # ==========================================
# # CẤU TRÚC DỮ LIỆU ĐỂ TÍNH TOÁN
# # ==========================================
# # Từ điển lưu thời gian xe chạm vạch Entry: {tracker_id: frame_index}
# entry_timestamps = {}
# # Danh sách lưu các vận tốc đã tính toán để lấy trung bình
# calculated_speeds_kmh = []

# ==========================================
# CẤU TRÚC DỮ LIỆU ĐỂ TÍNH TOÁN
# ==========================================

# [MỚI] Sử dụng Cửa sổ thời gian trượt (Sliding Window) thay vì cộng dồn
SLIDING_WINDOW_SEC = 30.0  # Cửa sổ 30 giây

def main():
    print("[INFO] Khởi động Hàm 4: Ước lượng Mật độ qua Dòng Giao thông (k = q/v)...")
    model = YOLO(MODEL_PATH)
    
    video_info = sv.VideoInfo.from_video_path(VIDEO_PATH)
    video_fps = video_info.fps
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(OUTPUT_PATH, fourcc, video_fps, (video_info.width, video_info.height))

    # Công cụ vẽ Box và Text
    box_annotator = sv.BoxAnnotator(thickness=2)
    label_annotator = sv.LabelAnnotator(text_thickness=2, text_scale=0.6, text_color=sv.Color.BLACK)

    # Khởi tạo 2 bộ đếm qua vạch (Line Zone) của supervision
    entry_line = sv.LineZone(start=ENTRY_START, end=ENTRY_END)
    exit_line = sv.LineZone(start=EXIT_START, end=EXIT_END)

    # Công cụ vẽ 2 vạch lên màn hình
    entry_annotator = sv.LineZoneAnnotator(thickness=2, text_thickness=2, text_scale=1.0, custom_in_text="ENTRY IN", custom_out_text="ENTRY OUT")
    exit_annotator = sv.LineZoneAnnotator(thickness=2, text_thickness=2, text_scale=1.0, custom_in_text="EXIT IN", custom_out_text="EXIT OUT")

    cap = cv2.VideoCapture(VIDEO_PATH)
    frame_count = 0

    # ==========================================
    # [MANG 3 BIẾN NÀY VÀO TRONG HÀM MAIN]
    # ==========================================
    entry_timestamps = {}
    exit_timestamps_frames = []
    vehicle_speed_records = []

    cv2.namedWindow("Fundamental Traffic Equation", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Fundamental Traffic Equation", 1280, 720) 

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_count += 1

        results = model.track(frame, persist=True, tracker="bytetrack.yaml", conf=0.3, verbose=False)[0]

        # Khởi tạo mảng label rỗng cho frame hiện tại
        custom_labels = []

        if results.boxes.id is not None:
            detections = sv.Detections.from_ultralytics(results)
            
            # # --- KIỂM TRA GIAO CẮT Ở 2 VẠCH ---
            # # Trả về 2 mảng boolean [True, False...] xem xe nào cắt vạch ở frame này
            # entry_crossed = entry_line.trigger(detections=detections)
            # exit_crossed = exit_line.trigger(detections=detections)


            # --- KIỂM TRA GIAO CẮT Ở 2 VẠCH ---
            # Hàm trigger() ở bản mới trả về Tuple (crossed_in, crossed_out)
            entry_in, entry_out = entry_line.trigger(detections=detections)
            exit_in, exit_out = exit_line.trigger(detections=detections)
            
            # Gộp 2 chiều lại: Chỉ cần xe cắt vạch (bất kể chiều nào) thì tính là True
            entry_crossed = entry_in | entry_out
            exit_crossed = exit_in | exit_out   

        #     # --- LÕI TOÁN HỌC: ĐO VẬN TỐC (SPEED ESTIMATION) ---
        #     for i, tracker_id in enumerate(detections.tracker_id):
        #         class_id = detections.class_id[i]
        #         class_name = results.names[class_id]
        #         conf = detections.confidence[i]
        #         speed_text = ""

        #         # 1. Nếu xe chạm vạch ENTRY -> Ghi lại thời điểm (số thứ tự frame)
        #         if entry_crossed[i]:
        #             entry_timestamps[tracker_id] = frame_count

        #         # 2. Nếu xe chạm vạch EXIT VÀ nó đã từng đi qua vạch ENTRY trước đó
        #         if exit_crossed[i] and tracker_id in entry_timestamps:
        #             # Tính thời gian đã trôi qua (bằng Giờ - Hours)
        #             frames_elapsed = frame_count - entry_timestamps[tracker_id]
        #             time_elapsed_hours = (frames_elapsed / video_fps) / 3600.0
                    
        #             if time_elapsed_hours > 0:
        #                 # Tính vận tốc v = D / t (km/h)
        #                 speed_kmh = ZONE_DISTANCE_KM / time_elapsed_hours
                        
        #                 # Loại bỏ các vận tốc sai số (ví dụ xe đậu lại làm v = 0.001 hoặc lỗi AI v = 999)
        #                 # if 5.0 <= speed_kmh <= 120.0:
        #                 if 1.0 <= speed_kmh <= 250.0:
        #                     calculated_speeds_kmh.append(speed_kmh)
                            
        #                 # Sau khi tính xong, xóa ID khỏi từ điển để tiết kiệm RAM
        #                 del entry_timestamps[tracker_id]

        #         # 3. Tạo nhãn dán: "#ID Tên_xe" (Không cần hiện tốc độ lên từng xe vì tốc độ chỉ có sau khi qua vạch 2)
        #         custom_labels.append(f"#{tracker_id} {class_name} {conf:.2f}")

        #     # Vẽ Box và Text lên xe
        #     frame = box_annotator.annotate(scene=frame, detections=detections)
        #     frame = label_annotator.annotate(scene=frame, detections=detections, labels=custom_labels)

        # # Vẽ 2 vạch kẻ lên màn hình (Màu đỏ cho Entry, Xanh dương cho Exit)
        # entry_annotator.annotate(frame=frame, line_counter=entry_line)
        # exit_annotator.annotate(frame=frame, line_counter=exit_line)

        # # # ==========================================
        # # # TÍNH TOÁN CÁC CHỈ SỐ VĨ MÔ (q, v, k)
        # # # ==========================================
        # # # 1. Tính thời gian video (đơn vị: Giờ)
        # # video_time_hours = (frame_count / video_fps) / 3600.0

        # # # 2. Tính Lưu lượng (q): Lấy tổng số xe đã hoàn thành việc qua vạch EXIT
        # # total_vehicles_passed = exit_line.in_count + exit_line.out_count
        # # q_flow_rate = 0.0
        # # if video_time_hours > 0:
        # #     q_flow_rate = total_vehicles_passed / video_time_hours # veh/h

        # # # 3. Tính Vận tốc trung bình không gian (v_avg)
        # # v_avg_kmh = 0.0
        # # if len(calculated_speeds_kmh) > 0:
        # #     # Chỉ lấy trung bình của 20 xe gần nhất (Moving Average) để phản ánh đúng thực tại
        # #     recent_speeds = calculated_speeds_kmh[-20:]
        # #     v_avg_kmh = sum(recent_speeds) / len(recent_speeds)
        
        # # # 4. Tính Mật độ giao thông (k = q / v)
        # # k_density = 0.0
        # # if v_avg_kmh > 0:
        # #     k_density = q_flow_rate / v_avg_kmh # veh/km
        

        # # ==========================================
        # # TÍNH TOÁN CÁC CHỈ SỐ VĨ MÔ (q, v, k)
        # # ==========================================
        # # 1. Tính thời gian video (đơn vị: Giờ)
        # video_time_hours = (frame_count / video_fps) / 3600.0

        # # Khởi tạo mặc định các số là 0.0
        # q_flow_rate = 0.0
        # v_avg_kmh = 0.0
        # k_density = 0.0

        # # CHỈ CẬP NHẬT CHỈ SỐ SAU KHI VIDEO CHẠY ĐƯỢC 5 GIÂY (Tránh nhiễu chia số quá nhỏ lúc đầu)
        # if video_time_hours > (5.0 / 3600.0):
        #     # 2. Tính Lưu lượng (q)
        #     total_vehicles_passed = exit_line.in_count + exit_line.out_count
        #     q_flow_rate = total_vehicles_passed / video_time_hours # veh/h

        #     # 3. Tính Vận tốc trung bình (v_avg)
        #     if len(calculated_speeds_kmh) > 0:
        #         recent_speeds = calculated_speeds_kmh[-20:]
        #         v_avg_kmh = sum(recent_speeds) / len(recent_speeds)
            
        #     # 4. Tính Mật độ (k = q / v)
        #     if v_avg_kmh > 0:
        #         k_density = q_flow_rate / v_avg_kmh # veh/km


        # --- LÕI TOÁN HỌC: ĐO VẬN TỐC VÀ LƯU LƯỢNG (SLIDING WINDOW LOGIC) ---
            for i, tracker_id in enumerate(detections.tracker_id):
                class_id = detections.class_id[i]
                class_name = results.names[class_id]
                conf = detections.confidence[i]

                # 1. Nếu xe chạm vạch ENTRY -> Ghi lại mốc thời gian bắt đầu
                if entry_crossed[i]:
                    entry_timestamps[tracker_id] = frame_count

                # 2. Nếu xe chạm vạch EXIT -> Tính Lưu lượng và Vận tốc
                if exit_crossed[i]:
                    # BẤT KỂ xe có được track từ đầu hay không, cứ qua Exit là đếm vào Lưu lượng (q)
                    exit_timestamps_frames.append(frame_count)

                    # NẾU xe có mốc thời gian ở Entry -> Đủ điều kiện để tính Vận tốc (v)
                    if tracker_id in entry_timestamps:
                        frames_elapsed = frame_count - entry_timestamps[tracker_id]
                        time_elapsed_hours = (frames_elapsed / video_fps) / 3600.0
                        
                        if time_elapsed_hours > 0:
                            speed_kmh = ZONE_DISTANCE_KM / time_elapsed_hours
                            # Lọc nhiễu AI (Chỉ lấy xe có vận tốc thực tế của con người)
                            if 1.0 <= speed_kmh <= 250.0:
                                # Lưu tốc độ kèm theo thời điểm nó đi qua để sau này trượt cửa sổ
                                vehicle_speed_records.append((speed_kmh, frame_count))
                                
                        del entry_timestamps[tracker_id] # Xóa để giải phóng RAM

                custom_labels.append(f"#{tracker_id} {class_name} {conf:.2f}")

            # Vẽ Box và Text lên xe
            frame = box_annotator.annotate(scene=frame, detections=detections)
            frame = label_annotator.annotate(scene=frame, detections=detections, labels=custom_labels)

        # Vẽ 2 vạch kẻ
        entry_annotator.annotate(frame=frame, line_counter=entry_line)
        exit_annotator.annotate(frame=frame, line_counter=exit_line)

        # ==========================================
        # [CẬP NHẬT] TÍNH TOÁN CÁC CHỈ SỐ VĨ MÔ QUA CỬA SỔ TRƯỢT
        # ==========================================
        current_time_sec = frame_count / video_fps

        # 1. TÍNH LƯU LƯỢNG (q) TRONG 30 GIÂY GẦN NHẤT
        # Loại bỏ các xe đã đi qua quá 30 giây (ngoài cửa sổ)
        exit_timestamps_frames = [f for f in exit_timestamps_frames if (current_time_sec - f/video_fps) <= SLIDING_WINDOW_SEC]
        N_window = len(exit_timestamps_frames)
        
        # Thời gian quan sát thực tế (obs_time)
        # Nếu video mới chạy 10s thì chia 10s, nếu chạy qua 30s thì luôn chia 30s
        obs_time = min(current_time_sec, SLIDING_WINDOW_SEC)
        
        q_flow_rate = 0.0
        if obs_time > 0:
            q_flow_rate = (N_window / obs_time) * 3600.0 # Quy đổi ra xe/giờ

        # 2. TÍNH VẬN TỐC TRUNG BÌNH (v_avg) TRONG 30 GIÂY GẦN NHẤT
        # Loại bỏ các bản ghi vận tốc quá 30 giây
        vehicle_speed_records = [rec for rec in vehicle_speed_records if (current_time_sec - rec[1]/video_fps) <= SLIDING_WINDOW_SEC]
        
        v_avg_kmh = 0.0
        if len(vehicle_speed_records) > 0:
            v_avg_kmh = sum([rec[0] for rec in vehicle_speed_records]) / len(vehicle_speed_records)

        # 3. TÍNH MẬT ĐỘ (k = q / v)
        k_density = 0.0
        if v_avg_kmh > 0:
            k_density = q_flow_rate / v_avg_kmh # veh/km
        elif q_flow_rate > 0 and v_avg_kmh == 0:
            # Fallback an toàn: Có xe chạy qua (q > 0) nhưng AI bị mất dấu nên không đo được v
            # Gán tạm vận tốc giới hạn của đường (ví dụ 40km/h) để hệ thống không bị crash (k = vô cực)
            k_density = q_flow_rate / 40.0





        # ==========================================
        # VẼ DASHBOARD HIỂN THỊ (THE FUNDAMENTAL EQUATION)
        # ==========================================
        cv2.rectangle(frame, (20, 20), (600, 220), (0, 0, 0), -1) 
        
        cv2.putText(frame, "FUNDAMENTAL TRAFFIC EQUATION", (40, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        cv2.putText(frame, f"Flow (q): {q_flow_rate:.1f} veh/h", 
                    (40, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
        
        cv2.putText(frame, f"Avg Speed (v): {v_avg_kmh:.1f} km/h", 
                    (40, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 165, 0), 2)
        
        # In đậm chỉ số k (Mật độ)
        cv2.putText(frame, f"Density (k=q/v): {k_density:.1f} veh/km", 
                    (40, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)

        out.write(frame)
        cv2.imshow("Fundamental Traffic Equation", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()
    print("[SUCCESS] Đã hoàn thành Hàm 4: Tính Mật độ qua Vận tốc.")

if __name__ == "__main__":
    main()