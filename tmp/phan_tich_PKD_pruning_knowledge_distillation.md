# PKD — Pruning + Knowledge Distillation kết hợp

> Đây là **framework tổng hợp**, không phải một paper đơn lẻ.
> Kết hợp Structured Pruning + Knowledge Distillation thành một pipeline thống nhất.
>
> Paper chính tham khảo:
> - **PKD-YOLOv8** (MDPI Sensors 2025): https://www.mdpi.com/1424-8220/25/16/5004
> - **YOLOv8 Compression via Structured Pruning + CWD** (arXiv 2509.12918): https://arxiv.org/abs/2509.12918
> - **YOLOv8-DDS** (Info Processing in Agriculture 2025): Pruning + CWD trên Jetson Nano
> - **"Prune Your Model Before Distill It"** (ECCV 2022): Lý thuyết nền tảng
> - **Torch-Pruning / DepGraph** (CVPR 2023): https://github.com/VainF/Torch-Pruning

---

## 1. Tại sao kết hợp Pruning + KD?

### Vấn đề khi dùng riêng lẻ

| Kỹ thuật đơn lẻ | Hạn chế |
|---|---|
| **Pruning alone** | Cắt channels → mất accuracy 2–5%, fine-tune khó recover hết |
| **KD alone** | Student architecture cố định → không giảm được FLOPs/params vượt architecture limit |
| **Quantization alone** | INT8 → mất precision trên small objects, hardware-specific |

### Kết hợp giải quyết cả hai

```
Pruning: Giảm architecture size (channels, layers)
    ↓
KD: Recover accuracy bị mất do pruning bằng teacher guidance
    ↓
Kết quả: Smaller model + accuracy gần bằng original
```

**Key insight** (ECCV 2022 — "Prune Your Model Before Distill It"):
> Pruned teacher provides **student-friendly knowledge** that is easier to transfer.
> Pruning effectively acts as a **label smoothing regularization** making soft labels smoother.

---

## 2. Hai hướng Pipeline chính

### 2.1 Hướng A: Train → Prune → Distill (PKD-YOLOv8, YOLOv8-DDS)

```
Step 1: Train teacher (YOLOv8l/s) đầy đủ
Step 2: Train student (YOLOv8n/s) đầy đủ
Step 3: Structured pruning trên student → student_pruned
Step 4: KD từ teacher → student_pruned (recover accuracy)
Step 5: (Optional) Quantize → TensorRT deploy
```

**Ưu điểm**: Student đã có baseline tốt trước khi prune, KD chỉ cần "repair"
**Nhược điểm**: Nhiều bước, tổng training time lâu

### 2.2 Hướng B: Prune → Distill cùng lúc (Untitled15.ipynb hiện tại)

```
Step 1: Train teacher (YOLOv8m) đầy đủ
Step 2: Load student (YOLOv8n), apply FastNAS pruning
Step 3: Fine-tune student_pruned VỚI KD loss (teacher guidance) cùng lúc
Step 4: Export ONNX → TensorRT
```

**Ưu điểm**: Ít bước hơn, KD guide pruned model từ đầu
**Nhược điểm**: Pruned model yếu ban đầu → KD phải "dạy từ zero"

### 2.3 Hướng C: Distill first → Prune after (IEEE Access 2024)

```
Step 1: Train teacher đầy đủ
Step 2: KD từ teacher → student (full-size)
Step 3: Structured pruning trên distilled student
Step 4: Fine-tune pruned model
```

**IEEE Access 2024**: "distill first, then prune with structure awareness—preserves detection"
**Ưu điểm**: Student đã absorb teacher knowledge → prune mất ít hơn
**Nhược điểm**: Cần train student đầy đủ trước → tổng time dài nhất

---

## 3. PKD-YOLOv8 (MDPI Sensors 2025) — Chi tiết

### 3.1 Overview

