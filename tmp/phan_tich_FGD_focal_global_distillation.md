# FGD — Focal and Global Knowledge Distillation for Detectors

> Paper: **"Focal and Global Knowledge Distillation for Detectors"** (CVPR 2022)
> Authors: Zhendong Yang, Zhe Li, Xiaohu Jiang, Yuan Gong, Zehuan Yuan, Danpei Zhao, Chun Yuan
> Affiliations: Tsinghua Shenzhen International Graduate School & ByteDance Inc
> arXiv: https://arxiv.org/abs/2111.11837
> Code (official): https://github.com/yzd-v/FGD (based on MMDetection)
> Framework: https://github.com/open-mmlab/mmrazor (OpenMMLab Model Compression Toolbox)

---

## 1. Vấn đề FGD giải quyết

Các phương pháp KD trước đó (FitNet, vanilla feature mimicking) **đối xử đồng đều** tất cả pixel trên feature map khi distill. Trong object detection, điều này gây ra 2 vấn đề:

1. **Foreground/Background imbalance**: Background chiếm ~90% diện tích feature map, lấn át tín hiệu từ foreground (object).
2. **Missing global context**: Nếu chỉ focus cục bộ (focal) thì mất thông tin quan hệ giữa các vùng khác nhau trên ảnh.

FGD kết hợp **2 nhánh distillation** để giải quyết cả hai:

```
FGD Loss = L_focal + L_global + L_attention
```

---

## 2. Focal Distillation — Chi tiết

### 2.1 Foreground/Background Separation

Sử dụng binary mask $M$ dựa trên ground-truth bounding boxes:

$$M_{i,j} = \begin{cases} 1 & \text{if } (i,j) \in \text{bounding box region} \\ 0 & \text{otherwise} \end{cases}$$

### 2.2 Spatial Attention $A^S$

Tính từ feature map $F$ của Teacher bằng cách tổng hợp qua channels:

$$A^S_{i,j} = \frac{H \cdot W \cdot \exp\left(\frac{\sum_k |F_{k,i,j}|}{T}\right)}{\sum_{i'}\sum_{j'}\exp\left(\frac{\sum_k |F_{k,i',j'}|}{T}\right)}$$

với $T = 0.5$ (temperature cho attention distribution).

### 2.3 Channel Attention $A^C$

Tính bằng cách tổng hợp qua spatial dimensions:

$$A^C_k = \frac{C \cdot \exp\left(\frac{\sum_i\sum_j |F_{k,i,j}|}{T}\right)}{\sum_{k'}\exp\left(\frac{\sum_i\sum_j |F_{k',i,j}|}{T}\right)}$$

### 2.4 Focal Feature Loss (Eq. 9 trong paper)

$$L_{fea} = \alpha \sum_k \sum_i \sum_j M_{i,j} \cdot S_{i,j} \cdot A^S_{i,j} \cdot A^C_k \cdot \left(F^T_{k,i,j} - f(F^S_{k,i,j})\right)^2$$
$$\quad + \beta \sum_k \sum_i \sum_j (1-M_{i,j}) \cdot S_{i,j} \cdot A^S_{i,j} \cdot A^C_k \cdot \left(F^T_{k,i,j} - f(F^S_{k,i,j})\right)^2$$

Trong đó:
- $\alpha$: trọng số cho **foreground** (vùng có object)
- $\beta$: trọng số cho **background** (thường $\beta < \alpha$ vì background noise ít quan trọng hơn)
- $f(\cdot)$: adaptation layer (1×1 conv) để căn chỉnh channel dimension nếu Teacher/Student khác architecture
- $S_{i,j}$: scale factor dựa trên kích thước object (object lớn → trọng số nhỏ hơn, small object → trọng số lớn hơn)

**Điểm mấu chốt**: Nhân $M_{i,j}$ vào loss buộc student tập trung pixel thuộc object. Nhân $A^S \cdot A^C$ buộc student tập trung vào pixels/channels mà teacher cho là quan trọng nhất.

---

## 3. Global Distillation — Chi tiết

### 3.1 GcBlock (Global Context)

Xây dựng ma trận quan hệ (relation matrix) giữa tất cả pixel-pairs trên feature map, rồi transfer quan hệ đó từ Teacher sang Student.

### 3.2 Global Loss (Eq. 12 trong paper)

$$L_{global} = \lambda \cdot ||G(F^T) - G(f(F^S))||_2^2$$

Trong đó $G(\cdot)$ là GcBlock operator tạo global context representation.

**Mục đích**: Bù đắp thông tin bị mất khi focal distillation chỉ focus cục bộ. Global distillation transfer "quan hệ giữa các vùng" — ví dụ: xe buýt gần vỉa hè, xe máy gần ngã tư.

---

## 4. Attention Loss (Eq. 10)

