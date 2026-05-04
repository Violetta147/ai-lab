import os
import sys
import atexit
import subprocess
from threading import Thread, Lock
import numpy as np
import cv2
import time

# Tắt inference để xem camera mượt thế nào (True = chỉ camera, không load model)
SKIP_INFERENCE = False

if not SKIP_INFERENCE:
    import tensorrt as trt
    import pycuda.driver as cuda
    import pycuda.autoinit


def _cleanup():
    """Cleanup khi thoát - release camera, đợi GPU ổn định."""
    try:
        vs = globals().get("vs")
        if vs is not None:
            vs.stop()
    except Exception:
        pass
    time.sleep(0.5)  # Đợi GPU/hardware ổn định trước khi process thoát


atexit.register(_cleanup)

vs = None  # WebcamStream instance, dùng cho cleanup

# COCO 80 classes cho YOLOv8
COCO_NAMES = [
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
    'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog',
    'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella',
    'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball', 'kite',
    'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket', 'bottle',
    'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich',
    'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
    'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote',
    'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator',
    'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
]


class WebcamStream:
    """Camera giống test_fps_ssh.py: CAP_V4L2, MJPG, threading."""
    def __init__(self, src=0):
        self.stream = cv2.VideoCapture(src, cv2.CAP_V4L2)
        self.stream.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.grabbed, self.frame = self.stream.read()
        self.new_frame = False
        self.stopped = False
        self.lock = Lock()

    def start(self):
        self.thread = Thread(target=self._update, daemon=True)
        self.thread.start()
        return self

    def _update(self):
        frame_times = []
        while not self.stopped:
            grabbed, frame = self.stream.read()
            if grabbed and frame is not None:
                now = time.time()
                frame_times.append(now)
                # Chỉ giữ 30 mốc thời gian gần nhất
                if len(frame_times) > 30:
                    frame_times.pop(0)
                with self.lock:
                    self.frame = frame
                    self.new_frame = True
                    # FPS thực = số frame / khoảng thời gian giữa frame đầu và cuối
                    if len(frame_times) >= 2:
                        self.camera_fps = (len(frame_times) - 1) / (frame_times[-1] - frame_times[0])

    def read(self):
        with self.lock:
            if self.new_frame:
                self.new_frame = False
                return True, self.frame.copy()
        return False, None

    def stop(self):
        self.stopped = True
        if hasattr(self, 'thread'):
            self.thread.join(timeout=2.0)


