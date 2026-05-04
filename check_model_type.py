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
