# MGD — Masked Generative Distillation

> Paper: **"Masked Generative Distillation"** (ECCV 2022)
> Authors: Zhendong Yang, Zhe Li, Mingqi Shao, Dachuan Shi, Zehuan Yuan, Chun Yuan
> (Cùng nhóm tác giả với FGD — Tsinghua/ByteDance)
> arXiv: https://arxiv.org/abs/2205.01529
> Code (official): https://github.com/yzd-v/MGD (MMDetection/MMRazor based)
>
> Paper ứng dụng: **"LKD-YOLOv8: A Lightweight Knowledge Distillation-Based Method for Infrared Object Detection"** (MDPI Sensors, 2025)
> URL: https://www.mdpi.com/1424-8220/25/13/4054
> PubMed: https://pubmed.ncbi.nlm.nih.gov/40648312/

---

## 1. Ý tưởng cốt lõi

### Khác biệt với KD truyền thống

Các phương pháp KD trước đó (MSE, CWD, FGD) đều **bắt chước (mimic)** teacher features trực tiếp. MGD đảo ngược tiếp cận:

> **Không bắt chước — mà TÁI TẠO (generate).**

MGD **random mask** một phần features của student, rồi buộc student **tái tạo lại toàn bộ features** của teacher từ phần còn lại. Giống cách Masked Autoencoders (MAE) hoạt động, nhưng áp dụng cho distillation.

### Intuition

- **Mimic** (CWD/FGD): "Copy bài thầy"
- **Generate** (MGD): "Bị che mất 65% bài, phải tự suy ra toàn bộ bài thầy từ 35% còn lại"

→ Student buộc phải xây dựng **representation power mạnh hơn** vì không thể copy trực tiếp.

---

## 2. Kiến trúc & Thuật toán

### 2.1 Pipeline (Algorithm 1 trong paper)

```
Input: Teacher T, Student S, image x, label y

1. Forward student: fea_S, ŷ = S(x)
2. Forward teacher (frozen): fea_T = T(x)
3. Random binary mask M: mask λ% pixels of fea_S
4. Masked student feature: fea_S_masked = fea_S ⊙ M
5. Generate teacher feature: fea_gen = Generator(fea_S_masked)
6. Distillation loss: L_dis = MSE(fea_gen, fea_T)
7. Total loss: L = L_original(ŷ, y) + α · L_dis
8. Update student + generator (teacher frozen)
```

### 2.2 Generator Block

Generator cực kỳ đơn giản — chỉ gồm:

```python
Generator = nn.Sequential(
    nn.Conv2d(C_student, C_teacher, 1),  # 1×1 conv (channel align)
    nn.ReLU(inplace=True),
    nn.Conv2d(C_teacher, C_teacher, 3, padding=1),  # 3×3 conv (spatial reconstruct)
)
```

- 1×1 conv: Align channel dimension (student → teacher)
- ReLU: Non-linear activation
- 3×3 conv: Reconstruct spatial features bị mask

**Rất nhẹ** — chỉ ~O(C²) parameters, negligible so với model chính.

### 2.3 Masking Mechanism

Binary mask $M$ tạo từ random uniform:

$$M_{i,j} = \begin{cases} 0 & \text{with probability } \lambda \\ 1 & \text{with probability } 1 - \lambda \end{cases}$$

- $\lambda = 0.65$: mask 65% pixels (paper gốc, detection)
- $\lambda = 0.50$: mask 50% pixels (classification)
- Mask **khác nhau mỗi batch** → data augmentation effect

### 2.4 Distillation Loss

$$L_{dis} = \frac{\alpha}{H \times W} \sum_{i=1}^{H} \sum_{j=1}^{W} \left\| \text{Gen}(f^S \odot M)_{i,j} - f^T_{i,j} \right\|_2^2$$

- $f^S$: student feature map
- $f^T$: teacher feature map
- $M$: random binary mask
- $\text{Gen}(\cdot)$: generator block
- $\alpha$: loss weight hyperparameter

---

## 3. Hyper-parameters

### 3.1 Từ paper gốc (ECCV 2022)

| Task | α (loss weight) | λ (mask ratio) |
|---|---|---|
| Image Classification | 7 × 10⁻⁵ | 0.50 |
| **One-stage Detection** | **2 × 10⁻⁵** | **0.65** |
| Two-stage Detection | 5 × 10⁻⁷ | 0.45 |
| Semantic Segmentation | 1 × 10⁻² | 0.75 |
| Instance Segmentation | 5 × 10⁻⁶ | 0.65 |

**YOLO = one-stage** → dùng α = 2×10⁻⁵, λ = 0.65.