class YOLOv8TRT:
    def __init__(self, engine_path):
        self.logger = trt.Logger(trt.Logger.INFO)
        with open(engine_path, "rb") as f, trt.Runtime(self.logger) as runtime:
            self.engine = runtime.deserialize_cuda_engine(f.read())
        self.context = self.engine.create_execution_context()
        
        self.inputs, self.outputs, self.bindings, self.stream = self.allocate_buffers()
        self.input_shape = self.context.get_binding_shape(0) # [1, 3, 640, 640]

    def allocate_buffers(self):
        inputs, outputs, bindings = [], [], []
        stream = cuda.Stream()

        # Nếu engine có dynamic shape, set theo profile opt để tính kích thước buffer
        for binding in self.engine:
            binding_idx = self.engine.get_binding_index(binding)
            shape = self.engine.get_binding_shape(binding)
            if any(dim < 0 for dim in shape):
                opt_shape = self.engine.get_profile_shape(0, binding_idx)[1]
                self.context.set_binding_shape(binding_idx, opt_shape)

        for binding in self.engine:
            shape = self.context.get_binding_shape(self.engine.get_binding_index(binding))
            size = trt.volume(shape)
            dtype = trt.nptype(self.engine.get_binding_dtype(binding))
            try:
                host_mem = cuda.pagelocked_empty(size, dtype)
            except cuda.MemoryError:
                # Fallback nếu thiếu RAM pinned
                host_mem = np.empty(size, dtype=dtype)
            device_mem = cuda.mem_alloc(host_mem.nbytes)
            bindings.append(int(device_mem))
            if self.engine.binding_is_input(binding):
                inputs.append({'host': host_mem, 'device': device_mem})
            else:
                outputs.append({'host': host_mem, 'device': device_mem})
        return inputs, outputs, bindings, stream

    def preprocess(self, image):
        img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (640, 640))
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1)) # HWC to CHW
        return np.expand_dims(img, axis=0) # CHW to NCHW

    def postprocess(self, output, conf_threshold=0.25, iou_threshold=0.45):
        # Output YOLOv8n thường là [1, 8400, 84] hoặc [1, 84, 8400]
        output = output.reshape(self.engine.get_binding_shape(1))
        predictions = np.squeeze(output)
        if predictions.ndim == 3:
            predictions = predictions[0]

        # Đưa về shape [8400, 84]
        if predictions.shape[0] == 84 and predictions.shape[1] != 84:
            predictions = predictions.T

        if predictions.shape[1] < 5:
            return [], [], []

        scores = np.max(predictions[:, 4:], axis=1)
        mask = scores > conf_threshold
        predictions = predictions[mask]
        scores = scores[mask]

        if len(scores) == 0:
            return [], [], []

        class_ids = np.argmax(predictions[:, 4:], axis=1)
        boxes = predictions[:, :4]

        # Chuyển từ xywh sang xyxy
        boxes_xyxy = np.copy(boxes)
        boxes_xyxy[:, 0] = boxes[:, 0] - boxes[:, 2] / 2
        boxes_xyxy[:, 1] = boxes[:, 1] - boxes[:, 3] / 2
        boxes_xyxy[:, 2] = boxes[:, 0] + boxes[:, 2] / 2
        boxes_xyxy[:, 3] = boxes[:, 1] + boxes[:, 3] / 2

        # NMSBoxes cần xywh
        boxes_xywh = np.copy(boxes_xyxy)
        boxes_xywh[:, 2] = boxes_xyxy[:, 2] - boxes_xyxy[:, 0]
        boxes_xywh[:, 3] = boxes_xyxy[:, 3] - boxes_xyxy[:, 1]

        indices = cv2.dnn.NMSBoxes(boxes_xywh.tolist(), scores.tolist(), conf_threshold, iou_threshold)
        if len(indices) == 0:
            return [], [], []
        indices = np.array(indices).reshape(-1)

        boxes_xyxy = boxes_xyxy[indices]
        scores = scores[indices]
        class_ids = class_ids[indices]

        # Lọc class id hợp lệ
        valid = (class_ids >= 0) & (class_ids < len(COCO_NAMES))
        return boxes_xyxy[valid], scores[valid], class_ids[valid]

    def infer(self, frame):
        input_data = self.preprocess(frame)
        self.inputs[0]['host'] = np.ascontiguousarray(input_data)
        
        cuda.memcpy_htod_async(self.inputs[0]['device'], self.inputs[0]['host'], self.stream)
        self.context.execute_async_v2(bindings=self.bindings, stream_handle=self.stream.handle)
        cuda.memcpy_dtoh_async(self.outputs[0]['host'], self.outputs[0]['device'], self.stream)
        self.stream.synchronize()
        
        return self.postprocess(self.outputs[0]['host'])


def draw_detections(frame, boxes, scores, class_ids):
    """Vẽ box và label lên frame. boxes ở dạng xyxy, scale từ 640x640 sang frame size."""
    h, w = frame.shape[:2]
    scale_x, scale_y = w / 640, h / 640  # Model output là 640x640

    for box, score, cid in zip(boxes, scores, class_ids):
        if int(cid) < 0 or int(cid) >= len(COCO_NAMES):
            continue
        x1, y1, x2, y2 = box
        x1 = int(x1 * scale_x)
        y1 = int(y1 * scale_y)
        x2 = int(x2 * scale_x)
        y2 = int(y2 * scale_y)

        label = f"{COCO_NAMES[int(cid)]} {score:.2f}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw, y1), (0, 255, 0), -1)
        cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)


