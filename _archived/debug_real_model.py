import torch
import torch.nn as nn
from collections import OrderedDict
from ultralytics.nn.tasks import DetectionModel

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

class YOLO26DeepStreamDecodedWrapper(nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model_layers = model.model
        self.detect = self.model_layers[23] 
        self.nl = self.detect.nl 
        self.nc = self.detect.nc 
        self.strides = [8.0, 16.0, 32.0]
        
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
            
            # INJECT DEBUG LOGIC FOR GRID 0
            if i == 0:
                b_box = b[:, :4, :, :]
                dx = b_box[:, 0, :, :]
                print("\n" + "="*70)
                print(f"🔎 DEBUG TẠI LỚP DETECT {i} (stride={self.strides[i]}) TRÊN MODEL THẬT!")
                print("="*70)
                print("1. Shape của ảnh mồi đầu vào: [1, 3, 640, 640]")
                print("\n2. Hình dáng thực tế của b_box = b[:, :4, :, :]")
                print(f"   >>> Shape: {b_box.shape}   (Tương đương: [Batch=1, Channels=4 (dx, dy, dw, dh), Height=80, Width=80])")
                
                print("\n3. Hình dáng thực tế của độ lệch trục X (dx = b_box[:, 0, :, :])")
                print(f"   >>> Shape: {dx.shape}   (Tương đương: [Batch=1, Height=80, Width=80])")
                print("\n   👉 Mạng nơ-ron đã dự đoán ra một ma trận 80x80 chứa các 'lực xê dịch' dx.")
                print("   👉 Dưới đây là 3x3 giá trị dx ở góc trên cùng bên trái của ảnh:")
                print(dx[0, 0:3, 0:3])
                print("="*70 + "\n")
                
            b_box = b[:, :4, :, :] 
            h, w = b_box.shape[2:]
            y = torch.arange(h).to(b_box.device)
            x_g = torch.arange(w).to(b_box.device)
            grid_y, grid_x = torch.meshgrid(y, x_g, indexing='ij')
            
            stride = self.strides[i]
            
            cx = ((b_box[:, 0, :, :] + grid_x) * stride) / 640.0
            cy = ((b_box[:, 1, :, :] + grid_y) * stride) / 640.0
            wh = (b_box[:, 2:4, :, :].exp() * stride) / 640.0
            
            decoded_box = torch.stack([cx, cy, wh[:, 0, :, :], wh[:, 1, :, :]], 1)
            combined = torch.cat([decoded_box, c.sigmoid()], 1)
            
            results.append(combined.view(combined.shape[0], combined.shape[1], -1))
        
        return torch.cat(results, 2).transpose(1, 2)

if __name__ == "__main__":
    print("⏳ Đang load model best.pt...")
    pt_path = "models/khoa/best.pt"
    ckpt = torch.load(pt_path, map_location='cpu', weights_only=False)
    
    model = DetectionModel(ckpt['yaml_config'])
    repair_pruned_model(model, ckpt['model'])
    model.load_state_dict(ckpt['model'], strict=True)
    
    wrapper = YOLO26DeepStreamDecodedWrapper(model)
    wrapper.eval().float()
    
    print("🚀 Đang chạy 1 ảnh mồi (dummy image 640x640) qua model...")
    dummy_input = torch.randn(1, 3, 640, 640)
    with torch.no_grad():
        wrapper(dummy_input)
