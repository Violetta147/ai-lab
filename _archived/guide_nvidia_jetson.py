# %% [markdown]
# # Quick Start: NVIDIA Jetson with Ultralytics YOLO26
# Source: https://docs.ultralytics.com/guides/nvidia-jetson/
#
# Deploy YOLO26 on NVIDIA Jetson devices (Nano, Orin NX, AGX Orin, AGX Thor).
# TensorRT is recommended for maximum inference performance on Jetson.
#
# ## NVIDIA Jetson Series Comparison
#
# | Device | AI Performance | GPU Cores | Memory |
# |--------|---------------|-----------|--------|
# | Jetson AGX Thor | 2070 TFLOPS | 2560 Blackwell | 128GB LPDDR5X |
# | Jetson AGX Orin 64GB | 275 TOPS | 2048 Ampere | 64GB LPDDR5 |
# | Jetson Orin NX 16GB | 100 TOPS | 1024 Ampere | 16GB LPDDR5 |
# | Jetson Orin Nano Super | 67 TOPS | 1024 Ampere | 8GB LPDDR5 |
# | Jetson Nano | 472 GFLOPS | 128 Maxwell | 4GB LPDDR4 |
#
# ## JetPack Compatibility
#
# | Device | JP4 | JP5 | JP6 | JP7 |
# |--------|-----|-----|-----|-----|
# | Jetson Nano | Yes | No | No | No |
# | Jetson AGX Orin | No | Yes | Yes | No |
# | Jetson Orin NX | No | Yes | Yes | No |
# | Jetson AGX Thor | No | No | No | Yes |

# %% [markdown]
# ## Quick Start with Docker
#
# The fastest way to get started:
#
# ```bash
# # JetPack 6
# t=ultralytics/ultralytics:latest-jetson-jetpack6
# sudo docker pull $t && sudo docker run -it --ipc=host --runtime=nvidia $t
#
# # JetPack 5
# t=ultralytics/ultralytics:latest-jetson-jetpack5
# sudo docker pull $t && sudo docker run -it --ipc=host --runtime=nvidia $t
#
# # JetPack 7 (AGX Thor)
# t=ultralytics/ultralytics:latest-nvidia-arm64
# sudo docker pull $t && sudo docker run -it --ipc=host --runtime=nvidia $t
# ```

# %% [markdown]
# ## Native Installation (JetPack 6.1)
#
# ```bash
# # 1. Update and install pip
# sudo apt update
# sudo apt install python3-pip -y
# pip install -U pip
#
# # 2. Install ultralytics with export dependencies
# pip install ultralytics[export]
#
# # 3. Reboot
# sudo reboot
#
# # 4. Install PyTorch and Torchvision for ARM64
# pip install https://github.com/ultralytics/assets/releases/download/v0.0.0/torch-2.10.0-cp310-cp310-linux_aarch64.whl
# pip install https://github.com/ultralytics/assets/releases/download/v0.0.0/torchvision-0.25.0-cp310-cp310-linux_aarch64.whl
#
# # 5. Install onnxruntime-gpu for Jetson
# pip install https://github.com/ultralytics/assets/releases/download/v0.0.0/onnxruntime_gpu-1.23.0-cp310-cp310-linux_aarch64.whl
# ```

# %% [markdown]
# ## TensorRT Export and Inference
#
# TensorRT delivers the best inference performance on Jetson by leveraging
# GPU-specific optimizations: layer fusion, precision calibration, kernel auto-tuning.

# %% TensorRT Export and Inference Demo
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
print("[DEBUG] Loaded yolo26n.pt")

print("[DEBUG] Exporting to TensorRT...")
engine_path: str = model.export(format="engine")
print(f"[DEBUG] TensorRT engine: {engine_path}")

trt_model = YOLO(engine_path)
results = trt_model.predict(
    source="https://ultralytics.com/images/bus.jpg",
    imgsz=640,
    conf=0.25,
    verbose=False,
)
print(f"[DEBUG] TensorRT inference: {len(results[0].boxes)} detections")

# %% FP16 TensorRT Export
print("[DEBUG] Exporting to TensorRT FP16...")
fp16_path: str = model.export(format="engine", half=True)
print(f"[DEBUG] TensorRT FP16 engine: {fp16_path}")

# %% [markdown]
# ## NVIDIA Deep Learning Accelerator (DLA)
#
# DLA is specialized hardware on Jetson Orin/Xavier for energy-efficient
# deep learning inference. It offloads tasks from the GPU, enabling lower
# power consumption while maintaining throughput.
#
# ```python
# # Export with DLA (FP16 or INT8 only)
# model.export(format="engine", device="dla:0", half=True)
# ```
#
# Supported devices:
# - Jetson AGX Orin: 2 DLA cores (1.6 GHz)
# - Jetson Orin NX 16GB: 2 DLA cores (614 MHz)
# - Jetson AGX Xavier: 2 DLA cores (1.4 GHz)

# %% [markdown]
# ## Benchmark Results — Jetson AGX Thor (YOLO26, imgsz=640)
#
# | Model | Format | mAP50-95 | Inference (ms) |
# |-------|--------|----------|---------------:|
# | YOLO26n | TensorRT FP32 | 0.4791 | 1.90 |
# | YOLO26n | TensorRT FP16 | 0.4797 | 1.39 |
# | YOLO26n | TensorRT INT8 | 0.4273 | 1.52 |
# | YOLO26s | TensorRT FP32 | 0.5664 | 2.95 |
# | YOLO26s | TensorRT FP16 | 0.5650 | 1.77 |
# | YOLO26m | TensorRT FP32 | 0.6230 | 5.56 |
# | YOLO26m | TensorRT FP16 | 0.6209 | 2.58 |
# | YOLO26l | TensorRT FP16 | 0.6243 | 3.34 |
# | YOLO26x | TensorRT FP16 | 0.6611 | 5.16 |

# %% [markdown]
# ## Best Practices for Jetson Performance
#
# ```bash
# # 1. Enable MAX Power Mode (all CPU/GPU cores active)
# sudo nvpmodel -m 0
#
# # 2. Enable Jetson Clocks (max frequency)
# sudo jetson_clocks
#
# # 3. Install Jetson Stats for monitoring
# sudo pip install jetson-stats
# sudo reboot
# jtop  # launch system monitor
# ```

# %% Reproduce Benchmarks
print("[DEBUG] To reproduce benchmarks on your Jetson:")
print("  from ultralytics import YOLO")
print("  model = YOLO('yolo26n.pt')")
print("  results = model.benchmark(data='coco128.yaml', imgsz=640)")
