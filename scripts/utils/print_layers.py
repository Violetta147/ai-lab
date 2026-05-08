from ultralytics import YOLO
from pprint import pprint

model = YOLO("D:\\datas\\Final.yolov8\\models\\best.pt")
# checkpoint metadata
pprint(model.ckpt.keys())

print("\n========== METADATA ==========\n")

for k, v in model.ckpt.items():
    if k != "model":   # model object rất dài
        print(f"{k}:")
        print(v)
        print()