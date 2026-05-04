import torch
ckpt = torch.load('models/v8n_ModelOpt_Physical_Pruning_KD/weights/best.pt', map_location='cpu', weights_only=False)
print(type(ckpt))
print(ckpt.keys() if isinstance(ckpt, dict) else "not a dict")
if isinstance(ckpt, dict):
    print('model:', type(ckpt.get('model')))
    print('ema:', type(ckpt.get('ema')))
    print('state_dict:', 'state_dict' in ckpt)