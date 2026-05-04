"""
Test ONNX model xuất từ DeepStream-Yolo official export script.
Output format: [x1, y1, x2, y2, score, label] per detection.
"""
import cv2
import numpy as np
import onnxruntime as ort
import time

# ================= CẤU HÌNH =================
# ONNX_PATH = "yolo-prune_archive/runs/detect/fine-tuning/weights/best.onnx"
# ONNX_PATH = "models/YOLO26n_Pruned_v2_Final/weights/best.onnx"
ONNX_PATH = "models/yolo_all_exports_p2n/content/fine-tuning2/weights/best.onnx"

IMAGE_PATH = r"D:\datas\27-02-2026\images\20260227_151220UPLOADEDassignedDUTAI\20260227_151220_frame_000005.jpg"
OUTPUT_PATH = "test_result_official.jpg"

CONF_THRESH = 0.25
IOU_THRESH = 0.45
IMGSZ = 640
# ============================================

# Bảng màu cho từng class
COLORS = [
    (0, 255, 0),    # Class 0 - xanh lá
    (255, 0, 0),    # Class 1 - xanh dương
    (0, 0, 255),    # Class 2 - đỏ
    (0, 255, 255),  # Class 3 - vàng
    (255, 0, 255),  # Class 4 - hồng
]


def print_timings_ms(
    t_start_pre,
    t_end_pre,
    t_start_inf,
    t_end_inf,
    t_start_post,
    t_end_post,
    t_start_e2e,
    t_end_e2e,
):
    time_pre = (t_end_pre - t_start_pre) * 1000
    time_inf = (t_end_inf - t_start_inf) * 1000
    time_post = (t_end_post - t_start_post) * 1000
    time_e2e = (t_end_e2e - t_start_e2e) * 1000
    print("\n" + "=" * 30)
    print(f"Session/Open Time (pre): {time_pre:.2f} ms")
    print(f"Inference Time          : {time_inf:.2f} ms")
    print(f"Post-processing Time    : {time_post:.2f} ms")
    print(f"End-to-End Latency      : {time_e2e:.2f} ms")
    print("=" * 30)


def letterbox(im, new_shape, color):
    """Resize ảnh giữ nguyên tỷ lệ"""
    shape = im.shape[:2]  # H, W
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


