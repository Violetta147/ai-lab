# Quantization-Aware Distillation (QAD) — INT8/FP16 + Knowledge Distillation

> **QAD** = Quantization-Aware Training (QAT) + Knowledge Distillation (KD)
>
> Nguồn chính:
> - **NVIDIA QAD Technical Report** (2026): https://research.nvidia.com/labs/nemotron/files/NVFP4-QAD-Report.pdf
> - **NVIDIA Blog — QAT + QAD**: https://developer.nvidia.com/blog/how-quantization-aware-training-enables-low-precision-accuracy-recovery/
> - **SQAKD** — Self-Supervised QA Knowledge Distillation (AISTATS 2024): https://proceedings.mlr.press/v238/zhao24d/zhao24d.pdf
> - **Ultralytics TensorRT Integration**: https://docs.ultralytics.com/modes/export/
> - **Ultralytics Jetson Guide**: https://docs.ultralytics.com/guides/nvidia-jetson/

---

## 1. Tổng quan: PTQ vs QAT vs QAD

### 1.1 Ba mức Quantization

| Method | Training cần? | Accuracy | Effort |
|---|---|---|---|
| **PTQ** (Post-Training Quantization) | Không — chỉ calibrate | ★★★ (baseline) | Thấp nhất |
| **QAT** (Quantization-Aware Training) | Có — fake-quantize trong forward pass | ★★★★ | Trung bình |
| **QAD** (Quantization-Aware Distillation) | Có — QAT + KD teacher guidance | ★★★★★ | Cao nhất |

### 1.2 QAD Pipeline

```
Teacher (FP32, pre-trained) ──────────────────────┐
                                                    │ KL Divergence Loss
Student (fake-quantized INT8/FP16 trong forward) ──┘
        │
        ▼
   Backward pass → update FP32 weights của student
        │
        ▼
   After convergence → apply real quantization → deploy
```

**Key**: Student computations are **fake-quantized** during training. Teacher remains **FP32**. Any mismatch from quantization is exposed to the distillation loss → student adapts to low-precision arithmetic.

---

## 2. Jetson Nano — INT8 vs FP16 Reality

### 2.1 Hardware Specs

| Spec | Jetson Nano | Jetson TX2 | Jetson AGX Xavier |
|---|---|---|---|
| **GPU** | 128-core Maxwell | 256-core Pascal | 512-core Volta + NVDLA |
| **FP16 Performance** | **0.5 TFLOPs** | 1.33 TFLOPs | 11 TFLOPs |
| **INT8 Performance** | **—** (không có hardware INT8) | — | **22 TOPS** |
| **DP4A Instruction** | **Không** | Không | **Có** |
| **Memory** | 4 GB LPDDR4 | 8 GB | 16/32 GB |

### 2.2 INT8 trên Jetson Nano — Sự thật

**Maxwell GPU KHÔNG có DP4A instruction** — đây là instruction cần thiết cho INT8 inference hiệu quả trên GPU.

| Capability | Jetson Nano (Maxwell) | Jetson Orin (Ampere) |
|---|---|---|
| FP32 inference | ✅ Hỗ trợ | ✅ |
| FP16 inference | ✅ **Hỗ trợ native** | ✅ |
| INT8 inference | ⚠️ **Software emulation — KHÔNG có hardware acceleration** | ✅ Native |
| INT8 speedup vs FP16 | **~0%** hoặc **chậm hơn** (no DP4A) | 1.5–2× faster |

**Kết luận**: Trên Jetson Nano, **FP16 là precision tối ưu nhất**. INT8 sẽ KHÔNG nhanh hơn FP16 vì thiếu hardware support.

### 2.3 Benchmark YOLOv8 trên Jetson (Ultralytics official)

**Jetson Orin NX** (cho tham khảo — KHÔNG phải Nano):

| Format | mAP50-95 | Inference (ms) | ~FPS |
|---|---|---|---|
| PyTorch | 0.6266 | 46.50 | ~21 |
| TensorRT FP32 | 0.6305 | 27.86 | ~36 |
| **TensorRT FP16** | **0.6309** | **13.50** | **~74** |
| TensorRT INT8 | 0.6291 | 9.12 | ~110 |