| Item | Detail |
|---|---|
| **Base model** | YOLOv8s |
| **Teacher** | YOLOv8s (original, unpruned) |
| **Student** | YOLOv8s (after pruning) |
| **Pruning method** | Structured pruning based on BN γ coefficients |
| **KD method** | **LMGD** = Logit Distillation + Modified MGD |
| **Dataset** | ACEFP (rapeseed pests, custom) |
| **Target** | Jetson Nano edge deployment |

### 3.2 LMGD — Logit + MGD Distillation Strategy

LMGD kết hợp **hai loại KD cùng lúc**:

```
L_total = L_task + α · L_MGD + β · L_logit
```

- **L_task**: Detection loss gốc (box + cls + dfl)
- **L_MGD**: Masked Generative Distillation trên **feature maps** (FPN outputs)
  - Random mask student features → generator reconstruct teacher features
  - MSE loss giữa generated và actual teacher features
- **L_logit**: KL Divergence trên **detection head outputs** (logits)
  - Soft labels từ teacher với temperature scaling
  - Match probability distributions

**Tại sao kết hợp cả hai?**
- MGD (feature-based): Học **representations** — spatial patterns, object boundaries
- Logit (response-based): Học **inter-class relationships** — "car giống truck hơn person"
- Hai loại knowledge bổ sung cho nhau

### 3.3 Structured Pruning — BN γ Analysis

PKD-YOLOv8 dùng **pruning sensitivity analysis** dựa trên BN (BatchNorm) γ coefficients:

1. **Phân tích**: Scan tất cả BN layers, đo γ (scale factor) → γ nhỏ = channel ít quan trọng
2. **Layer-wise sensitivity**: Không prune uniform — mỗi layer có pruning ratio khác nhau
3. **Iterative pruning**: Prune dần (10% mỗi round), fine-tune, đo mAP, lặp lại

### 3.4 Kết quả

| Metric | Original YOLOv8s | PKD-YOLOv8 | Δ |
|---|---|---|---|
| **mAP@0.5** | 96.8% | 96.7% | **-0.1%** |
| **Accuracy** | — | 93.2% | — |
| **Recall** | — | 92.7% | — |
| **Parameters** | 11.2 MB | **4.4 MB** | **-60.7%** |
| **FLOPs** | 28.3 G | **10.01 G** | **-64.6%** |
| **Jetson Nano FPS** | — | **11.76 FPS** | Real-time |

**Highlight**: Giảm >60% parameters + FLOPs, mAP chỉ giảm 0.1%. Đây là kết quả tốt nhất trong các papers reviewed.

---

## 4. YOLOv8 Compression Framework (arXiv 2509.12918) — Chi tiết

### 4.1 3-Stage Pipeline

```
Stage 1: Sparsity-Aware Training (L1 regularization)
    → Dynamic sparsity during training → identify unimportant channels
    
Stage 2: Layer-Wise Structured Channel Pruning
    → Per-layer BN scaling factors → remove channels individually per layer
    → NOT global threshold — fine-grained per-layer decision
    
Stage 3: Channel-Wise Knowledge Distillation (CWD)
    → Original model (pre-pruned) = Teacher
    → Pruned model = Student
    → CWD trên C2f layers của YOLOv8
```

### 4.2 CWD trong pipeline này

Dùng CWD chuẩn (đã phân tích trong doc trước):

$$\varphi(y^c)_i = \frac{\exp(y^c_i / \tau)}{\sum_{j=1}^{H \cdot W} \exp(y^c_j / \tau)}$$

$$L_{CWD} = \frac{1}{C} \sum_{c=1}^{C} D_{KL}(\varphi(y^c_T) \| \varphi(y^c_S))$$

- $\tau$: Temperature (adjustable)
- Distill trên **C2f layers** (intermediate features) — không chỉ FPN outputs

### 4.3 Kết quả (VisDrone — Aerial Detection)

| Model | Params | FLOPs | MACs | AP50 | FPS |
|---|---|---|---|---|---|
| YOLOv8m (baseline) | 25.85M | 49.6G | 101G | 50.6 | 26 |
| **Pruned + CWD** | **6.85M** | **13.3G** | **34.5G** | **47.9** | **45** |
| + TensorRT | 6.85M | — | — | 47.6 | **68** |

