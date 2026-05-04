# %% [markdown]
# # YOLO26 on NVIDIA Jetson using DeepStream SDK and TensorRT
# Source: https://docs.ultralytics.com/guides/deepstream-nvidia-jetson/
#
# Deploy YOLO26 on NVIDIA Jetson devices using DeepStream SDK for
# real-time streaming analytics and TensorRT for maximum inference performance.
#
# ## What is NVIDIA DeepStream?
# NVIDIA DeepStream SDK is a streaming analytics toolkit based on GStreamer
# for AI-based multi-sensor processing, video, audio, and image understanding.
# It enables real-time analytics on video, image, and sensor data with
# neural networks and complex processing (tracking, encoding, rendering).
#
# ## Prerequisites
# - NVIDIA Jetson device with JetPack installed
# - DeepStream SDK matching your JetPack version:
#   - JetPack 4.6.4 → DeepStream 6.0.1
#   - JetPack 5.1.3 → DeepStream 6.3
#   - JetPack 6.1 → DeepStream 7.1

# %% [markdown]
# ## Step 1: Install Ultralytics and Clone DeepStream-Yolo
#
# ```bash
# cd ~
# pip install -U pip
# git clone https://github.com/ultralytics/ultralytics
# cd ultralytics
# pip install -e ".[export]" onnxslim
#
# cd ~
# git clone https://github.com/marcoslucianops/DeepStream-Yolo
# cp ~/DeepStream-Yolo/utils/export_yolo26.py ~/ultralytics
# ```

# %% [markdown]
# ## Step 2: Download and Convert Model to ONNX
#
# ```bash
# cd ~/ultralytics
# wget https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26s.pt
#
# # Convert to ONNX (dynamic batch for DeepStream >= 6.1)
# python3 export_yolo26.py -w yolo26s.pt --dynamic
#
# # Optional flags:
# #   --opset 12         (for DeepStream 5.1, remove --dynamic)
# #   -s 1280            (change inference size)
# #   --simplify         (simplify ONNX graph, DeepStream >= 6.0)
# #   --batch 4          (static batch size)
# ```

# %% [markdown]
# ## Step 3: Compile DeepStream Library
#
# ```bash
# cp yolo26s.pt.onnx labels.txt ~/DeepStream-Yolo
# cd ~/DeepStream-Yolo
#
# # Set CUDA version matching JetPack
# export CUDA_VER=10.2   # JetPack 4.6.4
# # export CUDA_VER=11.4 # JetPack 5.1.3
# # export CUDA_VER=12.6 # JetPack 6.1
#
# make -C nvdsinfer_custom_impl_Yolo clean && make -C nvdsinfer_custom_impl_Yolo
# ```

# %% [markdown]
# ## Step 4: Configure DeepStream
#
# ### Edit `config_infer_primary_yolo26.txt`
# ```ini
# [property]
# ...
# onnx-file=yolo26s.pt.onnx
# ...
# num-detected-classes=80
# ...
# ```
#
# ### Edit `deepstream_app_config.txt`
# ```ini
# [primary-gie]
# config-file=config_infer_primary_yolo26.txt
#
# [source0]
# uri=file:///opt/nvidia/deepstream/deepstream/samples/streams/sample_1080p_h264.mp4
# ```

# %% [markdown]
# ## Step 5: Run Inference
#
# ```bash
# deepstream-app -c deepstream_app_config.txt
# ```
#
# The first run generates a TensorRT engine file (slow). Subsequent runs
# are fast.
#
# ### FP16 Precision
# Set in `config_infer_primary_yolo26.txt`:
# ```ini
# model-engine-file=model_b1_gpu0_fp16.engine
# network-mode=2
# ```

# %% [markdown]
# ## INT8 Calibration
#
# For maximum speed with INT8 precision:
#
# ```bash
# export OPENCV=1
# make -C nvdsinfer_custom_impl_Yolo clean && make -C nvdsinfer_custom_impl_Yolo
#
# # Download COCO val2017 for calibration
# mkdir calibration
# for jpg in $(ls -1 val2017/*.jpg | sort -R | head -1000); do
#   cp ${jpg} calibration/
# done
# realpath calibration/*jpg > calibration.txt
#
# export INT8_CALIB_IMG_PATH=calibration.txt
# export INT8_CALIB_BATCH_SIZE=1
# ```
#
# Then update config:
# ```ini
# model-engine-file=model_b1_gpu0_int8.engine
# int8-calib-file=calib.table
# network-mode=1
# ```

# %% [markdown]
# ## MultiStream Setup
#
# Process multiple video streams simultaneously:
#
# ```ini
# [tiled-display]
# rows=2
# columns=2
#
# [source0]
# enable=1
# type=3
# uri=path/to/video1.mp4
# uri=path/to/video2.mp4
# uri=path/to/video3.mp4
# uri=path/to/video4.mp4
# num-sources=4
# ```

# %% [markdown]
# ## Benchmark Results (Jetson Orin NX 16GB, imgsz=640)
#
# | Model | TensorRT FP32 (ms) | TensorRT FP16 (ms) | TensorRT INT8 (ms) |
# |-------|--------------------:|--------------------:|--------------------:|
# | YOLO11n | 8.64 | 5.27 | 4.54 |
# | YOLO11s | 14.53 | 7.91 | 6.05 |
# | YOLO11m | 32.05 | 15.55 | 10.43 |
# | YOLO11l | 39.68 | 19.88 | 13.64 |
# | YOLO11x | 80.65 | 39.06 | 22.83 |
#
# TensorRT consistently delivers the best performance on Jetson hardware.

# %% Local Demo — Export YOLO26 to ONNX for DeepStream
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
print(f"[DEBUG] Model loaded: yolo26n.pt")

onnx_path: str = model.export(format="onnx", dynamic=True, simplify=True)
print(f"[DEBUG] ONNX exported for DeepStream: {onnx_path}")
print("[DEBUG] Copy this file to ~/DeepStream-Yolo/ on your Jetson device")