def run_onnx_on_bgr(session, img0_bgr, conf_thresh, iou_thresh, imgsz):
    """One forward + postprocess; counts mirror test_onnx_official main()."""
    h0, w0 = img0_bgr.shape[:2]
    imgsz_tuple = (imgsz, imgsz)
    color = (114, 114, 114)

    img, ratio, dw_dh = letterbox(img0_bgr, imgsz_tuple, color)
    dw, dh = dw_dh

    img_input = img[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    img_input = np.expand_dims(img_input, 0)

    input_name = session.get_inputs()[0].name
    output = session.run(None, {input_name: img_input})[0]
    preds = output[0]

    raw_n = int(preds.shape[0])
    mask = preds[:, 4] > conf_thresh
    preds = preds[mask]
    conf_n = int(preds.shape[0])

    if conf_n == 0:
        empty_idx = np.array([], dtype=np.int64)
        return {
            "raw_n": raw_n,
            "conf_n": conf_n,
            "nms_n": 0,
            "max_label": None,
            "invalid_label": False,
            "ratio": ratio,
            "dw": dw,
            "dh": dh,
            "boxes_xyxy": np.zeros((0, 4), dtype=np.float32),
            "scores": np.zeros((0,), dtype=np.float32),
            "labels": np.zeros((0,), dtype=np.int64),
            "indices_flat": empty_idx,
            "orig_hw": (h0, w0),
        }

    boxes_xyxy = preds[:, :4]
    scores = preds[:, 4]
    labels = preds[:, 5].astype(np.int64)
    boxes_xywh = []
    for b in boxes_xyxy:
        x1, y1, x2, y2 = b
        boxes_xywh.append([float(x1), float(y1), float(x2 - x1), float(y2 - y1)])

    indices = cv2.dnn.NMSBoxes(boxes_xywh, scores.tolist(), conf_thresh, iou_thresh)
    nms_n = 0
    max_label = None
    if indices is not None and len(indices) > 0:
        nms_n = int(len(np.array(indices).flatten()))
        sel = np.array(indices).flatten()
        max_label = int(labels[sel].max()) if len(sel) > 0 else None

    return {
        "raw_n": raw_n,
        "conf_n": conf_n,
        "nms_n": nms_n,
        "max_label": max_label,
        "invalid_label": False,
        "ratio": ratio,
        "dw": dw,
        "dh": dh,
        "boxes_xyxy": boxes_xyxy,
        "scores": scores,
        "labels": labels,
        "indices_flat": np.array(indices).flatten()
        if indices is not None and len(indices) > 0
        else np.array([], dtype=np.int64),
        "orig_hw": (h0, w0),
    }


def main():
    t_start_e2e = time.perf_counter()

    # 1. Load ảnh
    img0 = cv2.imread(IMAGE_PATH)
    if img0 is None:
        print(f"❌ Không tìm thấy ảnh: {IMAGE_PATH}")
        return

    print("Dang ONNXRuntime (CPU)...")
    t_start_pre = time.perf_counter()
    session = ort.InferenceSession(ONNX_PATH)
    t_end_pre = time.perf_counter()

    t_start_inf = time.perf_counter()
    res = run_onnx_on_bgr(session, img0, CONF_THRESH, IOU_THRESH, IMGSZ)
    t_end_inf = time.perf_counter()

    t_start_post = time.perf_counter()
    print(f"   Raw detections: {res['raw_n']}")
    print(f"   After conf filter ({CONF_THRESH}): {res['conf_n']}")

    if res["conf_n"] == 0:
        print("Khong tim thay vat the nao!")
        cv2.imwrite(OUTPUT_PATH, img0)
        t_end_post = time.perf_counter()
        t_end_e2e = time.perf_counter()
        print_timings_ms(
            t_start_pre,
            t_end_pre,
            t_start_inf,
            t_end_inf,
            t_start_post,
            t_end_post,
            t_start_e2e,
            t_end_e2e,
        )
        return

    indices = res["indices_flat"]
    if indices.size == 0:
        print("NMS loc het!")
        cv2.imwrite(OUTPUT_PATH, img0)
        t_end_post = time.perf_counter()
        t_end_e2e = time.perf_counter()
        print_timings_ms(
            t_start_pre,
            t_end_pre,
            t_start_inf,
            t_end_inf,
            t_start_post,
            t_end_post,
            t_start_e2e,
            t_end_e2e,
        )
        return

    print(f"Sau NMS: {len(indices)} vat the!")

    boxes_xyxy = res["boxes_xyxy"]
    scores = res["scores"]
    labels = res["labels"]
    ratio = res["ratio"]
    dw = res["dw"]
    dh = res["dh"]

    # 5. Vẽ lên ảnh gốc
    h0, w0 = img0.shape[:2]
    for i in indices:
        x1, y1, x2, y2 = boxes_xyxy[i]
        score = scores[i]
        label = labels[i]

        # Scale bbox ngược về ảnh gốc (undo letterbox)
        x1 = (x1 - dw) / ratio
        y1 = (y1 - dh) / ratio
        x2 = (x2 - dw) / ratio
        y2 = (y2 - dh) / ratio

        # Clamp
        x1 = max(0, min(int(x1), w0))
        y1 = max(0, min(int(y1), h0))
        x2 = max(0, min(int(x2), w0))
        y2 = max(0, min(int(y2), h0))

        color = COLORS[label % len(COLORS)]
        cv2.rectangle(img0, (x1, y1), (x2, y2), color, 2)
        text = f"Class {label}: {score:.2f}"
        cv2.putText(img0, text, (x1, max(y1 - 5, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    t_end_post = time.perf_counter()
    cv2.imwrite(OUTPUT_PATH, img0)
    t_end_e2e = time.perf_counter()
    print(f"Da luu: {OUTPUT_PATH}")

    t_end_e2e = time.perf_counter()
    print_timings_ms(
        t_start_pre,
        t_end_pre,
        t_start_inf,
        t_end_inf,
        t_start_post,
        t_end_post,
        t_start_e2e,
        t_end_e2e,
    )


if __name__ == "__main__":
    main()