- **Parameters giảm 73.5%**
- **AP50 giảm 2.7%** (50.6 → 47.9)
- **FPS tăng 2.6×** (26 → 68 với TensorRT)

### 4.4 Điểm quan trọng cho project

- Sparsity-aware training **trước** pruning → pruning hiệu quả hơn
- **Layer-wise** (không global) pruning → sensitive layers giữ nguyên
- CWD recover accuracy tốt nhất so với fine-tune alone
- TensorRT thêm +23 FPS gần như miễn phí (chỉ -0.3% AP50)

---

## 5. YOLOv8-DDS (Info Processing in Agriculture 2025) — Jetson Nano Focus

### 5.1 Pipeline

```
Magnitude Pruning (layer-wise adaptive) → CWD → TensorRT trên Jetson Nano
```

### 5.2 Kết quả

| Metric | Baseline YOLOv8n | YOLOv8n-DDS | Δ |
|---|---|---|---|
| Precision | — | +2.4% | ↑ |
| Recall | — | +5.6% | ↑ |
| mAP50 | — | +2.2% | ↑ |
| Parameters | — | **-23.8%** | ↓ |
| GFLOPs | — | **-14.8%** | ↓ |
| Jetson Nano latency | — | **-25.8%** (with TRT) | ↓ |

**Đặc biệt**: mAP **tăng** sau pruning + CWD (không giảm!) vì CWD transfer knowledge hiệu quả từ teacher.

---

## 6. Torch-Pruning / DepGraph (CVPR 2023)

### 6.1 Tại sao cần Torch-Pruning?

PyTorch built-in `torch.nn.utils.prune`:
- Chỉ **zero-out weights** (mask), không thực sự remove channels
- Không giảm inference time thực tế
- Không handle dependencies giữa layers

**Torch-Pruning** (DepGraph):
- **Physically removes** channels/neurons
- Automatically traces dependencies (Conv → BN → ReLU → next Conv)
- Produces a **truly smaller model** → real speedup
- YOLOv8 example có sẵn: `examples/yolov8/yolov8_pruning.py`

### 6.2 YOLOv8m Pruning Results (Torch-Pruning official)

| Pruning Ratio | MACs | Params | Latency |
|---|---|---|---|
| 0.00 (baseline) | 4.12 G | 25.56 M | 45.22 ms |
| 0.30 | 2.02 G | 12.46 M | 33.38 ms |
| 0.50 | 1.07 G | 6.41 M | 20.68 ms |
| 0.65 | 0.53 G | 3.10 M | 15.19 ms |
| 0.75 | 0.29 G | 1.61 M | 10.07 ms |

→ Pruning 50%: **75% MACs reduction**, **75% params reduction**, **54% faster**

### 6.3 Code Example (YOLOv8)

```python
import torch
import torch_pruning as tp
from ultralytics import YOLO

model = YOLO("yolov8n.pt")
example_inputs = torch.randn(1, 3, 640, 640).to(model.device)

# DepGraph-based structured pruning
pruner = tp.pruner.MetaPruner(
    model.model,
    example_inputs,
    importance=tp.importance.MagnitudeImportance(p=2),  # L2 norm
    pruning_ratio=0.5,  # remove 50% channels
    root_module_types=[torch.nn.Conv2d],
)

# Iterative pruning
for i in range(iterative_steps):
    pruner.step()
    # Fine-tune or KD after each step
```

---

## 7. So sánh các Pipeline Prune + KD

| Paper/Method | Pruning | KD | Base Model | Params Δ | mAP Δ | Deploy |
|---|---|---|---|---|---|---|
| **PKD-YOLOv8** | BN γ structured | **LMGD** (Logit+MGD) | YOLOv8s | **-60.7%** | **-0.1%** | Jetson Nano 11.76 FPS |
| **arXiv 2509.12918** | L1 sparse + layer-wise | CWD | YOLOv8m | **-73.5%** | -2.7% | 68 FPS (TRT) |
| **YOLOv8-DDS** | Magnitude adaptive | CWD | YOLOv8n | -23.8% | **+2.2%** | Jetson Nano -25.8% latency |
| **Untitled15.ipynb** | FastNAS (ModelOpt) | MSE on preds[1] | YOLOv8n | ~-30% | TBD | Target: Jetson Nano |
| **YOLOX-nano** | BN iterative | None (fine-tune) | YOLOX-nano | -50% backbone | ~stable | Edge |