**Jetson Nano (original)** — từ các benchmarks thực tế:

| Config | ~FPS | Ghi chú |
|---|---|---|
| YOLOv8n PyTorch (Python) | ~6 FPS | 163–170ms/frame |
| YOLOv8n TensorRT FP16 (Python) | ~15–19 FPS | Estimated |
| YOLOv8n TensorRT FP16 (C++) | **~25–30 FPS** | Loại bỏ Python overhead |
| YOLOv8n Pruned + TensorRT FP16 | **~30–40 FPS** | Depends on pruning ratio |

---

## 3. Pipeline cho Project hiện tại

### 3.1 Pipeline thực tế (Jetson Nano = FP16 only)

```
=== PHASE 1: Training (trên GPU mạnh — H100/A100/RTX) ===

Step 1: Train Teacher YOLOv8m (FP32) — ~50 epochs
Step 2: Prune Student YOLOv8n (FastNAS / Torch-Pruning)
Step 3: KD fine-tune: Teacher FP32 → Student FP32 (MSE/CWD/MGD)
    └── Đây chính là Untitled15.ipynb

=== PHASE 2: Quantization (có thể trên GPU mạnh hoặc Nano) ===

Step 4: Export ONNX (opset=12, dynamic=False, simplify=True)
Step 5: Convert to TensorRT FP16 trên Jetson Nano
    └── trtexec --onnx=model.onnx --saveEngine=model_fp16.engine --fp16

=== PHASE 3: Deploy ===

Step 6: C++ TensorRT inference trên Jetson Nano
    └── ~25-40 FPS depending on model size
```

### 3.2 Pipeline nâng cao (nếu có Jetson Orin hoặc Xavier — INT8 support)

```
=== PHASE 1: Training (GPU mạnh) ===
Step 1–3: Same as above

=== PHASE 2: QAD — Quantization-Aware Distillation ===
Step 4: Fake-quantize student to INT8
Step 5: QAD fine-tune: Teacher FP32 → Student INT8 with KL loss
    └── ~10% of original training schedule
    └── Annealing learning rate

=== PHASE 3: Export ===
Step 6: Export ONNX with Q/DQ nodes
Step 7: TensorRT INT8 engine build
    └── trtexec --onnx=model_qat.onnx --saveEngine=model_int8.engine --int8

=== PHASE 4: Deploy ===
Step 8: 1.5–2× faster than FP16 on Orin/Xavier
```

---

## 4. Chi tiết từng loại Quantization

### 4.1 PTQ (Post-Training Quantization) — Đơn giản nhất

```python
from ultralytics import YOLO

model = YOLO("best.pt")

# FP16 export (Jetson Nano)
model.export(format="engine", half=True, imgsz=640)

# INT8 export (Jetson Orin/Xavier — KHÔNG dùng cho Nano)
model.export(format="engine", int8=True, data="dataset.yaml", imgsz=640)
```

**INT8 PTQ cần calibration dataset** — TensorRT chạy ~100–500 images qua model để xác định dynamic range cho mỗi tensor.

| PTQ Type | Ultralytics Flag | Calibration? | Accuracy Loss |
|---|---|---|---|
| FP16 | `half=True` | Không | ~0% (negligible) |
| INT8 | `int8=True` | Có (`data=...`) | 0.5–2% mAP |

### 4.2 QAT (Quantization-Aware Training) — Training với fake quantize

**Concept**: Insert fake quantize/dequantize (Q/DQ) nodes vào model graph → forward pass simulates INT8 arithmetic → backward pass uses FP32 gradients (Straight-Through Estimator).

```python
from pytorch_quantization import quant_modules
from pytorch_quantization import nn as quant_nn

# Enable quantization globally
quant_modules.initialize()

# Model forward pass now uses fake-quantized weights
# Train for ~10% of original schedule
for epoch in range(fine_tune_epochs):
    for batch in dataloader:
        preds = model(batch["img"])  # fake-quantized forward
        loss = criterion(preds, batch)
        loss.backward()  # FP32 gradients via STE
        optimizer.step()

# Export with Q/DQ nodes
torch.onnx.export(model, dummy_input, "model_qat.onnx",
                  opset_version=13, do_constant_folding=True)
```

