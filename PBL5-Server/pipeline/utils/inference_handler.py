import torch
from ultralytics import YOLO
from ..config import MODEL_PATH


class InferenceHandler:
    def __init__(self):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"🧠 [Inference] Loading model {MODEL_PATH} on {self.device}...")
        self.model = YOLO(MODEL_PATH)
        self.model.to(self.device)
        print(f"✅ [Inference] Model loaded successfully.")

    def predict(self, img_path: str) -> str:
        """Chạy inference trên ảnh, trả về nội dung YOLO txt format.
        
        Args:
            img_path: Đường dẫn ảnh đầu vào.
            
        Returns:
            Chuỗi YOLO format (class_id cx cy w h) cho mỗi detection.
            Trả về chuỗi rỗng nếu không phát hiện object nào.
        """
        results = self.model(
            img_path, imgsz=1280, conf=0.45,
            verbose=False, device=self.device
        )
        result = results[0]

        # Convert result to YOLO format string
        lines = []
        for box in result.boxes:
            cls_id = int(box.cls[0])
            x, y, w, h = box.xywhn[0].tolist()
            lines.append(f"{cls_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}")

        return "\n".join(lines) + "\n" if lines else ""
