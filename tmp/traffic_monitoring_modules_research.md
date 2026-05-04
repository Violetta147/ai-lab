# Traffic Monitoring System — 14 Module Research

---

## MODULE 1 — Vehicle Detection & Counting

| Repo / Resource | Description | Key Tech |
|---|---|---|
| [arief25ramadhan/vehicle-tracking-counting](https://github.com/arief25ramadhan/vehicle-tracking-counting) | Vehicle tracking + counting using YOLOv8 + ByteTrack | YOLOv8, ByteTrack, TensorRT |
| [VuBacktracking/yolo-bytetrack-vehicle-tracking](https://github.com/VuBacktracking/yolo-bytetrack-vehicle-tracking) | Vehicle tracking + counting with line crossing | YOLOv8, ByteTrack |
| [arafathosense/Vehicle-Detection-and-Counting](https://github.com/arafathosense/Vehicle-Detection-and-Counting) | Detect + count multiple vehicle types, SORT tracker | YOLOv8, NumPy, SORT |
| [RayanAIX/vehicle-detection-and-counting-yolov8](https://github.com/RayanAIX/vehicle-detection-and-counting-yolov8) | Real-time counting, Streamlit demo, car/motorcycle/bus/truck | YOLOv8, OpenCV, Streamlit |
| [anujeshify/Traffic-Counting-Program-using-YOLOv8](https://github.com/anujeshify/Traffic-Counting-Program-using-YOLOv8) | Automate counting, output to text file | YOLOv8m, OpenCV |
| Stanford CS231A — Vehicle Counting with YOLO + DeepSORT | Academic paper on counting via line crossing + DeepSORT | YOLOv5/v8, DeepSORT |

---

## MODULE 2 — Object Tracking

| Repo / Resource | Description | Key Tech |
|---|---|---|
| [FoundationVision/ByteTrack](https://github.com/FoundationVision/ByteTrack) | **ECCV 2022** — SOTA tracker. 80.3 MOTA on MOT17. Associates every detection box, not just high-confidence | YOLOX, Kalman Filter |
| [hulkwork/yolov8_tracking](https://github.com/hulkwork/yolov8_tracking) | Multi-tracker framework: DeepOCSORT, StrongSORT, OCSORT, ByteTrack, BoTSORT. Hyperparameter tuning supported | YOLOv8, OSNet ReID |
| [Ultralytics Built-in Tracking](https://docs.ultralytics.com/modes/track/) | `model.track()` — supports BoT-SORT and ByteTrack natively | YOLOv8/YOLO26, BoT-SORT |
| **BoT-SORT vs ByteTrack Benchmark** (Thesis, 2024) | Comparative analysis on MOT17: BoT-SORT better MOTP, ByteTrack better FPS | YOLOv8, MOTA/MOTP/FPS |

**Tracker Selection Guide:**
- **ByteTrack**: Fastest, best for real-time edge. Low-confidence recovery
- **BoT-SORT**: Better precision (MOTP). Uses camera motion compensation + ReID
- **DeepSORT**: Classic. Needs ReID model → slower. Good for re-identification
- **StrongSORT**: Enhanced DeepSORT. NSA Kalman + ECC motion + OSNet ReID

---

## MODULE 3 — Bird's Eye View / Homography

| Repo / Resource | Description | Key Tech |
|---|---|---|
| [ika-rwth-aachen/Cam2BEV](https://github.com/ika-rwth-aachen/Cam2BEV) | Multi-camera → BEV using IPM + DeepLab/uNetXST. Semantic segmentation in BEV space | TensorFlow, IPM, DeepLab |
| [ayushgoel24/Birds-Eye-View-from-Multiple-Vehicle-Camera-Images](https://github.com/ayushgoel24/Birds-Eye-View-from-Multiple-Vehicle-Camera-Images) | U-Net backbone + Spatial Transformer for multi-cam BEV | PyTorch, U-Net |
| [SAmmarAbbas/birds-eye-view](https://github.com/SAmmarAbbas/birds-eye-view) | Single image → BEV via CNN-predicted homography (Andrew Zisserman group) | VGG-16, Inception, CARLA |
| OpenCV BEV Gist — `cv2.warpPerspective` | Basic perspective transform with trackbar UI for alpha/beta/gamma | OpenCV, Python/C++ |
| MATLAB `birdsEyeView` | Built-in IPM function for ADAS/traffic applications | MATLAB, monoCamera |

**Key Concept**: Homography matrix H maps pixel coordinates → ground plane coordinates. Need 4+ corresponding points (anchor points on road markings, lane lines, or known distances).

---

## MODULE 4 — Traffic Density & Pressure

| Repo / Resource | Description | Key Tech |
|---|---|---|
| [FarzadNekouee/YOLOv8_Traffic_Density_Estimation](https://github.com/FarzadNekouee/YOLOv8_Traffic_Density_Estimation) | Fine-tuned YOLOv8, count per frame, classify density ("Smooth"/"Heavy") | YOLOv8, Roboflow dataset |
| [pratheeshkumar99/Real-Time-Vehicle-Detection-and-Traffic-Flow-Classification-System](https://github.com/pratheeshkumar99/Real-Time-Vehicle-Detection-and-Traffic-Flow-Classification-System) | Per-lane counting, traffic intensity, ONNX export | YOLOv8, PyTorch, ONNX |
| [ijas9118/Real-time-Traffic-Analysis-YOLOv8](https://github.com/ijas9118/Real-time-Traffic-Analysis-YOLOv8) | Detection + classification + tracking + parking safety module | YOLOv8 |
| ITS paper — YOLOv8n for real-time vehicle detection (IIETA) | Nano model for edge ITS: counting, classification, OCR, density | YOLOv8n, edge device |

**Density Metrics**: Vehicles/km/lane, area occupancy ratio, Level of Service (LOS A-F).

---

## MODULE 5 — Speed Estimation

| Repo / Resource | Description | Key Tech |
|---|---|---|
| [swhan0329/vehicle_speed_estimation](https://github.com/swhan0329/vehicle_speed_estimation) | **Best-in-class** — Modular, per-lane speed estimation from CCTV. Calibration tool included, YAML config | Optical Flow, OpenCV |
| Monocular Vehicle Speed Estimation (TU Wien Thesis, 2025) | YOLOv8 + ByteTrack + ArcGIS homography calibration on Hailo-8 edge | YOLOv8, ByteTrack, Hailo-8 |
| PMC Paper — YOLOv7 + DeepSORT speed measurement | 2D positioning + distance model + camera calibration | YOLOv7, DeepSORT |
| [lovnishverma/vehicle-speed-estimation](https://github.com/lovnishverma/vehicle-speed-estimation) | YOLOv10 + DeepSORT, perspective transformation | YOLOv10, DeepSORT |

**Speed Estimation Pipeline**:
1. Detect vehicles (YOLO)
2. Track across frames (ByteTrack/DeepSORT)
3. Calibrate: px_to_meter ratio via homography or known road dimensions
4. Speed = distance_meters / time_seconds (between frames)

---

## MODULE 6 — Lane Detection & Road Segmentation

| Repo / Resource | Description | Key Tech |
|---|---|---|
| [Turoad/CLRNet](https://github.com/Turoad/CLRNet) | **CVPR 2022** — Cross Layer Refinement Network. SOTA on CULane + TuSimple | PyTorch, DLA34 backbone |
| [hirotomusiker/CLRerNet](https://github.com/hirotomusiker/CLRerNet) | **WACV 2024** — Improved CLRNet with LaneIoU. 81.43 F1 on CULane | PyTorch, DLA34 |
| Ultra-Fast Lane Detection (ONNX) | Lightweight, Jetson Xavier AGX tested. 4 lanes max | ONNX, TensorRT |
| [louislelay/Lane-Detection-and-Vehicle-Tracking](https://github.com/louislelay/Lane-Detection-and-Vehicle-Tracking) | C++ OpenCV lane detection + vehicle tracking | C++, OpenCV |

**Per-lane counting**: Combine lane detection output with vehicle detections. Assign each vehicle to a lane polygon → count per lane.

---

## MODULE 7 — Dashboard & Visualization

| Repo / Resource | Description | Key Tech |
|---|---|---|
| [vietanhlee/Smart-Traffic-Monitoring-System](https://github.com/vietanhlee/Smart-Traffic-Monitoring-System) | **Full system** — YOLOv8 detection, speed/count per road, interactive dashboard, AI chatbot (ReAct agent) | FastAPI, React, PostgreSQL |
| Streamlit Traffic Dashboard pattern | Build real-time dashboard with `st.metric`, `plotly`, live video | Streamlit, Plotly |
| Gradio ML interface | Quick demo UI for model inference with webcam/video input | Gradio, Python |
| Grafana + InfluxDB pattern | Time-series metrics (vehicle count/min, avg speed), real-time alerting | Grafana, InfluxDB, MQTT |

**Recommended Stack**: FastAPI (backend) + React/Streamlit (frontend) + PostgreSQL/InfluxDB (storage) + WebSocket (real-time).

---

## MODULE 8 — Heatmap & Trajectory

| Resource | Description | Key Tech |
|---|---|---|
| [Isarsoft Perception](https://www.isarsoft.com/article/using-heat-maps-to-analyze-traffic-flow-the-isarsoft-approach) | Commercial tool: position map, path map, velocity map, dwell time map, trajectory map | Thermal imaging, commercial |
| HAL Thesis — Visualization of Spatial and Temporal Road Traffic Data | Academic survey: heatmaps, flow maps, TripVista, ThemeRiver | D3.js, matplotlib |
| TripVista — Triple Perspective Visual Trajectory Analytics | Traffic view + ThemeRiver + PCP for directional flow patterns | Academic |
| OpenCV Heatmap approach | Accumulate tracked positions → Gaussian blur → apply colormap | OpenCV, `cv2.applyColorMap` |

**DIY Heatmap**: Maintain a 2D accumulator array (H×W). For each tracked vehicle, increment pixels along trajectory. Apply Gaussian blur + `cv2.COLORMAP_JET`.

---

## MODULE 9 — Anchor Points & Calibration

| Repo / Resource | Description | Key Tech |
|---|---|---|
| [kocurvik/deep_vp](https://github.com/kocurvik/deep_vp) | **ICANN 2021** — Traffic Camera Calibration via Vehicle Vanishing Point Detection. Auto calibrate without manual measurement | CNN, BrnoCompSpeed |
| [Algorithms for Automated Driving — Vanishing Point Calibration](https://thomasfermi.github.io/Algorithms-for-Automated-Driving/) | Interactive tutorial: vanishing point → yaw/pitch → homography | Python, lane detection |
| [geekymonk123/Real-time-traffic-monitoring-system](https://github.com/geekymonk123/Real-time-traffic-monitoring-system) | Single camera: detection + speed estimation + license plate | OpenCV, YOLOv7 |
| TU Wien — ArcGIS-based homography calibration tool | Select points on satellite map + camera view → auto-generate H matrix | ArcGIS, GPS, OpenCV |

**Calibration Methods:**
1. **Manual**: Select 4+ corresponding points (image ↔ ground truth coordinates)
2. **Vanishing Point**: Detect lane line convergence → compute camera pitch/yaw
3. **Known Dimensions**: Use road markings (lane width = 3.5m) as reference
4. **GPS/Map-based**: Match camera view points to satellite coordinates

---

## MODULE 10 — Traffic Signal & Control Integration

| Repo / Resource | Description | Key Tech |
|---|---|---|
| [RituPande/DQL-TSC](https://github.com/RituPande/DQL-TSC) | Adaptive traffic signal control using Deep Q-Learning + SUMO | DQN, SUMO simulator |
| [quantumiracle/Reinforcement_Learning_for_Traffic_Light_Control](https://github.com/quantumiracle/Reinforcement_Learning_for_Traffic_Light_Control) | DQN + DDPG for "Green Wave" phenomenon. **NIPS 2018 Workshop** | DQN, DDPG, OpenAI Gym |
| [DaRL-LibSignal/awesome-RL-traffic-signals](https://github.com/DaRL-LibSignal/awesome-RL-traffic-signals) | **Curated list** — 80+ papers on RL for traffic signal control | Survey, paper list |
| [TJ1812/Adaptive-Traffic-Signal-Control](https://github.com/TJ1812/Adaptive-Traffic-Signal-Control-Using-Reinforcement-Learning) | Q-Learning approximation with SUMO | DQN, SUMO |

**Integration Pattern**: CV system outputs queue length/density per lane → RL agent optimizes green phase duration → send commands to traffic controller via API.

---

## MODULE 11 — Full Pipeline / End-to-End Projects

| Repo / Resource | Description | Key Tech |
|---|---|---|
| **NVIDIA Jetson Platform Services** — [Traffic Analytics](https://developer.nvidia.com/blog/generate-traffic-insights-using-yolov8-and-nvidia-jetpack-6-0/) | **End-to-end**: VST (video storage) + DeepStream (detection) + YOLOv8 + API for tripwire counting, trajectory analysis | JetPack 6.0, DeepStream |
| [marcoslucianops/DeepStream-Yolo](https://github.com/marcoslucianops/DeepStream-Yolo) | DeepStream SDK 5.1–8.0 for ALL YOLO models. dGPU + Jetson | DeepStream, TensorRT |
| [vietanhlee/Smart-Traffic-Monitoring-System](https://github.com/vietanhlee/Smart-Traffic-Monitoring-System) | Full stack: backend (FastAPI) + AI models + dashboard + chatbot | YOLOv8, FastAPI, React |
| Seeed Studio — [Traffic Management with DeepStream](https://wiki.seeedstudio.com/Traffic-Management-DeepStream-SDK/) | Pre-trained TAO models (DashCamNet + VehicleMakeNet + VehicleTypeNet) | DeepStream, TAO, Jetson |

---

## MODULE 12 — Datasets

| Dataset | Type | Size | Classes | Source |
|---|---|---|---|---|
| **UA-DETRAC** | Detection + Tracking | 140K frames, 100 videos, 8250 vehicles | car, bus, van, others | 24 locations, Canon camera |
| **MIO-TCD** | Classification + Localization | ~137K images | 11 classes (car, truck, bus, motorcycle, bicycle, pedestrian, etc.) | Real traffic surveillance |
| **CityFlow** | Multi-camera tracking | 40 cameras, 200K+ boxes | vehicle | Urban intersections |
| **VisDrone** | Aerial detection | 10K+ images, 261K+ instances | 10 classes (pedestrian, car, van, truck, bus, etc.) | Drone footage |
| **UIT-VinaDeveS22** | Vietnamese traffic | 6 videos, 720×1280 | bicycle, motorcycle, car, van, truck, bus, fire truck | Vietnamese DoT cameras |
| **BrnoCompSpeed** | Speed estimation | Multiple cameras | vehicles | Czech Republic, ground truth speed |
| **CULane** | Lane detection | 133K frames | lane markings | 6 scenarios (normal, crowd, curve, etc.) |
| **TuSimple** | Lane detection | 6408 clips | lane lines | Highway, USA |

---

## MODULE 13 — Research Papers

| Paper / Survey | Year | Topic | Key Finding |
|---|---|---|---|
| "Intelligent Traffic Monitoring with YOLOv11" (arXiv 2604.04080) | 2025 | Vehicle detection + counting + density | mAP 92.4%, IoU 0.85 |
| "Reducing Traffic Congestion Using YOLOv8" (Pudaruth, 2024) | 2024 | Real-time monitoring Mauritius | 96.1% counting, 94.4% classification accuracy |
| "METRIC — Monitoring and Prediction of Road Traffic Using Drones" | 2025 | UAV-based traffic flow, AVIATOR system | BEV + optical flow + speed estimation |
| "What Demands Attention in Urban Street Scenes?" (arXiv 2507.06513) | 2025 | Survey: datasets + methods for traffic scene understanding | Comprehensive comparison of datasets |
| "A Survey of Traffic Data Visualization" | Academic | Heatmaps, flow maps, trajectory clustering | TripVista, DBSCAN/OPTICS clustering |
| "ByteTrack" (ECCV 2022) | 2022 | Multi-object tracking | 80.3 MOTA, 77.3 IDF1 on MOT17 |
| "CLRNet" (CVPR 2022) | 2022 | Lane detection | Cross Layer Refinement |
| "RL for Traffic Signal Control" (awesome-RL-traffic-signals) | Survey | 80+ papers on RL for TSC | DQN, DDPG, PPO, multi-agent |

---

## MODULE 14 — Specific Tools & Libraries

| Tool | Purpose | GitHub | Stars |
|---|---|---|---|
| **supervision** (Roboflow) | Reusable CV tools: annotate, track, count in zone/line, save to CSV | [roboflow/supervision](https://github.com/roboflow/supervision) | 25K+ |
| **norfair** (Tryolabs) | Lightweight multi-object tracker. Works with ANY detector. Kalman filter based | [tryolabs/norfair](https://github.com/tryolabs/norfair) | 2.3K+ |
| **ByteTrack** | ECCV 2022 SOTA tracker. Associates every detection box | [FoundationVision/ByteTrack](https://github.com/FoundationVision/ByteTrack) | 4.5K+ |
| **DeepStream-Yolo** | NVIDIA DeepStream for all YOLO models. Production-grade | [marcoslucianops/DeepStream-Yolo](https://github.com/marcoslucianops/DeepStream-Yolo) | 2K+ |
| **Torch-Pruning** | DepGraph structured pruning for ANY model (CVPR 2023) | [VainF/Torch-Pruning](https://github.com/VainF/Torch-Pruning) | 3K+ |
| **filterpy** | Kalman Filter, Extended KF, Unscented KF for smooth tracking | [rlabbe/filterpy](https://github.com/rlabbe/filterpy) | 3K+ |
| **vidgear** | High-performance video processing. Multi-source streaming | [abhiTronix/vidgear](https://github.com/abhiTronix/vidgear) | 3.3K+ |
| **learnopencv** (Satya Mallick) | 500+ OpenCV/DL tutorials with code. Heatmaps, detection, tracking | [spmallick/learnopencv](https://github.com/spmallick/learnopencv) | 21K+ |

---

## Quick Reference — Recommended Stack for Jetson Nano

```
Detection:     YOLOv8n (pruned + KD) → ONNX → TensorRT FP16
Tracking:      ByteTrack (fastest, ~5ms overhead)
Counting:      supervision LineZone / PolygonZone
Speed:         Homography calibration → px_to_meter → distance/time
BEV:           cv2.getPerspectiveTransform + warpPerspective
Dashboard:     FastAPI backend + Streamlit frontend (on separate machine)
Calibration:   4-point manual or vanishing point auto
Deployment:    C++ TensorRT inference (2-3× faster than Python)
Alternative:   DeepStream SDK (if using Jetson with JetPack 6+)
```

---

## Search Tips (for further exploration)

High-quality repos:
```
site:github.com stars:>100 traffic vehicle [keyword] python
```

Academic papers:
```
site:arxiv.org OR site:paperswithcode.com traffic [keyword] 2024
```