$$L_{at} = \gamma \cdot \left(||A^S_T - A^S_S||_1 + ||A^C_T - A^C_S||_1\right)$$

Buộc student tạo ra spatial/channel attention maps giống teacher.

---

## 5. Tổng Loss

$$L_{total} = L_{det} + L_{fea} + L_{at} + L_{global}$$

Trong đó $L_{det}$ là detection loss gốc (box + cls + dfl).

---

## 6. Hyper-parameters (từ paper)

| Detector Type | α (fg) | β (bg) | γ (attention) | λ (global) |
|---|---|---|---|---|
| Two-stage (Faster RCNN) | 5×10⁻⁵ | 2.5×10⁻⁵ | 5×10⁻⁵ | 5×10⁻⁷ |
| Anchor-based one-stage (RetinaNet) | 1×10⁻³ | 5×10⁻⁴ | 1×10⁻³ | 5×10⁻⁶ |
| Anchor-free one-stage (FCOS) | 1.6×10⁻³ | 8×10⁻⁴ | 8×10⁻³ | 8×10⁻⁶ |

**YOLO = anchor-free one-stage** → dùng hàng cuối.

Temperature $T = 0.5$ cho tất cả experiments.
Training: 24 epochs, SGD (momentum=0.9, weight_decay=0.0001).

---

## 7. Benchmark — COCO Results (Table 2 từ paper)

### Homogeneous pairs (cùng architecture, R101→R50)

| Model | Backbone (S) | Baseline mAP | +FGD mAP | Δ |
|---|---|---|---|---|
| RetinaNet | ResNet-50 | 37.4 | **40.7** | **+3.3** |
| Faster RCNN | ResNet-50 | 38.4 | **42.0** | **+3.6** |
| RepPoints | ResNet-50 | 38.6 | **42.0** | **+3.4** |
| FCOS | ResNet-50 | 38.5 | **42.7** | **+4.2** |
| MaskRCNN | ResNet-50 | 39.2 | **42.1** | **+2.9** |
| GFL | ResNet-50 | 40.2 | **43.5** | **+3.3** |

### YOLOX result

| Model | Baseline | +FGD | Δ |
|---|---|---|---|
| YOLOX-m (student) ← YOLOX-l (teacher) | 45.9 | **46.6** | +0.7 |

### Instance Segmentation

| Model | Baseline Mask mAP | +FGD Mask mAP | Δ |
|---|---|---|---|
| SOLO (R50) | 33.1 | **36.0** | +2.9 |
| MaskRCNN (R50) | 35.4 | **37.8** | +2.4 |

### AP_S (Small Object) — từ bảng so sánh khác

Trên Faster RCNN R101→R50:
| Method | AP | AP_S | AP_M | AP_L |
|---|---|---|---|---|
| Baseline | 37.9 | 22.4 | 41.1 | 49.1 |
| FGD | 40.5 | 22.6 | **44.7** | **53.2** |
| HMKD (2024) | **41.7** | **24.8** | 44.9 | 54.2 |

---

## 8. So sánh FGD vs CWD vs MGD

| Tiêu chí | CWD | FGD | MGD |
|---|---|---|---|
| **Paper** | ICCV 2021 | CVPR 2022 | ECCV 2022 |
| **Cơ chế** | Channel-wise KL divergence | Focal (fg/bg separation) + Global (pixel relation) + Attention matching | Masked feature reconstruction |
| **Ưu điểm chính** | Đơn giản, stable, hiệu quả trên semantic segmentation | Tốt cho small objects nhờ foreground focus; global context bổ sung | Mạnh nhất trên nhiều benchmark; student tự tái tạo features |
| **Nhược điểm** | Không phân biệt fg/bg → bị background noise | Phụ thuộc GT bounding boxes cho mask $M$ | Tốn thêm GPU/RAM; training time dài hơn |
| **Độ phức tạp implement** | ~1 tuần | ~2 tuần | ~3+ tuần |
| **Kết quả mAP** (Faster RCNN R50 trên COCO) | ~40.0–40.8 | 42.0 | ~42.4 |
| **AP_S improvement** | Moderate | Tốt (focal mechanism) | Tốt nhất (masked reconstruction) |
| **YOLO compatible** | Dễ (channel-wise loss) | Trung bình (cần GT boxes for mask) | Khó hơn (mask generation logic) |

### Kết luận so sánh
- **CWD**: Đơn giản nhất, baseline tốt, thêm ~2–3% mAP
- **FGD**: Tốt hơn CWD ~0.5–1% mAP cho small objects (nhờ fg/bg separation)
- **MGD**: Mạnh nhất ~0.5–1% hơn FGD, nhưng phức tạp và tốn tài nguyên hơn

---

## 9. Phù hợp cho Traffic/Vehicle Detection

FGD **đặc biệt phù hợp** cho traffic scenes vì:

