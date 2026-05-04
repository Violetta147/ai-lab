# %% [markdown]
# # Best Practices for Model Deployment
# Source: https://docs.ultralytics.com/guides/model-deployment-practices/
#
# Model deployment brings a trained model from development into a real-world
# application. This guide covers deployment environments, containerization,
# optimization techniques, troubleshooting, and security considerations.
#
# ## Deployment Environment Options
#
# | Environment | Pros | Cons |
# |-------------|------|------|
# | **Cloud** (AWS, GCP, Azure) | Scalable, powerful GPUs/TPUs, managed services | Cost at scale, latency from distance |
# | **Edge** (Jetson, phones, IoT) | Real-time, low latency, data stays local | Limited compute, harder maintenance |
# | **Local** (on-prem servers) | Full control, data privacy, no cloud costs | Hard to scale, maintenance burden |

# %% Installation
import subprocess
import sys

def _install(packages: list[str]) -> None:
    for pkg in packages:
        print(f"[SETUP] Installing {pkg}...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-U", pkg],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
    print("[SETUP] All packages installed.")

_install(["ultralytics", "onnx"])

# %% [markdown]
# ## Containerization with Docker
#
# Docker ensures consistent behavior across dev, test, and production:
# - **Environment Consistency**: encapsulates model + all dependencies
# - **Isolation**: prevents library/version conflicts
# - **Portability**: runs on any system with Docker
# - **Scalability**: Kubernetes can orchestrate containers
# - **Version Control**: images are versioned for rollback
#
# ### Example Dockerfile for YOLO26
# ```dockerfile
# FROM ultralytics/ultralytics:latest
#
# WORKDIR /app
# COPY ./models/yolo26n.pt /app/models/
# COPY ./scripts /app/scripts/
#
# ENV MODEL_PATH=/app/models/yolo26n.pt
# CMD ["python", "/app/scripts/predict.py"]
# ```

# %% Export Model to Deployment Formats
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
print(f"[DEBUG] Model loaded: {model.model_name}")

print("[DEBUG] Exporting to ONNX...")
onnx_path: str = model.export(format="onnx")
print(f"[DEBUG] ONNX exported: {onnx_path}")

# %% [markdown]
# ## Model Optimization Techniques
#
# ### 1. Model Pruning
# Removes weights that contribute little to output, making the model
# smaller and faster without significantly affecting accuracy.
#
# ### 2. Model Quantization
# Converts weights from FP32 to lower precision (FP16 or INT8):
# - Reduces model size by 2-4x
# - Speeds up inference on supported hardware
# - Quantization-aware training (QAT) preserves accuracy better than
#   post-training quantization
#
# ### 3. Knowledge Distillation
# Trains a smaller "student" model to mimic a larger "teacher" model,
# creating a compact model that retains most of the teacher's accuracy.

# %% Export with FP16 Quantization
print("[DEBUG] Exporting to ONNX with FP16 (half precision)...")
onnx_fp16_path: str = model.export(format="onnx", half=True)
print(f"[DEBUG] ONNX FP16 exported: {onnx_fp16_path}")

# %% Export to OpenVINO
print("[DEBUG] Exporting to OpenVINO format...")
openvino_path: str = model.export(format="openvino", half=True)
print(f"[DEBUG] OpenVINO exported: {openvino_path}")

# %% [markdown]
# ## Troubleshooting Deployment Issues
#
# ### Accuracy Drops After Deployment
# 1. **Check data consistency** — ensure test data matches training distribution
# 2. **Validate preprocessing** — same resize, normalize, transforms as training
# 3. **Evaluate environment** — hardware/software differences can cause discrepancies
# 4. **Monitor inference** — log inputs/outputs at each pipeline stage
# 5. **Review export/conversion** — re-export and verify model integrity
# 6. **Test with controlled dataset** — isolate environment vs data issues
#
# ### Slow Inference
# 1. **Warm-up runs** — exclude initial setup overhead from measurements
# 2. **Optimize inference engine** — use latest drivers and GPU-specific optimizations
# 3. **Async processing** — handle concurrent requests without blocking
# 4. **Profile the pipeline** — identify bottleneck stages (data loading, NMS, etc.)
# 5. **Right precision** — FP16 or INT8 if accuracy allows

# %% Benchmark Model Performance
print("[DEBUG] Running benchmark on ONNX model...")

ov_model = YOLO(openvino_path)
results = ov_model.predict(
    source="https://ultralytics.com/images/bus.jpg",
    imgsz=640,
    conf=0.25,
    verbose=False,
)
print(f"[DEBUG] OpenVINO inference: {len(results[0].boxes)} detections")

# %% [markdown]
# ## Security Considerations
#
# ### Secure Data Transmission
# - Use TLS (Transport Layer Security) to encrypt data in transit
# - End-to-end encryption from source to destination
#
# ### Access Controls
# - Strong authentication (MFA where possible)
# - Role-Based Access Control (RBAC)
# - Audit logs for all model access and changes
#
# ### Model Obfuscation
# - Encrypt model parameters (weights, biases)
# - Obfuscate architecture (rename layers, add dummy layers)
# - Serve in secure enclaves or Trusted Execution Environments (TEE)
#
# ## Summary
# - Choose deployment environment based on latency, scale, and privacy needs
# - Containerize with Docker for reproducibility and portability
# - Optimize with pruning, quantization, and distillation
# - Monitor, troubleshoot, and secure your deployed model