**Kết quả benchmark** (SQAKD paper, AISTATS 2024):

| Model | Precision | Method | Top-1 Accuracy |
|---|---|---|---|
| ResNet-18 (FP32 baseline) | FP32 | — | 71.08% |
| ResNet-18 | INT8 (PTQ) | EWGS | 70.90% (-0.18%) |
| ResNet-18 | INT8 (QAD) | **SQAKD** | **71.40% (+0.32%)** |

→ **QAD vượt cả FP32 baseline** nhờ regularization effect từ distillation!

**Throughput speedup** (INT8 vs FP32):

| Model | FP32 FPS | INT8 FPS | Speedup |
|---|---|---|---|
| ResNet-18 | 1.87 | 5.79 | **3.10×** |
| MobileNet-V2 | 3.09 | 9.40 | **3.04×** |
| ShuffleNet-V2 | 12.64 | 36.78 | **2.91×** |

### 4.3 QAD (Quantization-Aware Distillation) — QAT + KD

```
L_QAD = L_task + λ · L_distill

L_distill = KL(softmax(z_student_quantized / T) || softmax(z_teacher_fp32 / T))
```

Từ NVIDIA QAD Report (2026):
- **Teacher = original BF16/FP32 model** (KHÔNG phải model lớn hơn)
- Student = **cùng architecture nhưng fake-quantized**
- Dùng **KL Divergence** trên output distributions
- Fine-tune ~10% of original training schedule
- **Robust to data quality** — không cần full training data

**Key finding**: Dùng teacher cùng size (original model) > dùng teacher lớn hơn:

| Teacher | Student (Quantized) | Accuracy |
|---|---|---|
| 9B BF16 (original) | 9B NVFP4 | **Better** |
| 12B BF16 (larger) | 9B NVFP4 | Worse |

→ Vì adapting to different distribution cần more data. Self-distillation hiệu quả hơn.

---

## 5. Áp dụng cho YOLOv8n → Jetson Nano

### 5.1 Pipeline đề xuất (Practical — FP16 focus)

Vì Jetson Nano **KHÔNG có INT8 hardware**, pipeline thực tế là:

```
╔════════════════════════════════════════════════════════╗
║  PHASE 1: Model Compression (trên GPU mạnh)          ║
║                                                        ║
║  Teacher: YOLOv8m (FP32, pre-trained)                 ║
║       ↓                                                ║
║  Student: YOLOv8n → FastNAS Prune (~30% params)       ║
║       ↓                                                ║
║  KD Fine-tune: MSE/CWD/MGD (Untitled15.ipynb)        ║
║       ↓                                                ║
║  Student FP32 (compressed, KD-enhanced)               ║
╠════════════════════════════════════════════════════════╣
║  PHASE 2: Export (trên GPU mạnh)                      ║
║                                                        ║
║  Export ONNX: opset=12, static shape, simplify=True   ║
║       ↓                                                ║
║  (Optional) Validate ONNX trên GPU mạnh              ║
╠════════════════════════════════════════════════════════╣
║  PHASE 3: Deploy (trên Jetson Nano)                   ║
║                                                        ║
║  Build TensorRT FP16 engine ON DEVICE:                ║
║    trtexec --onnx=model.onnx \                        ║
║            --saveEngine=model_fp16.engine \            ║
║            --fp16                                      ║
║       ↓                                                ║
║  C++ TensorRT inference: ~25-40 FPS                   ║
╚════════════════════════════════════════════════════════╝
```

### 5.2 Nếu nâng cấp lên Jetson Orin Nano (tương lai)

```
Tất cả Phase 1 giữ nguyên
    ↓
+ Thêm QAD step: Fine-tune student INT8 with FP32 teacher guidance (~5 epochs)
    ↓
Export ONNX with Q/DQ nodes → TensorRT INT8
    ↓
Expected: 2-3× faster than FP16, accuracy gần bằng FP32
```