1. **Small objects**: Biển báo, người đi bộ, xe máy ở xa → focal mechanism tập trung vào foreground nhỏ
2. **Background dominance**: Đường, bầu trời, cây xanh chiếm phần lớn ảnh → fg/bg separation giảm noise
3. **Global context**: Quan hệ spatial giữa xe buýt-vỉa hè, xe máy-ngã tư được transfer qua global distillation
4. **One-stage YOLO friendly**: FGD hỗ trợ anchor-free one-stage detectors (FCOS), YOLO thuộc nhóm này

---

## 10. Tools & Repositories

### 10.1 Official Implementation
- **Repo**: https://github.com/yzd-v/FGD
- **Base**: MMDetection framework
- **Usage**:
  ```bash
  # single GPU
  python tools/train.py configs/distillers/fgd/fgd_retina_rx101_64x4d_distill_retina_r50_fpn_2x_coco.py
  # multi GPU
  bash tools/dist_train.sh configs/distillers/fgd/<config>.py 8
  ```
- **Transfer checkpoint**: `python pth_transfer.py --fgd_path $ckpt --output_path $new_ckpt`

### 10.2 MMRazor (OpenMMLab)
- **Repo**: https://github.com/open-mmlab/mmrazor
- **Hỗ trợ**: CWD, MGD configs sẵn tại `configs/distill/mmdet/cwd/`
- **FGD**: Không có config sẵn trong mmrazor (xem Issue #582), nhưng có thể tự implement dựa trên official repo
- **Lưu ý**: mmrazor hỗ trợ framework-agnostic distillation → có thể adapt cho Ultralytics YOLO

### 10.3 Áp dụng cho YOLOv8n (project hiện tại)

FGD **không có sẵn** trong Ultralytics. Để áp dụng cần custom implementation:

```
Pipeline: YOLOv8m (teacher) → FGD → YOLOv8n (student)

Bước 1: Override loss() trong DetectionTrainer (giống Untitled15.ipynb)
Bước 2: Thay MSE loss bằng FGD loss:
   - Tính foreground mask M từ batch["bboxes"]
   - Tính spatial attention A^S và channel attention A^C từ teacher features
   - Tính focal feature loss (Eq. 9) với α/β weighting
   - Tính global loss (Eq. 12) qua GcBlock
   - Tính attention loss (Eq. 10)
Bước 3: Tổng hợp: L_total = L_det + L_focal + L_global + L_attention
```

**Ước lượng thời gian**: ~2 tuần implement + debug (phức tạp hơn MSE-based KD hiện tại trong Untitled15.ipynb, nhưng ít hơn MGD)

---

## 11. Hạn chế của FGD

1. **Phụ thuộc GT bounding boxes**: Foreground mask $M$ cần ground-truth boxes → không áp dụng được cho unsupervised/semi-supervised settings
2. **Hyper-parameter sensitive**: 4 hyper-parameters (α, β, γ, λ) cần tune riêng cho từng loại detector
3. **Adaptation layer**: Nếu teacher/student channels khác nhau (YOLOv8m vs YOLOv8n), cần thêm 1×1 conv adapter — thêm complexity
4. **Không phải state-of-the-art 2024+**: Các phương pháp mới (CrossKD CVPR2024, ScaleKD CVPR2023, DiffKD NeurIPS2023) đã vượt FGD ~1–2% mAP

---

## 12. Đánh giá cho project YOLOv8n → Jetson Nano

| Tiêu chí | Đánh giá |
|---|---|
| Khả thi? | Có, nhưng cần custom code (~2 tuần) |
| Có đáng upgrade từ MSE KD? | Có nếu small object accuracy là ưu tiên |
| mAP gain dự kiến | +0.5–1.5% so với vanilla MSE KD |
| Risk | Hyper-parameter tuning phức tạp; GT boxes dependency |
| Alternative đơn giản hơn | CWD (channel-wise KL, ~1 tuần, +2–3% mAP baseline) |

---

## Nguồn tham khảo

1. Yang et al., "Focal and Global Knowledge Distillation for Detectors," CVPR 2022 — https://arxiv.org/abs/2111.11837
2. Official code — https://github.com/yzd-v/FGD
3. MMRazor — https://github.com/open-mmlab/mmrazor
4. PMC Survey "Knowledge Distillation in Object Detection: A Survey from CNN to Transformer" — https://pmc.ncbi.nlm.nih.gov/articles/PMC12788226/
5. PMC "Foreground separation knowledge distillation for object detection" — https://pmc.ncbi.nlm.nih.gov/articles/PMC11623026/
6. ICCV 2025 Weed Detection KD comparison (CWD vs MGD) — ICCV 2025W/CVPPA
7. CrossKD: Cross-Head Knowledge Distillation for Object Detection, CVPR 2024
8. PKD: General Distillation Framework, NeurIPS 2022
9. HMKD: Knowledge Distillation via Hierarchical Matching for Small Objects — JCST 2024