### 3.2 Feature map selection

- **Classification**: Distill trên **last feature map** từ backbone
- **Detection**: Distill trên **tất cả feature maps từ neck** (FPN outputs — P3, P4, P5)
- **Segmentation**: Distill trên **tất cả FPN outputs**

---

## 4. Benchmark — COCO Object Detection

### 4.1 One-stage (RetinaNet ResNeXt101 → ResNet50)

| Method | mAP | AP_S | AP_M | AP_L |
|---|---|---|---|---|
| Baseline student | 37.4 | 20.6 | 40.7 | 49.7 |
| FKD | 39.6 | 22.7 | 43.3 | 52.5 |
| CWD | 40.8 | 22.7 | 44.5 | 55.3 |
| FGD | 40.7 | 22.9 | 45.0 | 54.7 |
| **MGD** | **41.0** | **23.4** | **45.3** | **55.7** |

→ **MGD vượt FGD 0.3%, CWD 0.2%** trên RetinaNet.

### 4.2 Two-stage (Cascade Mask RCNN ResNeXt101 → Faster RCNN ResNet50)

| Method | mAP | AP_S | AP_M | AP_L |
|---|---|---|---|---|
| Baseline | 38.4 | 21.5 | 42.1 | 50.3 |
| CWD | 41.7 | 23.3 | 45.5 | 55.5 |
| FGD | 42.0 | 23.8 | 46.4 | 55.5 |
| **MGD** | **42.1** | 23.7 | 46.4 | **56.1** |

### 4.3 Anchor-free (RepPoints ResNeXt101 → ResNet50)

| Method | mAP | AP_S |
|---|---|---|
| Baseline | 38.6 | 22.5 |
| FGD | 42.0 | 24.0 |
| **MGD** | **42.3** | **24.4** |

### 4.4 Classification (ImageNet)

| Teacher → Student | Baseline | +MGD |
|---|---|---|
| ResNet34 → ResNet18 | 69.90 | **71.69** (+1.79) |
| ResNet50 → MobileNet | 68.87 | **72.03** (+3.16) |

### 4.5 Segmentation (Cityscapes)

| Teacher → Student | Baseline mIoU | +MGD mIoU |
|---|---|---|
| PSPNet R101 → PSPNet R18 | 69.85 | **73.63** (+3.78) |
| PSPNet R101 → DeepLabV3 R18 | 73.20 | **76.02** (+2.82) |

---

## 5. LKD-YOLOv8 (MDPI Sensors, 2025)

### 5.1 Paper Summary

**"LKD-YOLOv8: A Lightweight Knowledge Distillation-Based Method for Infrared Object Detection"**

- **Nhiệm vụ**: Infrared object detection trên edge devices
- **Teacher**: YOLOv8s (standard)
- **Student**: YOLOv8n (modified = LKD-YOLOv8)
- **KD method**: MGD (Masked Generative Distillation)
- **Cải tiến thêm**:
  - **LDConv** (Linear Deformable Convolution): Spatial feature extraction mạnh hơn
  - **Coordinate Attention (CA)**: Channel-wise + spatial interaction → feature alignment tốt hơn

### 5.2 Kết quả

| Model | mAP50 | mAP50-95 | Parameters |
|---|---|---|---|
| YOLOv8n (baseline) | — | baseline | 3.15M |
| LKD-YOLOv8 (MGD + LDConv + CA) | — | **+1.18%** | **2.90M (-7.9%)** |
| + Coordinate Attention (CA) riêng | — | **+2.16%** | — |

### 5.3 Điểm quan trọng

- MGD hoạt động tốt khi **kết hợp với attention mechanisms** (CA)
- Giảm parameters 7.9% nhờ lightweight convolution (LDConv) mà vẫn tăng accuracy
- Phù hợp cho **edge devices** (infrared → tương tự traffic detection trên Jetson)

---

## 6. Benchmark mới nhất: CWD vs MGD (ICCV 2025 Workshop)

Từ paper "Improving Lightweight Weed Detection via Knowledge Distillation" (Saltık et al., YOLO11x → YOLO11n):

| Method | Best Config | mAP50 | Δ vs Baseline |
|---|---|---|---|
| Baseline YOLO11n | — | 0.834 | — |
| **CWD** | τ = 2.0 | **0.859** | **+2.5%** |
| MGD | α = 2×10⁻⁵ | 0.853 | +1.9% |
| Teacher YOLO11x | — | 0.895 | — |

