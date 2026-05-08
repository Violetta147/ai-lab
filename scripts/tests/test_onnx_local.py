import os
import cv2
import numpy as np
import onnxruntime as ort

# ================= CẤU HÌNH =================
ONNX_PATH = "models/khoa/YOLO26_DeepStream_Elegant.onnx"
IMAGE_PATH = "D:\\datas\\27-02-2026\\images\\20260227_151220UPLOADEDassignedDUTAI\\20260227_151220_frame_000005.jpg" # 👈 ĐỔI THÀNH TÊN ẢNH CỦA BẠN (VD: test1.jpg)
OUTPUT_PATH = "test_result.jpg"

CONF_THRESH = 0.25 # Điểm tự tin tối thiểu
IOU_THRESH = 0.45  # Độ trùng lặp NMS
IMGSZ = 640
# ============================================

def letterbox(im, new_shape=(640, 640), color=(114, 114, 114)):
    """Resize ảnh giữ nguyên tỷ lệ (giống hệt maintain-aspect-ratio=1 của DeepStream)"""
    shape = im.shape[:2]
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    dw /= 2
    dh /= 2
    if shape[::-1] != new_unpad:
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return im, r, (dw, dh)

def main():
    if not os.path.exists(IMAGE_PATH):
        print(f"⚠️ Không tìm thấy ảnh {IMAGE_PATH}. Đang tạo một ảnh giả màu đen để test...")
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(img, "Please replace test_image.jpg with a real image", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
        cv2.imwrite(IMAGE_PATH, img)

    # 1. Tải ảnh & Tiền xử lý
    print("📸 Đang tiền xử lý ảnh...")
    img0 = cv2.imread(IMAGE_PATH)
    img, ratio, (dw, dh) = letterbox(img0, new_shape=(IMGSZ, IMGSZ))
    
    # Chuyển BGR -> RGB, HWC -> CHW, / 255.0
    x = img.copy()[:, :, ::-1].transpose(2, 0, 1)
    x = np.ascontiguousarray(x).astype(np.float32) / 255.0
    x = np.expand_dims(x, 0) # Tạo batch = 1: [1, 3, 640, 640]

    # 2. Suy luận bằng ONNXRuntime
    print("🚀 Đang chạy inference bằng ONNXRuntime (CPU)...")
    session = ort.InferenceSession(ONNX_PATH, providers=['CPUExecutionProvider'])
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: x})
    
    # Gồm 4 tọa độ (cx, cy, w, h), và nc class scores
    preds = outputs[0][0] 
    
    # Xử lý tự động mọi số lượng class
    boxes = preds[:, :4]
    if preds.shape[1] > 6:
        class_probs = preds[:, 4:]
        scores = np.max(class_probs, axis=1)
        labels = np.argmax(class_probs, axis=1)
    else:
        scores = preds[:, 4]
        labels = preds[:, 5]
    
    # Lọc ra những hộp có điểm tự tin > 0.25
    mask = scores > CONF_THRESH
    valid_boxes = boxes[mask]
    valid_scores = scores[mask]
    valid_labels = labels[mask]
    
    if len(valid_boxes) == 0:
        print("🤔 Không tìm thấy vật thể nào trên ảnh!")
        return

    # Chuyển [cx, cy, w, h] sang [x_min, y_min, w, h] để xài hàm NMS của OpenCV
    x_min = valid_boxes[:, 0] - valid_boxes[:, 2] / 2
    y_min = valid_boxes[:, 1] - valid_boxes[:, 3] / 2
    cv_boxes = np.stack([x_min, y_min, valid_boxes[:, 2], valid_boxes[:, 3]], axis=1).tolist()
    
    # Chạy thuật toán NMS để xóa box trùng lặp
    indices = cv2.dnn.NMSBoxes(cv_boxes, valid_scores.tolist(), CONF_THRESH, IOU_THRESH)
    
    # 4. Vẽ hộp lên ảnh
    if len(indices) > 0:
        print(f"🎯 Đã tìm thấy {len(indices)} vật thể sau khi NMS!")
        indices = np.array(indices).flatten()
        for i in indices:
            idx = int(i)
            box = valid_boxes[idx]
            score = valid_scores[idx]
            label = int(valid_labels[idx])
            
            # Tính ngược tọa độ từ lưới 640x640 về kích thước ảnh thật
            cx_scaled = (box[0] - dw) / ratio
            cy_scaled = (box[1] - dh) / ratio
            w_scaled = box[2] / ratio
            h_scaled = box[3] / ratio
            
            x1 = int(cx_scaled - w_scaled/2)
            y1 = int(cy_scaled - h_scaled/2)
            x2 = int(cx_scaled + w_scaled/2)
            y2 = int(cy_scaled + h_scaled/2)
            
            # Vẽ Box và Text
            cv2.rectangle(img0, (x1, y1), (x2, y2), (0, 0, 255), 2)
            text = f"Class {label}: {score:.2f}"
            cv2.putText(img0, text, (x1, max(10, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
        cv2.imwrite(OUTPUT_PATH, img0)
        print(f"🖼️ Đã lưu ảnh kết quả tại: {OUTPUT_PATH}")
    else:
        print("🤔 Các vật thể bị lọc hết sau NMS!")

if __name__ == "__main__":
    main()
