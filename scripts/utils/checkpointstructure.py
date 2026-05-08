# =========================================================
# Script kiểm tra cấu trúc tổng quát của checkpoint .pt
#
# Mục đích:
# - Xác định cấu trúc bên trong file checkpoint PyTorch/YOLO
# - Kiểm tra checkpoint chứa những thành phần nào:
#     + model
#     + ema
#     + state_dict
#     + optimizer
#     + metadata
#
# - Hỗ trợ debug lỗi load/export model
# - Phân tích compatibility với ONNX/TensorRT/DeepStream
# - Reverse engineering checkpoint từ source không rõ ràng
#
# Ý nghĩa:
#
# 1. type(ckpt)
#    - Kiểm tra object load lên là kiểu gì
#    - Thông thường:
#         dict
#         OrderedDict
#         torch.nn.Module
#
# 2. ckpt.keys()
#    - Liệt kê toàn bộ metadata và thành phần trong checkpoint
#
# 3. model
#    - Kiểm tra model architecture chính
#    - Nếu là torch.nn.Module:
#         -> Có đầy đủ kiến trúc mạng
#         -> Export dễ hơn
#
# 4. ema
#    - EMA = Exponential Moving Average
#    - YOLO thường lưu model EMA để inference ổn định hơn
#    - Nếu tồn tại:
#         -> Có thể dùng EMA weights thay vì model thường
#
# 5. state_dict
#    - Kiểm tra checkpoint có chứa raw weights hay không
#    - Nếu chỉ có state_dict:
#         -> Phải recreate architecture trước khi load
#
# Script sẽ:
# - Load checkpoint .pt bằng CPU
# - In kiểu dữ liệu checkpoint
# - Liệt kê các key metadata
# - Kiểm tra kiểu dữ liệu của:
#       + model
#       + ema
# - Kiểm tra sự tồn tại của state_dict
#
# Trường hợp sử dụng thực tế:
# - Debug checkpoint YOLO bị lỗi
# - Kiểm tra model trước khi export ONNX
# - Xác định checkpoint dùng cho TensorRT/DeepStream
# - Phân tích checkpoint từ project người khác
# - So sánh model thường và EMA model
# =========================================================
import torch
ckpt = torch.load('models/v8n_ModelOpt_Physical_Pruning_KD/weights/best.pt', map_location='cpu', weights_only=False)
print(type(ckpt))
print(ckpt.keys() if isinstance(ckpt, dict) else "not a dict")
if isinstance(ckpt, dict):
    print('model:', type(ckpt.get('model')))
    print('ema:', type(ckpt.get('ema')))
    print('state_dict:', 'state_dict' in ckpt)