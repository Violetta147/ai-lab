# %% [markdown]
# # OpenVINO Inference Optimization for YOLO
# Source: https://docs.ultralytics.com/guides/optimizing-openvino-latency-vs-throughput-modes/
#
# Intel's OpenVINO toolkit optimizes deep learning inference on Intel hardware
# (CPUs, integrated GPUs, dedicated GPUs, VPUs). This guide covers two key
# optimization strategies: **latency** (fastest single response) and
# **throughput** (maximum requests per second).
#
# ## Latency vs Throughput
#
# | Goal | Optimize For | Use Case |
# |------|-------------|----------|
# | **Latency** | Minimum delay per inference | Real-time apps, consumer devices |
# | **Throughput** | Maximum inferences per second | Batch processing, server workloads |

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

_install(["ultralytics", "openvino"])

# %% [markdown]
# ## Optimizing for Latency
#
# ### Key Strategies
# 1. **Single inference per device** — one inference at a time minimizes delay
# 2. **Leverage sub-devices** — multi-socket CPUs / multi-tile GPUs can serve
#    multiple requests with minimal latency increase
# 3. **OpenVINO Performance Hints** — use `LATENCY` mode for device-agnostic tuning
#
# ### Managing First-Inference Latency
# - **Model Caching**: cache compiled models to avoid recompilation on restart
# - **Model Mapping vs Reading**: mapping is faster; use reading for network drives
# - **AUTO Device Selection**: starts on CPU, switches to accelerator when ready

# %% Export to OpenVINO with FP16
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
print("[DEBUG] Loaded yolo26n.pt")

print("[DEBUG] Exporting to OpenVINO FP16...")
ov_path: str = model.export(format="openvino", half=True)
print(f"[DEBUG] OpenVINO model: {ov_path}")

# %% Latency-Optimized Inference
ov_model = YOLO(ov_path)

print("[DEBUG] Running latency-optimized inference...")
results = ov_model.predict(
    source="https://ultralytics.com/images/bus.jpg",
    imgsz=640,
    conf=0.25,
    verbose=False,
)
detections_count: int = len(results[0].boxes)
print(f"[DEBUG] Detections: {detections_count}")

# %% [markdown]
# ## Optimizing for Throughput
#
# ### Approaches
# 1. **Performance Hints** — high-level, future-proof throughput tuning:
#    ```python
#    import openvino.properties.hint as hints
#    config = {hints.performance_mode: hints.PerformanceMode.THROUGHPUT}
#    compiled_model = core.compile_model(model, "GPU", config)
#    ```
# 2. **Explicit Batching and Streams** — fine-grained control over parallelism
#
# ### Application Design for Throughput
# - Process inputs in parallel using the device's full capacity
# - Decompose data flow into concurrent inference requests
# - Use Async API with callbacks to avoid device starvation
#
# ### Multi-Device Execution
# OpenVINO's multi-device mode automatically balances inference across
# available devices (CPU + GPU + VPU) without application-level management.

# %% Batch Inference with OpenVINO
import time

BATCH_SOURCES: list[str] = [
    "https://ultralytics.com/images/bus.jpg",
    "https://ultralytics.com/images/zidane.jpg",
]

print(f"[DEBUG] Running batch inference on {len(BATCH_SOURCES)} images...")
start_time: float = time.perf_counter()

batch_results = ov_model.predict(
    source=BATCH_SOURCES,
    imgsz=640,
    conf=0.25,
    verbose=False,
)

elapsed_ms: float = (time.perf_counter() - start_time) * 1000
print(f"[DEBUG] Batch inference: {elapsed_ms:.1f}ms total")
for i, r in enumerate(batch_results):
    print(f"[DEBUG]   Image {i}: {len(r.boxes)} detections")

# %% [markdown]
# ## Real-World Performance Gains
#
# OpenVINO-optimized YOLO models on Intel hardware can achieve:
# - Up to **3x faster** inference on Intel Xeon CPUs vs PyTorch
# - Even greater acceleration on Intel integrated/dedicated GPUs and VPUs
# - No accuracy compromise — same mAP as PyTorch originals
#
# ## Summary
#
# | Strategy | When to Use | How |
# |----------|------------|-----|
# | Latency mode | Real-time, single inference | `PerformanceMode.LATENCY` hint |
# | Throughput mode | Batch processing, servers | `PerformanceMode.THROUGHPUT` hint |
# | Model caching | Repeated startups | `ov::cache_dir` property |
# | FP16 export | Balance speed + accuracy | `model.export(format="openvino", half=True)` |
# | Multi-device | Multiple Intel accelerators | OpenVINO multi-device mode |