**Lưu ý**: CWD thắng MGD 0.6% trong benchmark này. Tuy nhiên:
- Dataset nhỏ (weed, 5 classes) — MGD mạnh hơn ở datasets lớn
- MGD alpha sweep chỉ test 4 giá trị — có thể chưa tối ưu
- COCO benchmark: MGD > CWD nhất quán

---

## 7. So sánh tổng quan: MGD vs CWD vs FGD vs MSE

| Tiêu chí | MSE (Untitled15) | CWD | FGD | **MGD** |
|---|---|---|---|---|
| **Paper** | Classic | ICCV 2021 | CVPR 2022 | **ECCV 2022** |
| **Cơ chế** | Trực tiếp match features | Channel-wise KL | Focal + Global | **Mask + Generate** |
| **Generator module** | Không | Không | Không | **Có (2 conv layers)** |
| **Training overhead** | Nhẹ nhất | Nhẹ | Trung bình | **+15–20% training time** |
| **Inference overhead** | 0 | 0 | 0 | **0** (generator không dùng khi inference) |
| **COCO RetinaNet R50** | ~38–39 | 40.8 | 40.7 | **41.0** |
| **COCO AP_S** | ~21 | 22.7 | 22.9 | **23.4** |
| **Implement complexity** | ✅ Trivial | 1 tuần | 2 tuần | **2–3 tuần** |
| **Hyper-params** | α only | α, τ | α, β, γ, λ | **α, λ (mask ratio)** |
| **Best for** | Quick baseline | Stable, similar classes | Small objects | **Maximum accuracy** |

---

## 8. Implementation cho YOLOv8

### 8.1 Generator Module (PyTorch)

```python
import torch
import torch.nn as nn

class MGDGenerator(nn.Module):
    """Simple generator for MGD: align channels + reconstruct masked features."""

    def __init__(self, student_channels: int, teacher_channels: int):
        super().__init__()
        self.align = nn.Conv2d(student_channels, teacher_channels, 1)
        self.relu = nn.ReLU(inplace=True)
        self.generate = nn.Conv2d(teacher_channels, teacher_channels, 3, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.generate(self.relu(self.align(x)))
```

### 8.2 MGD Loss Function

```python
def mgd_loss(
    student_feat: torch.Tensor,
    teacher_feat: torch.Tensor,
    generator: nn.Module,
    mask_ratio: float,
) -> torch.Tensor:
    """Masked Generative Distillation loss (Yang et al., ECCV 2022)."""
    B, C, H, W = student_feat.shape

    # Random binary mask: 0 = masked, 1 = visible
    mask = (torch.rand(B, 1, H, W, device=student_feat.device) > mask_ratio).float()

    # Mask student features
    masked_feat = student_feat * mask

    # Generate teacher features from masked student
    generated = generator(masked_feat)

    # MSE between generated and actual teacher features
    loss = torch.nn.functional.mse_loss(generated, teacher_feat)

    return loss
```

### 8.3 Tích hợp vào PrunedTrainer

```python
class PrunedTrainerMGD(PrunedTrainer):
    """Extends PrunedTrainer with MGD instead of vanilla MSE."""

    def _setup_train(self):
        super()._setup_train()

        # Create generators for each FPN level (P3, P4, P5)
        # Channel dims depend on Detect head output
        detect_channels = self.model.model[-1].no  # reg_max*4 + nc
        self._generators = nn.ModuleList([
            MGDGenerator(detect_channels, detect_channels)
            for _ in range(3)  # 3 FPN levels
        ]).to(self.device)

        # Add generator params to optimizer
        self.optimizer.add_param_group({
            "params": self._generators.parameters(),
            "lr": self.args.lr0,
        })

    def loss(self, batch, preds=None):
        if preds is None:
            preds = self.model(batch["img"])

        student_loss, loss_items = super(PrunedTrainer, self).loss(batch, preds)

        with torch.no_grad():
            t_preds = self._teacher(batch["img"])

        s_feats = preds[1] if isinstance(preds, tuple) else preds
        t_feats = t_preds[1] if isinstance(t_preds, tuple) else t_preds

        kd_loss = torch.tensor(0.0, device=self.device)
        for gen, s_feat, t_feat in zip(self._generators, s_feats, t_feats):
            if s_feat.shape[-2:] != t_feat.shape[-2:]:
                s_feat = F.interpolate(s_feat, size=t_feat.shape[-2:],
                                       mode="bilinear", align_corners=False)
            kd_loss = kd_loss + mgd_loss(s_feat, t_feat, gen, mask_ratio=0.65)

        alpha = 2e-5  # paper default for one-stage
        total_loss = student_loss + alpha * kd_loss

        return total_loss, loss_items
```

