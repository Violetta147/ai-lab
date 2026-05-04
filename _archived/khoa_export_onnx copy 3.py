import io
import os
import sys
import torch
import torch.nn as nn
import onnx
from onnxsim import simplify
from collections import OrderedDict

# Import components for YOLO26
try:
    from ultralytics.nn.tasks import DetectionModel
    from ultralytics.nn.modules import C2f, Detect, v10Detect
    import ultralytics.utils.tal as _m
except ImportError:
    print("❌ Error: 'ultralytics' is required.")
    sys.exit(1)

class YOLO26DeepStreamWrapper(nn.Module):
    """
    DEDICATED FOR DEEPSTREAM.
    Outputs [1, 8400, 8] layout required by Marcos's custom parser.
    """
    def __init__(self, model):
        super().__init__()
        self.model_layers = model.model
        self.detect = self.model_layers[23] 

    def forward(self, x):
        cache = {}
        for i in range(23):
            layer = self.model_layers[i]
            if hasattr(layer, 'f'):
                if isinstance(layer.f, int):
                    x = layer(cache[layer.f] if layer.f in cache else x)
                else:
                    x = layer([cache[j] if j in cache else x for j in layer.f])
            else:
                x = layer(x)
            cache[i] = x

        feats = [cache[16], cache[19], cache[22]]
        results = []
        for i in range(len(feats)):
            b = self.detect.cv2[i](feats[i])
            c = self.detect.cv3[i](feats[i])
            combined = torch.cat([b, c], 1)
            results.append(combined.view(combined.shape[0], combined.shape[1], -1))
        
        # TRANSPOSE TO [1, 8400, 8] FOR DEEPSTREAM PARSER
        return torch.cat(results, 2).transpose(1, 2)

def repair_pruned_model(model, weights):
    """Surgery for YOLOv26n pruned layers."""
    print("🛠️  Repairing YOLOv26n architecture...")
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
                new_groups = new_out if (target.groups > 1 and target.in_channels == target.groups) else target.groups
                new_in = w_shape[1] * new_groups
                new_layer = nn.Conv2d(in_channels=new_in, out_channels=new_out,
                                      kernel_size=target.kernel_size, stride=target.stride,
                                      padding=target.padding, dilation=target.dilation,
                                      groups=new_groups, bias=(target.bias is not None))
                set_submodule(model, path, new_layer)
            elif isinstance(target, nn.BatchNorm2d):
                new_layer = nn.BatchNorm2d(num_features=w_shape[0])
                set_submodule(model, path, new_layer)
        except: continue

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

def main():
    pt_path = "models/khoa/best.pt"
    onnx_path = "models/khoa/YOLO26n_Pruned_Final.onnx"
    
    ckpt = torch.load(pt_path, map_location='cpu', weights_only=False)
    model = DetectionModel(ckpt['yaml_config'])
    repair_pruned_model(model, ckpt['model'])
    model.load_state_dict(ckpt['model'], strict=True)

    print("📦 Wrapping YOLOv26n for DeepStream [1, 8400, 8] output...")
    final_model = YOLO26DeepStreamWrapper(model)
    final_model.eval().float()

    print(f"🚀 Exporting to ONNX (Opset 11)...")
    dummy_input = torch.randn(1, 3, 640, 640)
    
    from torch.onnx import utils as torch_utils
    torch_utils._export(
        final_model, dummy_input, onnx_path,
        opset_version=11, do_constant_folding=True,
        input_names=["input"], output_names=["output"]
    )

    print("✨ Simplifying graph...")
    try:
        onnx_model = onnx.load(onnx_path)
        model_simp, check = simplify(onnx_model)
        if check:
            onnx.save(model_simp, onnx_path)
            print(f"✅ SUCCESS: DeepStream-compatible YOLO26n exported!")
    except Exception as e:
        print(f"❌ Simplify failed: {e}")

if __name__ == "__main__":
    main()
