import os
import sys
import torch
import torch.nn as nn
import onnx
from onnxsim import simplify
from collections import OrderedDict

# Import components for YOLOv26 (YOLO11)
try:
    from ultralytics.nn.tasks import DetectionModel
    from ultralytics.nn.modules import C2f, Detect, v10Detect
    import ultralytics.utils.tal as _m
except ImportError:
    print("❌ Error: 'ultralytics' is required. Run: pip install ultralytics")
    sys.exit(1)

# Patch logic for TensorRT compatibility
def _dist2bbox(distance, anchor_points, xywh=False, dim=-1):
    lt, rb = distance.chunk(2, dim)
    x1y1 = anchor_points - lt
    x2y2 = anchor_points + rb
    return torch.cat((x1y1, x2y2), dim)

_m.dist2bbox.__code__ = _dist2bbox.__code__

def get_submodule(model, path):
    parts = path.split('.')
    curr = model
    for p in parts:
        if p.isdigit(): curr = curr[int(p)]
        else: curr = getattr(curr, p)
    return curr

def set_submodule(model, path, new_module):
    parts = path.split('.')
    if len(parts) == 1:
        setattr(model, parts[0], new_module)
        return
    parent_path = ".".join(parts[:-1])
    layer_name = parts[-1]
    parent = get_submodule(model, parent_path)
    if layer_name.isdigit(): parent[int(layer_name)] = new_module
    else: setattr(parent, layer_name, new_module)

def repair_pruned_model(model, weights):
    """Physically resizes layers and handles 'groups' for Depthwise Conv."""
    print("🛠️  Performing surgery to match pruned weights...")
    model_state = model.state_dict()
    modules_to_fix = OrderedDict()
    for name, param in weights.items():
        if name in model_state and param.shape != model_state[name].shape:
            path = ".".join(name.split(".")[:-1])
            modules_to_fix[path] = param.shape

    for path in modules_to_fix.keys():
        try:
            target = get_submodule(model, path)
            w_shape = modules_to_fix[path]
            if isinstance(target, nn.Conv2d):
                new_out = w_shape[0]
                if target.groups > 1 and target.in_channels == target.groups:
                    new_groups = new_out
                    new_in = new_out
                else:
                    new_groups = target.groups
                    new_in = w_shape[1] * new_groups
                new_layer = nn.Conv2d(
                    in_channels=new_in, out_channels=new_out,
                    kernel_size=target.kernel_size, stride=target.stride,
                    padding=target.padding, dilation=target.dilation,
                    groups=new_groups, bias=(target.bias is not None)
                )
                set_submodule(model, path, new_layer)
            elif isinstance(target, nn.BatchNorm2d):
                new_layer = nn.BatchNorm2d(num_features=w_shape[0])
                set_submodule(model, path, new_layer)
        except: continue
    print("✅ Surgery complete.")

def main():
    pt_path = "models/khoa/best.pt"
    onnx_path = "models/khoa/YOLO26n_Pruned_Final.onnx"
    device = torch.device("cpu")

    if not os.path.exists(pt_path):
        print(f"❌ Error: {pt_path} not found!")
        return

    print(f"⏳ Loading YOLOv26n: {pt_path}")
    ckpt = torch.load(pt_path, map_location='cpu', weights_only=False)
    
    # 1. Build & Repair
    model = DetectionModel(ckpt['yaml_config'])
    repair_pruned_model(model, ckpt['model'])
    model.load_state_dict(ckpt['model'], strict=True)

    # 2. STRIP THE HEAD (Ultimate fix for 'Mod' operator)
    print("✂️  Stripping Detection Head (Layer 23) for TensorRT 8.0 compatibility...")
    # We only keep the backbone and neck. Output will be 3 feature maps.
    model.model = nn.Sequential(*(list(model.model.children())[:-1]))

    model.to(device).eval().float()

    # 3. Export Headless ONNX
    print(f"🚀 Exporting Headless ONNX (Opset 11)...")
    dummy_input = torch.randn(1, 3, 640, 640).to(device)
    
    torch.onnx.export(
        model, dummy_input, onnx_path,
        opset_version=11, do_constant_folding=True,
        input_names=["input"],
        output_names=["feat_stride_8", "feat_stride_16", "feat_stride_32"]
    )

    # 4. Final Simplify
    print("✨ Simplifying graph...")
    try:
        onnx_model = onnx.load(onnx_path)
        model_simp, check = simplify(onnx_model)
        if check:
            onnx.save(model_simp, onnx_path)
            print(f"✅ SUCCESS: Headless model saved at:\n👉 {onnx_path}")
    except Exception as e:
        print(f"❌ Simplify failed: {e}")

if __name__ == "__main__":
    main()
