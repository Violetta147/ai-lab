import io
import os
import sys
import types
import onnx
import torch
import torch.nn as nn
from collections import OrderedDict
from copy import deepcopy

from ultralytics.nn.tasks import DetectionModel
from ultralytics.nn.modules import C2f, Detect, v10Detect
import ultralytics.utils
import ultralytics.models.yolo
import ultralytics.utils.tal as _m

# Vá lỗi module map của Ultralytics
sys.modules["ultralytics.yolo"] = ultralytics.models.yolo
sys.modules["ultralytics.yolo.utils"] = ultralytics.utils

# ==============================================================================
# TƯ DUY DEEPSTREAM-YOLO (Nhưng điều chỉnh cho YOLO26)
# Model YOLO26 của bạn được train theo kiểu YOLOv5 (dùng .exp() cho W/H) thay vì DFL
# Nên không thể dùng hàm _dist2bbox tiêu chuẩn của Ultralytics được!
# ==============================================================================
class YOLO26DeepStreamDecodedWrapper(nn.Module):
    def __init__(self, model, normalize=False, img_size=640.0):
        super().__init__()
        self.model_layers = model.model
        self.detect = self.model_layers[23] 
        self.nl = self.detect.nl 
        self.nc = self.detect.nc 
        self.strides = [8.0, 16.0, 32.0]
        self.normalize = normalize
        self.img_size = float(img_size)

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
        for i in range(self.nl):
            b = self.detect.cv2[i](feats[i])
            c = self.detect.cv3[i](feats[i])
            
            b_box = b[:, :4, :, :]
            h, w = b_box.shape[2:]
            
            y = torch.arange(h).to(b_box.device)
            x_g = torch.arange(w).to(b_box.device)
            grid_y, grid_x = torch.meshgrid(y, x_g, indexing='ij')
            
            stride = self.strides[i]
            
            cx = (b_box[:, 0, :, :] + grid_x) * stride
            cy = (b_box[:, 1, :, :] + grid_y) * stride
            wh = b_box[:, 2:4, :, :].exp() * stride
            
            if self.normalize:
                cx = cx / self.img_size
                cy = cy / self.img_size
                wh = wh / self.img_size
                
            decoded_box = torch.stack([cx, cy, wh[:, 0, :, :], wh[:, 1, :, :]], 1)
            combined = torch.cat([decoded_box, c.sigmoid()], 1)
            
            results.append(combined.view(combined.shape[0], combined.shape[1], -1))
            
        return torch.cat(results, 2).transpose(1, 2)

# ==============================================================================
# HÀM PHỤC HỒI MODEL CẮT TỈA (PRUNED) THỦ CÔNG
# ==============================================================================
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
    print("🛠️ Đang sửa lỗi cấu trúc Pruned bằng thuật toán thủ công...")
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

def suppress_warnings():
    import warnings
    warnings.filterwarnings("ignore", category=torch.jit.TracerWarning)
    warnings.filterwarnings("ignore", category=UserWarning)


def main():
    suppress_warnings()
    
    # --- CẤU HÌNH ---
    WEIGHTS_PATH = "models/khoa/best.pt"
    OUTPUT_ONNX = "models/khoa/YOLO26_DeepStream_Elegant.onnx"
    IMGSZ = 640
    OPSET = 12
    # Đã tắt Normalize vì chạy bằng C++ Parser chuẩn của DeepStream-Yolo
    NORMALIZE_BOXES = False 
    # ---------------

    print(f"\n🚀 Khởi động Export YOLO26 (Pruned) -> DeepStream ONNX")
    print(f"📦 Đang tải trọng số từ: {WEIGHTS_PATH}")
    
    ckpt = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=False)
    
    # ==============================================================================
    # 3. PHỤC HỒI MÔ HÌNH BỊ CẮT TỈA
    # ==============================================================================
    # ⛔ Không dùng ModelOpt vì file best.pt này không chứa metadata của modelopt!
    # Phải bắt buộc dùng 'yaml_config' và tự build lại thủ công.
    model = DetectionModel(ckpt["yaml_config"])
    
    repair_pruned_model(model, ckpt['model'])
    model.load_state_dict(ckpt["model"], strict=True)
    
    model.eval()
    model.float()
    
    # Gộp BatchNorm để chạy nhanh hơn (Fuse)
    try:
        from ultralytics.utils.torch_utils import fuse_model
        model = fuse_model(model)
        print("⚡ Đã fuse model thành công.")
    except Exception as e:
        print(f"Bỏ qua fuse: {e}")

    # ==============================================================================
    # 4. CHUẨN BỊ CÁC LỚP DETECT ĐỂ XUẤT ONNX
    # ==============================================================================
    for k, m in model.named_modules():
        if isinstance(m, (Detect, v10Detect)):
            m.dynamic = False
            m.export = True
            m.format = "onnx"
        elif isinstance(m, C2f):
            m.forward = m.forward_split

    # Đóng gói Model với DeepStream Đầu Ra
    ds_model = YOLO26DeepStreamDecodedWrapper(model, normalize=NORMALIZE_BOXES, img_size=IMGSZ)
    ds_model.eval()

    # ==============================================================================
    # 5. XUẤT FILE ONNX TỐI ƯU
    # ==============================================================================
    dummy_input = torch.zeros(1, 3, IMGSZ, IMGSZ)
    
    print(f"⚙️ Bắt đầu xuất file ONNX (Opset {OPSET})...")
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

    print("✨ Đang làm mượt đồ thị (onnxsim)...")
    try:
        import onnxsim
        model_onnx = onnx.load(OUTPUT_ONNX)
        model_simplified, check = onnxsim.simplify(model_onnx)
        if check:
            onnx.save(model_simplified, OUTPUT_ONNX)
            print(f"✅ THÀNH CÔNG! File đã được lưu tại: {OUTPUT_ONNX}")
        else:
            print("❌ Lỗi khi Simplify ONNX!")
    except ImportError:
        print("⚠️ Không tìm thấy onnxsim. Vui lòng cài đặt bằng: pip install onnxsim")

if __name__ == "__main__":
    main()