---

## 8. LMGD vs Các KD Method Khác (trong context Prune + KD)

| KD Method | Trong Prune+KD Pipeline | Ưu điểm | Nhược điểm |
|---|---|---|---|
| **Fine-tune only** | Baseline | Đơn giản nhất | Recovery kém (-2-5% mAP) |
| **MSE on features** | Untitled15.ipynb | Implement nhanh (~3 ngày) | Chỉ match features, không match logits |
| **CWD** | arXiv 2509.12918, YOLOv8-DDS | Stable, tốt cho similar classes | Không capture inter-class relationships |
| **MGD** | — | Stronger representations | Thêm generator, +20% training time |
| **LMGD (Logit+MGD)** | PKD-YOLOv8 | **Best of both worlds** | Phức tạp nhất, 3 loss terms |
| **KL Response** | — | Inter-class relationships | Yếu trên spatial features |

---

## 9. Áp dụng cho Project hiện tại (YOLOv8n → Jetson Nano)

### 9.1 Pipeline đề xuất (progressive upgrade)

```
=== LEVEL 0 (DONE — Untitled15.ipynb) ===
FastNAS prune → Fine-tune with MSE KD from YOLOv8m teacher
Expected: ~30% params reduction, ~1-2% mAP recovery from KD

=== LEVEL 1 (~1 tuần — thay MSE bằng CWD) ===  
FastNAS prune → Fine-tune with CWD from YOLOv8m teacher
Expected: thêm +1-2% mAP recovery (based on YOLOv8-DDS results)

=== LEVEL 2 (~2 tuần — thay CWD bằng MGD) ===
FastNAS prune → Fine-tune with MGD from YOLOv8m teacher
Expected: thêm +0.3-0.5% mAP recovery

=== LEVEL 3 (~3 tuần — full LMGD) ===
FastNAS prune → Fine-tune with LMGD (Logit + MGD) from YOLOv8m teacher
Expected: maximum recovery, ~0.1% mAP loss from original (per PKD-YOLOv8)

=== FINAL ===
Export ONNX → TensorRT trên Jetson Nano → benchmark FPS
```

### 9.2 LMGD Implementation Sketch

```python
def loss(self, batch, preds=None):
    if preds is None:
        preds = self.model(batch["img"])

    # Task loss (box + cls + dfl)
    student_loss, loss_items = super().loss(batch, preds)

    with torch.no_grad():
        t_preds = self._teacher(batch["img"])

    s_feats = preds[1] if isinstance(preds, tuple) else preds
    t_feats = t_preds[1] if isinstance(t_preds, tuple) else t_preds

    # --- MGD Loss (feature-based) ---
    mgd_loss_val = torch.tensor(0.0, device=self.device)
    for gen, s_feat, t_feat in zip(self._generators, s_feats, t_feats):
        if s_feat.shape[-2:] != t_feat.shape[-2:]:
            s_feat = F.interpolate(s_feat, size=t_feat.shape[-2:],
                                   mode="bilinear", align_corners=False)
        B, C, H, W = s_feat.shape
        mask = (torch.rand(B, 1, H, W, device=s_feat.device) > 0.65).float()
        generated = gen(s_feat * mask)
        mgd_loss_val = mgd_loss_val + F.mse_loss(generated, t_feat)

    # --- Logit Distillation (response-based) ---
    # preds[0] = decoded predictions, t_preds[0] = teacher decoded
    s_logits = preds[0] if isinstance(preds, tuple) else preds
    t_logits = t_preds[0] if isinstance(t_preds, tuple) else t_preds
    T = 3.0  # temperature
    logit_loss = F.kl_div(
        F.log_softmax(s_logits / T, dim=-1),
        F.softmax(t_logits / T, dim=-1),
        reduction="batchmean",
    ) * (T * T)

    # --- Combined Loss ---
    alpha_mgd = 2e-5  # MGD weight (paper default for one-stage)
    alpha_logit = 0.5  # Logit weight
    total_loss = student_loss + alpha_mgd * mgd_loss_val + alpha_logit * logit_loss

    return total_loss, loss_items
```

