from ultralytics import YOLO
model = YOLO("D:/datas/Final.yolov8/project_understand_yolo26n/yolo26n.pt")
print(model.model)