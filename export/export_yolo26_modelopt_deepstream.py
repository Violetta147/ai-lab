"""
Export YOLO26n Pruned (Elegant) → DeepStream ONNX
==================================================
Tư duy đơn giản từ export_pruned_yolov8.py:
  1. mto.restore() khôi phục kiến trúc pruned
  2. Monkey-patch _dist2bbox cho ONNX compatibility
  3. DeepStreamOutput đơn giản: transpose + max score
  4. nn.Sequential(model, DeepStreamOutput()) → export
"""

import io
import sys
import onnx
import torch
import torch.nn as nn
import modelopt.torch.opt as mto

from ultralytics.nn.tasks import DetectionModel
from ultralytics.nn.modules import C2f, Detect, v10Detect
import ultralytics.utils.tal as _m
import ultralytics.utils
import ultralytics.models.yolo

# Vá module map Ultralytics
sys.modules["ultralytics.yolo"] = ultralytics.models.yolo
sys.modules["ultralytics.yolo.utils"] = ultralytics.utils

# ================= Configuration =================
WEIGHTS_PATH = "models/YOLO26n_Pruned_v2_Final/weights/best.pt"
OUTPUT_ONNX  = "models/YOLO26n_Pruned_v2_Final/weights/best_deepstream.onnx"
IMGSZ = 640
OPSET = 12
# =================================================

# Patch _dist2bbox cho ONNX/TensorRT compatibility
def _dist2bbox(distance, anchor_points, xywh=False, dim=-1):
    lt, rb = distance.chunk(2, dim)
    x1y1 = anchor_points - lt
    x2y2 = anchor_points + rb
    return torch.cat((x1y1, x2y2), dim)

_m.dist2bbox.__code__ = _dist2bbox.__code__


# DeepStream output đơn giản: transpose + lấy max score
class DeepStreamOutput(nn.Module):
    def forward(self, x):
        x = x.transpose(1, 2)             # [1, nc+4, 8400] → [1, 8400, nc+4]
        boxes = x[:, :, :4]
        scores, labels = torch.max(x[:, :, 4:], dim=-1, keepdim=True)
        return torch.cat([boxes, scores, labels.to(boxes.dtype)], dim=-1)


def main():
    import warnings
    warnings.filterwarnings("ignore")

    print(f"\n🚀 Export YOLO26n Pruned (Elegant) → DeepStream ONNX")
    print(f"📦 Đang tải: {WEIGHTS_PATH}")

    # 1. Load checkpoint
    ckpt = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=False)
    print(f"   Keys: {list(ckpt.keys())}")

    # 2. Dựng model gốc từ yaml
    yaml_cfg = ckpt.get("yaml_config") or ckpt.get("yaml")
    model = DetectionModel(yaml_cfg, nc=ckpt.get("nc"))
    if "names" in ckpt:
        model.names = ckpt["names"]

    # 3. Restore kiến trúc pruned bằng mto.restore()
    modelopt_state = ckpt.get("modelopt_state")
    if modelopt_state is None:
        raise RuntimeError(
            "❌ Checkpoint KHÔNG CÓ modelopt_state!\n"
            "   Dùng export_yolo26_deepstream.py (bản thủ công) cho file best.pt cũ."
        )

    print("🔧 mto.restore()...")
    buf = io.BytesIO()
    torch.save({
        "modelopt_state": modelopt_state,
        "model_state_dict": ckpt["model"]
    }, buf)
    buf.seek(0)
    mto.restore(model, buf)

    # 4. Nạp trọng số
    model.load_state_dict(ckpt["model"], strict=False)
    print("✅ Kiến trúc + trọng số đã khớp!")

    # 5. Optimize cho deployment
    model.eval().float()
    try:
        model = model.fuse()
        print("⚡ Fuse OK")
    except Exception as e:
        print(f"Bỏ qua fuse: {e}")

    for m in model.modules():
        if isinstance(m, (Detect, v10Detect)):
            m.dynamic = False
            m.export = True
            m.format = "onnx"
        elif isinstance(m, C2f):
            m.forward = m.forward_split

    # 6. Đóng gói với DeepStream output
    ds_model = nn.Sequential(model, DeepStreamOutput())
    ds_model.eval()

    # 7. Export ONNX
    print(f"⚙️ Xuất ONNX (Opset {OPSET})...")
    dummy_input = torch.zeros(1, 3, IMGSZ, IMGSZ)

    from torch.onnx import utils as torch_utils
    torch_utils._export(
        ds_model, dummy_input, OUTPUT_ONNX,
        opset_version=OPSET,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
    )

    # 8. Simplify
    print("✨ Simplify...")
    try:
        import onnxsim
        model_onnx = onnx.load(OUTPUT_ONNX)
        model_simplified, check = onnxsim.simplify(model_onnx)
        if check:
            onnx.save(model_simplified, OUTPUT_ONNX)
            print(f"✅ THÀNH CÔNG! → {OUTPUT_ONNX}")
        else:
            print("❌ Simplify thất bại, file vẫn được lưu.")
    except ImportError:
        print(f"⚠️ onnxsim chưa cài. File đã lưu tại: {OUTPUT_ONNX}")


if __name__ == "__main__":
    main()
