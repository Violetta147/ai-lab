import torch
import sys

try:
    ckpt = torch.load('models/khoa/best.pt', map_location='cpu', weights_only=False)
    if isinstance(ckpt, dict):
        print(f"KEYS_FOUND: {list(ckpt.keys())}")
        if 'modelopt_state' in ckpt:
            print("MODELOPT: YES")
        else:
            print("MODELOPT: NO")
    else:
        print(f"TYPE_FOUND: {type(ckpt)}")
except Exception as e:
    print(f"ERROR: {e}")
