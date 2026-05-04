import torch
import sys

try:
    ckpt = torch.load('models/khoa/best.pt', map_location='cpu', weights_only=False)
    if isinstance(ckpt, dict):
        for k, v in ckpt.items():
            print(f"KEY: {k} | TYPE: {type(v)}")
    else:
        print(f"TYPE_FOUND: {type(ckpt)}")
except Exception as e:
    print(f"ERROR: {e}")