---

## 6. FP16 vs INT8 — Khi nào cần quan tâm INT8?

### 6.1 FP16 (đủ cho Jetson Nano)

| Ưu điểm | Nhược điểm |
|---|---|
| ✅ Native support trên Maxwell GPU | ❌ Không nhanh bằng INT8 (trên GPU có DP4A) |
| ✅ Accuracy loss ~0% | |
| ✅ Không cần calibration dataset | |
| ✅ Model size giảm 50% (vs FP32) | |
| ✅ Đơn giản: `model.export(half=True)` | |

### 6.2 INT8 (chỉ dùng khi hardware support — Orin/Xavier)

| Ưu điểm | Nhược điểm |
|---|---|
| ✅ Model size giảm 75% (vs FP32) | ❌ Cần calibration dataset |
| ✅ 1.5–2× faster vs FP16 (on Orin) | ❌ 0.5–2% accuracy loss (PTQ) |
| ✅ Lower power consumption | ❌ **Không có speedup trên Nano** |

### 6.3 Decision Matrix

```
Jetson Nano (Maxwell)?
    └── YES → FP16 only. Đừng tốn thời gian cho INT8.
    
Jetson Orin / Xavier?
    ├── Accuracy quan trọng → QAD (INT8 + KD) ≈ FP32 accuracy
    ├── Speed quan trọng → PTQ INT8 (fast, ~1% accuracy loss)
    └── Balance → QAT INT8 (middle ground)
```

---

## 7. KD giúp Quantization như thế nào?

### 7.1 Vấn đề: Quantization → Accuracy Drop

```
FP32 model: mAP = 45.0%
     ↓ PTQ INT8
INT8 model: mAP = 43.5% (-1.5%)
```

### 7.2 Giải pháp: KD trước hoặc trong Quantization

**Approach A**: KD trước → Quantize sau (Pipeline hiện tại)

```
Teacher FP32 → KD → Student FP32 (mAP 44.5%) → PTQ FP16 → mAP ~44.5%
                                                  → PTQ INT8 → mAP ~43.5%
```

KD giúp student "mạnh hơn" → chịu quantization loss tốt hơn.

**Approach B**: QAD — KD TRONG quá trình quantize

```
Teacher FP32 ──┐
               │ KL Loss
Student INT8 ──┘ (fake-quantized)
               ↓
Student learns to compensate for INT8 errors
               ↓
mAP ~44.8% (gần bằng FP32!)
```

### 7.3 Kết quả thực tế — KD + Quantization cho Detection

Từ các papers đã review:

| Pipeline | mAP Δ vs Baseline | Deploy Speed |
|---|---|---|
| Baseline FP32 | 0% | 1× |
| PTQ FP16 | ~0% | **2× faster** |
| PTQ INT8 (no KD) | -1–2% | 3× faster (Orin) |
| **KD + PTQ FP16** | **+2–5%** (from KD) | **2× faster** |
| **KD + QAD INT8** | **+1–4%** (from KD, minus ~0.5% quant) | 3× faster (Orin) |
| KD + Prune + PTQ FP16 | +1–3% (net) | **3–4× faster** |

---

## 8. Tích hợp vào Untitled15.ipynb

### 8.1 Hiện tại (đã làm)

```
FastNAS Prune → KD (MSE) Fine-tune → Export ONNX → (deploy)
```

### 8.2 Thêm Quantization step

```python
# Cell mới: Export FP16 TensorRT cho Jetson Nano
from ultralytics import YOLO

model = YOLO("runs/detect/pruned_kd/weights/best.pt")

# FP16 — cho Jetson Nano
model.export(
    format="engine",
    half=True,           # FP16
    imgsz=416,           # hoặc 320 — test multiple sizes
    dynamic=False,
    simplify=True,
)
```

**Lưu ý quan trọng**: `format="engine"` cần chạy **trên device target** (Jetson Nano) vì TensorRT optimize cho GPU cụ thể. Trên GPU mạnh chỉ export ONNX, rồi dùng `trtexec` trên Nano.

