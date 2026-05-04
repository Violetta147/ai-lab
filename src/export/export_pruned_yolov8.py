import io
import torch
import torch.nn as nn
import onnx
import onnxsim
import modelopt.torch.opt as mto

from ultralytics.nn.tasks import DetectionModel
from ultralytics.nn.modules import C2f, Detect
import ultralytics.utils.tal as _m

# ================= Configuration =================
WEIGHTS_PATH = r"d:\datas\Final.yolov8\models\v8n_ModelOpt_Physical_Pruning_KD\weights\best.pt"
OUTPUT_ONNX = r"d:\datas\Final.yolov8\deepstream\best_deepstream_nvidia_output2.onnx"
IMGSZ = 640
OPSET = 12
# =================================================

# Patch Ultralytics' distance2bbox for ONNX/TensorRT compatibility
def _dist2bbox(distance, anchor_points, xywh=False, dim=-1):
    lt, rb = distance.chunk(2, dim)
    x1y1 = anchor_points - lt
    x2y2 = anchor_points + rb
    return torch.cat((x1y1, x2y2), dim)

_m.dist2bbox.__code__ = _dist2bbox.__code__


# Tensor reduction (moves post-processing from CPU to GPU)
class DeepStreamOutput(nn.Module):
    def forward(self, x):
        x = x.transpose(1, 2)  # [1, 84, 8400] -> [1, 8400, 84]
        boxes = x[:, :, :4]
        scores, labels = torch.max(x[:, :, 4:], dim=-1, keepdim=True)
        return torch.cat([boxes, scores, labels.to(boxes.dtype)], dim=-1)


def main():
    print(f"Loading pruned checkpoint: {WEIGHTS_PATH}")
    
    # 1. Load ModelOpt checkpoint (Dict only, no model object)
    ckpt = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=False)
    print(ckpt.keys())
    # 2. Reconstruct architecture & apply pruning masks
    model = DetectionModel(ckpt["yaml"], nc=ckpt.get("nc"))
    model.names = ckpt["names"]
    
    # The BytesIO buffer is a workaround to bypass ModelOpt's buggy metadata parser
    buf = io.BytesIO()
    # [FIX 1] Bọc đủ cả lõi mô hình (modelopt_state) lẫn trọng số (state_dict) vào rương ảo.
    # Nhờ cái này mà mto.restore() sẽ không bị phàn nàn 'KeyError: model_state_dict' nữa.
    torch.save({
        "modelopt_state": ckpt["modelopt_state"],
        "model_state_dict": ckpt["state_dict"]
    }, buf)
    buf.seek(0)
    mto.restore(model, buf)
    
    model.load_state_dict(ckpt["state_dict"], strict=False)

    # 3. Optimize network structure for deployment
    model.eval()
    model.float()
    model = model.fuse()

    for m in model.modules():
        if isinstance(m, Detect):
            m.dynamic = False
            m.export = True
            m.format = "onnx"
        elif isinstance(m, C2f):
            m.forward = m.forward_split

    # 4. Attach the DeepStream hardware-optimization head
    ds_model = nn.Sequential(model, DeepStreamOutput())

    # 5. Export to ONNX
    print("Exporting ONNX graph...")
    # [FIX 2] Bật chế độ suy luận (eval). Lệnh này sẽ gộp và ép phẳng các layer huấn luyện 
    # (như biến động của BatchNorm). Nhờ vậy lược đồ mạng nơ ron đạt độ ổn định đủ để lưu 
    # xuống ONNX chuẩn Opset 12 cũ rích, vượt chuẩn TensorRT 8.2 trên Jetson Nano.
    ds_model.eval()
    dummy_input = torch.zeros(1, 3, IMGSZ, IMGSZ)

    # [FIX 3] Bỏ qua bộ xuất ONNX Dynamo mới của PyTorch 2.6 bằng cách gọi thẳng 
    # API nội bộ `torch.onnx.utils._export` (bộ xuất TorchScript kinh điển).
    # Nước đi này giúp bỏ qua hoàn toàn cái bẫy Opset 18 và mọi lỗi Resize hay JIT Trace!
    from torch.onnx import utils as torch_utils
    torch_utils._export(
        ds_model,
        dummy_input,
        OUTPUT_ONNX,
        opset_version=OPSET,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
    )

    # 6. Simplify the ONNX graph
    print("Simplifying ONNX graph via onnxsim...")
    model_onnx = onnx.load(OUTPUT_ONNX)
    model_simplified, check = onnxsim.simplify(model_onnx)
    assert check, "ONNX simplification failed."
    onnx.save(model_simplified, OUTPUT_ONNX)

    print(f"✅ Successfully exported highly-optimized model: {OUTPUT_ONNX}")


if __name__ == "__main__":
    main()
