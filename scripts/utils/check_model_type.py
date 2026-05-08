# =========================================================
# Script kiểm tra cấu trúc checkpoint .pt của PyTorch/YOLO
#
# Mục đích:
# - Xác định file model .pt có chứa:
#     + Full model architecture (torch.nn.Module)
#     + Hay chỉ chứa state_dict/weights
#
# - Hỗ trợ debug lỗi load model
# - Kiểm tra khả năng export sang ONNX/TensorRT
# - Kiểm tra mức độ tương thích với DeepStream
# - Phục vụ reverse engineering cấu trúc model
#
# Ý nghĩa:
# - Nếu model là torch.nn.Module:
#       -> Có đầy đủ kiến trúc mạng + weights
#       -> Dễ export ONNX/TensorRT
#       -> Dễ dùng với DeepStream
#
# - Nếu model là OrderedDict:
#       -> Chỉ có weights
#       -> Cần recreate architecture trước khi load
#       -> Export và deployment phức tạp hơn
#
# Script sẽ:
# - Load checkpoint .pt
# - Đọc key "model"
# - In kiểu dữ liệu của model
# - Kiểm tra model có phải torch.nn.Module hay không
# =========================================================
import torch
import sys
from collections import OrderedDict

try:
    ckpt = torch.load('models/khoa/best.pt', map_location='cpu', weights_only=False)
    m = ckpt.get('model')
    print(f"MODEL_TYPE: {type(m)}")
    if isinstance(m, OrderedDict):
         print(f"STATE_DICT_LEN: {len(m)}")
    elif m is not None:
         # Try to see if it has architecture
         print(f"IS_MODULE: {isinstance(m, torch.nn.Module)}")
except Exception as e:
    print(f"ERROR: {e}")