**Lưu ý**: Sketch trên chỉ mang tính minh họa. Logit distillation cho YOLOv8 detection cần xử lý riêng classification logits và regression logits (DFL), không áp KL trực tiếp lên decoded predictions.

### 9.3 Thứ tự ưu tiên

Dựa trên tất cả evidence:

| Priority | Action | Effort | Expected Gain |
|---|---|---|---|
| **1** | Thay MSE → CWD trong Untitled15.ipynb | 3–5 ngày | +1–2% mAP |
| **2** | Thêm BN-based pruning sensitivity analysis | 3 ngày | Prune hiệu quả hơn |
| **3** | Upgrade CWD → MGD | 1–2 tuần | +0.3–0.5% mAP |
| **4** | Thêm Logit Distillation → LMGD | 1 tuần | +0.2–0.5% mAP |
| **5** | Quantization (INT8/FP16) + TensorRT | 2–3 ngày | 2–3× FPS |

---

## 10. Thứ tự Prune vs Distill — Evidence Summary

| Thứ tự | Cơ sở | Khi nào dùng |
|---|---|---|
| **Prune → Distill** | PKD-YOLOv8, arXiv 2509.12918, NVIDIA NeMo | **Khuyến nghị cho production** — prune tạo student nhỏ, KD recover |
| **Distill → Prune** | IEEE Access 2024 | Student đã absorb knowledge → prune an toàn hơn, nhưng tốn thời gian hơn |
| **Prune + Distill cùng lúc** | Untitled15.ipynb (hiện tại) | Nhanh nhất, nhưng pruned model ban đầu yếu |
| **Prune Teacher → Distill** | ECCV 2022 "Prune Before Distill" | Pruned teacher = softer labels → student học dễ hơn (unstructured pruning on teacher) |

**Consensus**: **Prune → Distill** là approach phổ biến nhất và stable nhất cho YOLO + edge deployment.

---

## Nguồn tham khảo

1. **PKD-YOLOv8** — Collaborative Pruning and KD (MDPI Sensors 2025): https://www.mdpi.com/1424-8220/25/16/5004 | https://pubmed.ncbi.nlm.nih.gov/40871867/
2. **Structured Pruning + CWD for YOLOv8** (arXiv 2509.12918): https://arxiv.org/abs/2509.12918
3. **YOLOv8-DDS** — Pruning + CWD trên Jetson Nano (Info Processing in Agriculture 2025)
4. **"Prune Your Model Before Distill It"** (ECCV 2022): https://www.ecva.net/papers/eccv_2022/papers_ECCV/papers/136710120.pdf
5. **Torch-Pruning / DepGraph** (CVPR 2023): https://github.com/VainF/Torch-Pruning
6. **NVIDIA TensorRT Model Optimizer** — Pruning + Distillation pipeline: https://developer.nvidia.com/blog/pruning-and-distilling-llms-using-nvidia-tensorrt-model-optimizer/
7. **NVIDIA NeMo** — Prune + Distill Llama tutorial: https://developer.nvidia.com/blog/llm-model-pruning-and-knowledge-distillation-with-nvidia-nemo-framework/
8. **Lightweight YOLOX with Structural Pruning** (CEUR-WS 2024): https://ceur-ws.org/Vol-4082/paper12.pdf
9. **KefanZhan/YOLOv8-KD** — Multi-method KD for YOLOv8: https://github.com/KefanZhan/YOLOv8-KD
10. **Ultralytics Issue #3507** — How to prune YOLOv8: https://github.com/ultralytics/ultralytics/issues/3507