### 8.3 ONNX Export (trên GPU mạnh)

```python
model.export(
    format="onnx",
    imgsz=416,          # hoặc 320
    opset=12,           # Jetson Nano JetPack 4 compatibility
    dynamic=False,      # static shape
    simplify=True,
)
```

### 8.4 TensorRT Build (trên Jetson Nano)

```bash
/usr/src/tensorrt/bin/trtexec \
    --onnx=best_pruned.onnx \
    --saveEngine=best_pruned_fp16.engine \
    --fp16 \
    --workspace=1024
```

---

## 9. So sánh tổng quan tất cả KD Methods đã nghiên cứu

| Method | Type | Effort | mAP Gain | Best For |
|---|---|---|---|---|
| **MSE on preds[1]** | Feature-based | ★☆☆ (3 days) | +1–2% | Quick baseline |
| **KL Response-based** | Response-based | ★☆☆ (3 days) | +0.5–2% | Inter-class confusion |
| **CWD** | Feature-based | ★★☆ (1 week) | +2–2.5% | Similar classes (traffic) |
| **FGD** | Feature-based | ★★★ (2 weeks) | +2–3% | Small objects |
| **MGD** | Feature-based | ★★★ (2–3 weeks) | +2–4% | Maximum accuracy |
| **LMGD (PKD)** | Feature + Response | ★★★★ (3 weeks) | +3–5% | Prune + KD combined |
| **QAD** | Response-based + Quantization | ★★★ (1 week thêm) | Recovery | INT8/FP4 deployment |

### Priority cho Jetson Nano Project

```
1. ✅ MSE KD (Done — Untitled15.ipynb)
2. → CWD (thay MSE, +1–2% mAP, 1 week)
3. → MGD hoặc LMGD (maximum accuracy, 2–3 weeks)
4. → Export ONNX → TensorRT FP16 on Nano (2–3 days)
5. → C++ inference (loại bỏ Python overhead, ~2× FPS)
```

**QAD (INT8)**: Chỉ cần thiết khi nâng cấp lên Jetson Orin/Xavier. Trên Nano, FP16 là đủ.

---

## Nguồn tham khảo

1. **NVIDIA QAD Report** (2026) — Quantization-Aware Distillation for NVFP4: https://research.nvidia.com/labs/nemotron/files/NVFP4-QAD-Report.pdf
2. **NVIDIA Blog — QAT + QAD**: https://developer.nvidia.com/blog/how-quantization-aware-training-enables-low-precision-accuracy-recovery/
3. **NVIDIA Blog — QAT with TensorRT**: https://developer.nvidia.com/blog/achieving-fp32-accuracy-for-int8-inference-using-quantization-aware-training-with-tensorrt/
4. **SQAKD** — Self-Supervised QA Knowledge Distillation (AISTATS 2024): https://proceedings.mlr.press/v238/zhao24d/zhao24d.pdf
5. **Ultralytics Export Docs**: https://docs.ultralytics.com/modes/export/
6. **Ultralytics Jetson Guide**: https://docs.ultralytics.com/guides/nvidia-jetson/
7. **Ultralytics TensorRT Blog**: https://www.ultralytics.com/blog/optimizing-ultralytics-yolo-models-with-the-tensorrt-integration
8. **Quantized Object Detection on Jetson** (IJACSA 2025): https://thesai.org/Downloads/Volume16No5/Paper_3-Quantized_Object_Detection_for_Real_Time_Inference.pdf
9. **YOLOv8 on Jetson Nano** (ReadyTensor): https://app.readytensor.ai/publications/accelerating-edge-vision-yolov8-object-detection-on-jetson-nano-4D88m4ggztQt
10. **Jetson Nano Specs** (NVIDIA): Maxwell 128-core, 0.5 TFLOPs FP16, 4GB LPDDR4
11. **YOLOv8 vs v26 on Jetson Orin** (Hackster): https://www.hackster.io/qwe018931/pushing-limits-yolov8-vs-v26-on-jetson-orin-nano-b89267