**Lưu ý quan trọng**: MGD loss dùng **additive weighting** (không convex combination) vì α rất nhỏ (~10⁻⁵). Gradient scale đã được kiểm soát bởi giá trị α nhỏ.

---

## 9. Repos & Tools

| Repo | Mô tả | Status |
|---|---|---|
| [yzd-v/MGD](https://github.com/yzd-v/MGD) | Official implementation (cls/det/seg) | ✅ Reference |
| [open-mmlab/mmrazor](https://github.com/open-mmlab/mmrazor) | MGD integrated, `configs/distill/mmdet/` | ✅ Production |
| [huangzongmou/yolov8_Distillation](https://github.com/huangzongmou/yolov8_Distillation) | CWD + MGD cho YOLOv8 | ⚠️ Cũ |
| [KefanZhan/YOLOv8-KD](https://github.com/KefanZhan/YOLOv8-KD) | Multi-method KD cho YOLOv8 (2025) | ✅ Newer |
| Ultralytics Community | MGD implementation discussion | 📌 Thread có sẵn |

---

## 10. Đánh giá cho project YOLOv8n → Jetson Nano

| Tiêu chí | Đánh giá |
|---|---|
| **Khả thi?** | Có, 2–3 tuần implement |
| **mAP gain dự kiến** | +2–4% (detection COCO benchmark) |
| **So với MSE (hiện tại)** | +1–2% improvement thêm |
| **So với CWD** | +0.2–0.5% improvement thêm (COCO) |
| **Training overhead** | +15–20% (thêm generator forward + mask) |
| **Inference impact** | **0** — generator chỉ dùng khi training |
| **GPU memory thêm** | ~5–10% (generator nhỏ, nhưng cần lưu masked features) |
| **Risk** | Trung bình — cần tune α và λ, training longer |
| **Kết hợp với pruning?** | Có — MGD tương thích với FastNAS pruning pipeline |

### Khi nào dùng MGD?

1. **Muốn maximum accuracy** và có thời gian implement (2–3 tuần)
2. **Teacher-student capacity gap lớn** (YOLOv8m → YOLOv8n pruned) — MGD mạnh nhất ở gap lớn
3. **Kết hợp với attention** (LKD-YOLOv8 chứng minh CA + MGD = +2.16%)

### Khi nào KHÔNG dùng MGD?

1. **Thời gian hạn chế** — CWD đơn giản hơn, kết quả gần tương đương
2. **Dataset nhỏ** (< 5000 images) — MGD cần data đủ lớn để generator học tốt
3. **Debugging khó** — thêm generator module = thêm điểm có thể fail

---

## 11. Workflow đề xuất (progressive)

Dựa trên tất cả các phương pháp đã phân tích:

```
Level 0 (Done):  MSE on preds[1]         → Untitled15.ipynb (baseline KD)
Level 1 (~3 days): CWD thay MSE          → +1-2% mAP, stable
Level 2 (~2 weeks): MGD thay CWD         → +0.5% thêm, maximum accuracy
Level 3 (optional): MGD + CWD hybrid     → thử nghiệm cả hai cùng lúc
Level 4 (optional): MGD + CA attention   → theo LKD-YOLOv8 pattern (+2.16%)
```

**Khuyến nghị cho project hiện tại**: Bắt đầu từ **Level 1 (CWD)** — effort thấp, gain tốt. Chỉ lên Level 2 (MGD) nếu CWD chưa đủ target mAP.

---

## Nguồn tham khảo

1. Yang et al., "Masked Generative Distillation" (ECCV 2022) — https://arxiv.org/abs/2205.01529
2. Official MGD code — https://github.com/yzd-v/MGD
3. LKD-YOLOv8 (MDPI Sensors 2025) — https://www.mdpi.com/1424-8220/25/13/4054
4. Saltık et al., "Improving Lightweight Weed Detection via KD" (ICCV 2025 Workshop) — CWD vs MGD benchmark
5. AMGD: Anchor-Based Masked Generative Distillation (BMVC 2024) — https://bmva-archive.org.uk/bmvc/2024/papers/Paper_365/paper.pdf
6. OpenMMLab mmrazor — https://github.com/open-mmlab/mmrazor
7. KefanZhan/YOLOv8-KD — https://github.com/KefanZhan/YOLOv8-KD
8. Ultralytics Community MGD discussion — https://community.ultralytics.com/t/implementing-knowledge-distillation-with-yolo11n-student-and-yolo11m-teacher-in-ultralytics-trainer/1743
9. PMC Survey "KD in Object Detection" — https://pmc.ncbi.nlm.nih.gov/articles/PMC12788226/