def main():
    """Chạy trong subprocess riêng - khi thoát toàn bộ GPU/CUDA được giải phóng sạch."""
    global vs
    HEADLESS = not (os.environ.get("DISPLAY"))

    model = None
    if not SKIP_INFERENCE:
        # Ưu tiên dùng engine do pipeline chỉ định (PIPELINE_ENGINE),
        # nếu không có thì fallback về workspace cũ.
        engine_file = os.environ.get("PIPELINE_ENGINE", "").strip()
        if not engine_file or not os.path.exists(engine_file):
            engine_file = "infer/workspace/yolov8n.transd.engine"
            if not os.path.exists(engine_file):
                engine_file = "workspace/yolov8n.transd.engine"
        print(f"[model_test] Using engine: {engine_file}")
        model = YOLOv8TRT(engine_file)

    # Camera giống test_fps_ssh.py: CAP_V4L2, MJPG, threading
    vs = WebcamStream(src=0).start()
    time.sleep(2.0)  # warmup

    camera_fps_interval = 1.0
    camera_fps_start = time.time()
    camera_frame_count = 0
    camera_fps_display = 0.0

    model_times = []  # Rolling average cho model FPS
    warmup_frames = 10
    infer_count = 0

    frame_count = 0
    log_interval = 1.0
    log_start = time.time()
    try:
        while True:
            got_new, frame = vs.read()
            if not got_new or frame is None:
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                time.sleep(0.001)
                continue

            camera_frame_count += 1
            elapsed = time.time() - camera_fps_start
            if elapsed >= camera_fps_interval:
                camera_fps_display = camera_frame_count / elapsed
                camera_frame_count = 0
                camera_fps_start = time.time()

            if SKIP_INFERENCE:
                boxes, scores, class_ids = [], [], []
                model_fps = 0.0
            else:
                t0 = time.time()
                boxes, scores, class_ids = model.infer(frame)
                infer_time = time.time() - t0
                infer_count += 1
                if infer_count > warmup_frames:
                    model_times.append(infer_time)
                    if len(model_times) > 30:
                        model_times.pop(0)
                model_fps = 1.0 / (sum(model_times) / len(model_times)) if model_times else 0.0

            # Vẽ kết quả
            if SKIP_INFERENCE:
                cv2.putText(frame, f"Camera FPS: {camera_fps_display:.1f} (no inference)", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            else:
                draw_detections(frame, boxes, scores, class_ids)
                cv2.putText(frame, f"Model FPS: {model_fps:.1f}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(frame, f"Camera FPS: {camera_fps_display:.1f}", (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

            if time.time() - log_start >= log_interval:
                if SKIP_INFERENCE:
                    print(f"Camera FPS: {camera_fps_display:.1f} | Infer FPS: 0.0 | Objects: 0")
                else:
                    print(
                        f"Camera FPS: {camera_fps_display:.1f} | Infer FPS: {model_fps:.1f} | "
                        f"Objects: {len(boxes)}"
                    )
                log_start = time.time()

            if HEADLESS:
                msg = f"Camera FPS: {camera_fps_display:.1f}"
                if not SKIP_INFERENCE:
                    msg += f" | Model FPS: {model_fps:.1f} | Objects: {len(boxes)}"
                    if len(boxes) > 0:
                        dets = [f"{COCO_NAMES[int(cid)]}({s:.2f})" for cid, s in zip(class_ids, scores)]
                        msg += f" | {', '.join(dets)}"
                print(msg, end="\r")
                if frame_count % 100 == 0:
                    cv2.imwrite("output_headless.jpg", frame)
            else:
                if not SKIP_INFERENCE and len(boxes) > 0 and frame_count % 15 == 0:
                    dets = [
                        f"{COCO_NAMES[int(cid)]}({s:.2f})"
                        for cid, s in zip(class_ids, scores)
                        if 0 <= int(cid) < len(COCO_NAMES)
                    ]
                    if dets:
                        print(f"Detected: {', '.join(dets)}")
                cv2.imshow("YOLOv8 Jetson Nano", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'): break

            frame_count += 1
    except KeyboardInterrupt:
        pass
    finally:
        vs.stop()
        if not HEADLESS:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    # Chạy trong subprocess để khi thoát GPU/CUDA được giải phóng hoàn toàn,
    # tránh segfault khi chạy test_fps_ssh.py hoặc chương trình camera khác sau đó
    if os.environ.get("_MODEL_TEST_SUBPROCESS"):
        main()
    else:
        env = os.environ.copy()
        env["_MODEL_TEST_SUBPROCESS"] = "1"
        sys.exit(subprocess.run(
            [sys.executable, __file__] + sys.argv[1:],
            env=env
        ).returncode)
