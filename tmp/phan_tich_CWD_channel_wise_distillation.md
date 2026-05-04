# CWD — Channel-wise Knowledge Distillation for Dense Prediction

> Paper gốc: **"Channel-wise Knowledge Distillation for Dense Prediction"** (ICCV 2021)
> Authors: Changyong Shu, Yifan Liu, Jianfei Gao, Zheng Yan, Chunhua Shen
> PDF: https://openaccess.thecvf.com/content/ICCV2021/papers/Shu_Channel-Wise_Knowledge_Distillation_for_Dense_Prediction_ICCV_2021_paper.pdf
> Code (official): https://github.com/drilistbox/CWD
>
> Paper ứng dụng: **"Enhanced Knowledge Distillation for YOLO via Attention Mechanisms in Smart City Applications"** (WCSE 2025)
> Authors: Yanbo Wang et al. (Inspur Smart City Technology Co., Ltd)
> URL: https://www.wcse.org/index.php?m=content&c=index&a=show&catid=28&id=1402
>
> Benchmark mới nhất: **"Improving Lightweight Weed Detection via Knowledge Distillation"** (ICCV 2025 Workshop CVPPA)
> Authors: Saltık et al.
> PDF: https://openaccess.thecvf.com/content/ICCV2025W/CVPPA/papers/Saltik_Improving_Lightweight_Weed_Detection_via_Knowledge_Distillation_ICCVW_2025_paper.pdf

---

## 1. Ý tưởng cốt lõi

### Trước CWD: Spatial Distillation (cũ)

Phương pháp truyền thống (FitNet, MSE) coi feature map tại mỗi vị trí spatial $(i,j)$ là 1 vector $C$-dimensional → distill theo spatial. Vấn đề: không khai thác ý nghĩa **từng channel** riêng biệt.

### CWD: Channel-wise Distillation (mới)

CWD đảo ngược cách nhìn: mỗi **channel** trong feature map encode thông tin của **1 semantic category** cụ thể. Ví dụ:
- Channel #17 có thể encode "xe buýt"
- Channel #42 có thể encode "đường kẻ vạch"
- Channel #58 có thể encode "người đi bộ"

**Insight chính**: Các activation values trong 1 channel tạo thành 1 "spatial probability map" — nơi nào feature active mạnh = nơi đó có object/semantic tương ứng. CWD normalize mỗi channel thành probability distribution → so sánh bằng KL divergence.

---

## 2. Công thức toán học

### 2.1 Channel Normalization (softmax per channel)

Cho feature map $y$ có $C$ channels, mỗi channel có $H \times W$ spatial locations. Normalize channel thứ $c$:

$$\phi(y_c)_i = \frac{\exp(y_{c,i} / \tau)}{\sum_{j=1}^{H \times W} \exp(y_{c,j} / \tau)}$$

Trong đó:
- $c = 1, 2, ..., C$: index channel
- $i = 1, 2, ..., H \times W$: index vị trí spatial
- $\tau$: temperature hyperparameter

**Softmax chạy theo chiều spatial (H×W)** cho mỗi channel riêng biệt → mỗi channel trở thành 1 probability distribution.

### 2.2 KL Divergence Loss per Channel

$$L_{CWD} = \frac{1}{C} \sum_{c=1}^{C} \text{KL}\left(\phi(y^T_c) \| \phi(y^S_c)\right)$$

$$= \frac{1}{C} \sum_{c=1}^{C} \sum_{i=1}^{H \times W} \phi(y^T_c)_i \cdot \log \frac{\phi(y^T_c)_i}{\phi(y^S_c)_i}$$

Trong đó:
- $y^T_c$: channel $c$ của teacher feature map
- $y^S_c$: channel $c$ của student feature map
- KL divergence **asymmetric**: teacher là "target", student là "predicted"

### 2.3 Channel Mismatch Handling

Nếu teacher và student có số channels khác nhau (ví dụ YOLOv8m: 192ch vs YOLOv8n: 64ch), thêm **1×1 convolution adapter** trên student để align số channels trước khi tính CWD loss.

### 2.4 Tổng Loss

$$L_{total} = L_{det} + \lambda \cdot L_{CWD}$$

- $L_{det}$: Standard YOLO detection loss (BCE cls + CIoU box + DFL)
- $\lambda$: distillation weight (paper gốc dùng 1.0–3.0)

---

## 3. Temperature τ — Chi tiết

### 3.1 Vai trò

$\tau$ kiểm soát "độ mềm" của probability distribution khi normalize channel:
- $\tau$ nhỏ (0.5): Distribution nhọn, tập trung vào pixel có activation cao nhất → precise nhưng dễ overfitting
- $\tau$ lớn (5.0): Distribution phẳng, trải đều hơn → smooth nhưng mất thông tin cụ thể

### 3.2 Kết quả thực nghiệm (ICCV 2025 Workshop — YOLO11x→YOLO11n)

Benchmark mới nhất (Saltık et al., 2025) sweep temperature trên weed detection:

| τ | Precision | Recall | mAP50 | mAP50-95 |
|---|---|---|---|---|
| 1.0 | 0.862±0.020 | 0.756±0.020 | 0.854±0.006 | 0.575±0.009 |
| **2.0** | **0.857±0.017** | **0.776±0.014** | **0.859±0.003** | **0.578±0.003** |
| 3.0 | 0.856±0.021 | 0.774±0.019 | 0.856±0.002 | 0.574±0.005 |
| 4.0 | 0.847±0.012 | 0.782±0.021 | 0.857±0.006 | 0.576±0.006 |
| Baseline (no KD) | — | — | 0.834 | — |

**Kết luận**: τ = 2.0 cho kết quả tốt nhất (+2.5% mAP50). τ ≥ 3 bắt đầu over-smooth.

### 3.3 Khuyến nghị τ theo use case

| Use case | τ khuyến nghị | Lý do |
|---|---|---|
| CWD paper gốc (segmentation) | 4.0 | Segmentation cần broader spatial context |
| WCSE 2025 (YOLO smart city) | 0.5 | Detection cần precise spatial focus |
| ICCV 2025 Workshop (weed/YOLO11) | **2.0** | Benchmark mới nhất, optimal cho detection |
| **Project hiện tại** (4 classes, traffic) | **2.0** (thử trước) | Theo benchmark ICCV 2025 Workshop |

---

## 4. WCSE 2025: CWD + Attention cho YOLO Smart City

### 4.1 Paper Summary

**"Enhanced Knowledge Distillation for YOLO via Attention Mechanisms in Smart City Applications"**
- Inspur Smart City Technology (pp. 10-14, WCSE 2025, Jeju Island)
- **Vấn đề**: CWD gốc bị background noise khi áp dụng cho YOLO detection → thêm attention modules để filter
- **Giải pháp**: Thêm attention modules vào CWD framework → model focus vào relevant features, giảm background interference
- **Application**: Real-time object detection trong smart city scenarios
- **Kết quả báo cáo**: mAP50 tăng từ 0.735 → 0.751 (+2.2%)

### 4.2 Pipeline từ WCSE 2025

```
1. Train teacher YOLOv8l: 50 epochs trên traffic dataset
2. Freeze teacher
3. Student YOLOv8n + CWD loss + attention modules
4. Optimizer: Adam, lr=0.001, momentum=0.9
5. Temperature τ = 0.5 (paper's choice — nhỏ hơn benchmark mới)
6. Distillation weight = 1.0
```

---

## 5. CWD vs Các phương pháp khác

### 5.1 Benchmark ICCV 2025 Workshop (CWD vs MGD trên YOLO11)

| Method | Best Config | mAP50 | Δ vs Baseline | Per-class improvement |
|---|---|---|---|---|
| Baseline YOLO11n | — | 0.834 | — | — |
| **CWD** | **τ = 2.0** | **0.859** | **+2.5%** | Fallopia +3.7%, Convolvulus +2.4% |
| MGD | α = 2×10⁻⁵ | 0.853 | +1.9% | Echinochloa +3.1% |
| Teacher YOLO11x | — | 0.895 | — | — |

**CWD tốt hơn MGD 0.6% mAP50** trên visually similar classes.

### 5.2 Benchmark Segmentation (Cityscapes)

| Method | mIoU (PSPNet R18→R101) |
|---|---|
| Baseline student | 69.85 |
| SKD | 72.70 |
| **CWD** | **73.53** |
| MGD | 73.63 |

### 5.3 So sánh tổng quan

| Tiêu chí | CWD | MSE Feature (Untitled15.ipynb) | KL Response-based | FGD |
|---|---|---|---|---|
| **Cơ chế** | Channel-wise KL trên normalized feature maps | MSE trên raw spatial logits | KL trên classification softmax | Focal fg/bg + Global relation |
| **Distill gì** | Semantic attention per channel | Raw feature magnitude | Classification probability | Foreground features + pixel relations |
| **Temperature** | τ = 2.0 (detection) | Không cần | T = 3–5 | T = 0.5 (cho attention) |
| **Channel mismatch** | 1×1 conv adapter | N/A (same output channels) | N/A | 1×1 conv adapter |
| **Ưu điểm** | Stable, loại bỏ magnitude bias, hiệu quả trên similar classes | Đơn giản nhất, giữ nguyên logit scale | Đơn giản, dark knowledge | Tốt cho small objects |
| **Nhược điểm** | Mất thông tin magnitude (do normalization) | Sensitive to magnitude scale differences | Hạn chế cho detection (chỉ cls head) | Phức tạp, cần GT boxes |
| **mAP gain** | +2–3% | +1–3% | +0.5–2% | +3–4% |
| **Implement** | ~1 tuần | ✅ Done | ~3 ngày | ~2 tuần |

---

## 6. Implementation cho YOLOv8

### 6.1 CWD Loss Function (PyTorch)

```python
import torch
import torch.nn.functional as F

def cwd_loss(
    student_feat: torch.Tensor,
    teacher_feat: torch.Tensor,
    tau: float,
) -> torch.Tensor:
    """Channel-wise Distillation Loss (Shu et al., ICCV 2021).

    Args:
        student_feat: (B, C, H, W) student feature map
        teacher_feat: (B, C, H, W) teacher feature map (same C after adapter)
        tau: temperature for spatial softmax normalization
    """
    B, C, H, W = student_feat.shape

    # Reshape to (B, C, H*W) — each channel becomes a spatial vector
    s = student_feat.reshape(B, C, -1)  # (B, C, H*W)
    t = teacher_feat.reshape(B, C, -1)  # (B, C, H*W)

    # Softmax normalization per channel (along spatial dim)
    s_prob = F.softmax(s / tau, dim=-1)  # (B, C, H*W)
    t_prob = F.softmax(t / tau, dim=-1)  # (B, C, H*W)

    # KL divergence per channel, averaged over channels and batch
    loss = F.kl_div(
        s_prob.log(),
        t_prob,
        reduction="none",
    ).sum(dim=-1).mean()  # sum over spatial, mean over (B, C)

    return loss
```

### 6.2 Channel Adapter (khi teacher/student channels khác nhau)

```python
class ChannelAdapter(torch.nn.Module):
    """1x1 conv to match student channels to teacher channels."""

    def __init__(self, student_channels: int, teacher_channels: int):
        super().__init__()
        self.conv = torch.nn.Conv2d(student_channels, teacher_channels, 1, bias=False)
        self.bn = torch.nn.BatchNorm2d(teacher_channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.bn(self.conv(x))
```

### 6.3 Tích hợp vào PrunedTrainer (Untitled15.ipynb)

Nếu muốn thêm CWD vào loss() hiện tại (bổ sung cho MSE):

```python
def loss(self, batch, preds=None):
    if preds is None:
        preds = self.model(batch["img"])

    student_loss, loss_items = super().loss(batch, preds)

    with torch.no_grad():
        t_preds = self._teacher(batch["img"])

    s_feats = preds[1] if isinstance(preds, tuple) else preds
    t_feats = t_preds[1] if isinstance(t_preds, tuple) else t_preds

    # CWD loss thay cho MSE loss
    kd_loss = torch.tensor(0.0, device=self.device)
    for s_feat, t_feat in zip(s_feats, t_feats):
        if s_feat.shape[-2:] != t_feat.shape[-2:]:
            s_feat = F.interpolate(s_feat, size=t_feat.shape[-2:], mode="bilinear", align_corners=False)
        # Nếu channels khác nhau → cần adapter (không áp dụng nếu cùng Detect head output)
        kd_loss = kd_loss + cwd_loss(s_feat, t_feat, tau=2.0)

    alpha = self._kd_alpha
    total_loss = (1.0 - alpha) * student_loss + alpha * kd_loss
    return total_loss, loss_items
```

---

## 7. Repos & Tools

| Repo | Mô tả | Phù hợp cho |
|---|---|---|
| [drilistbox/CWD](https://github.com/drilistbox/CWD) | Official CWD implementation (segmentation) | Tham khảo formula, PSPNet/DeepLab |
| [huangzongmou/yolov8_Distillation](https://github.com/huangzongmou/yolov8_Distillation) | CWD/MGD cho YOLOv8, fork Ultralytics cũ | Quick start, cần port sang version mới |
| [KefanZhan/YOLOv8-KD](https://github.com/KefanZhan/YOLOv8-KD) | Multi-method KD cho YOLOv8 (2025) | Multiple methods, newer code |
| [open-mmlab/mmrazor](https://github.com/open-mmlab/mmrazor) | CWD config tại `configs/distill/mmdet/cwd/` | Production-grade, MMDetection-based |

---

## 8. Đánh giá cho project YOLOv8n → Jetson Nano

| Tiêu chí | Đánh giá |
|---|---|
| **Khả thi?** | Có, ~1 tuần implement |
| **Có đáng upgrade từ MSE hiện tại?** | Có nếu muốn stable improvement (+2–3%) |
| **Lợi thế so với MSE** | Loại bỏ magnitude bias, tốt cho similar classes (car↔truck) |
| **Temperature** | Bắt đầu τ = 2.0 (theo ICCV 2025 benchmark) |
| **Distillation weight** | λ = 1.0 (theo WCSE 2025) |
| **Risk** | Thấp — CWD stable, ít hyper-params cần tune |
| **Kết hợp được với pruning?** | Có — CWD loss thay MSE loss trong Untitled15.ipynb |
| **Inference impact** | Không — CWD chỉ ảnh hưởng training, inference giữ nguyên |

### Quyết định cho project

1. **Nếu thời gian hạn chế**: Giữ MSE (Untitled15.ipynb) — đã hoạt động tốt
2. **Nếu muốn improve +1%**: Thay MSE bằng CWD trong loss() — ~2–3 ngày
3. **Nếu muốn maximize**: CWD + MSE hybrid — ~1 tuần

---

## Tại sao CWD được khuyến nghị cho traffic detection?

1. **Visually similar classes**: bus, car, truck có shape/color tương tự → CWD giúp student phân biệt bằng channel-level semantic attention
2. **Background dominance**: Đường, bầu trời chiếm phần lớn ảnh → CWD normalize per channel nên giảm background bias tự nhiên
3. **Stable across seeds**: ICCV 2025 benchmark chạy 5 seeds, std rất nhỏ (±0.003 mAP50) → reliable
4. **No GT dependency**: Không cần GT boxes (khác FGD) → dễ implement, ít bug
5. **Proven trên YOLO**: WCSE 2025 và ICCV 2025 Workshop đều test trên YOLO architectures

---

## Nguồn tham khảo

1. Shu et al., "Channel-wise Knowledge Distillation for Dense Prediction" (ICCV 2021) — https://openaccess.thecvf.com/content/ICCV2021/papers/Shu_Channel-Wise_Knowledge_Distillation_for_Dense_Prediction_ICCV_2021_paper.pdf
2. Official CWD code — https://github.com/drilistbox/CWD
3. Wang et al., "Enhanced Knowledge Distillation for YOLO via Attention Mechanisms in Smart City Applications" (WCSE 2025) — https://www.wcse.org/index.php?m=content&c=index&a=show&catid=28&id=1402
4. Saltık et al., "Improving Lightweight Weed Detection via Knowledge Distillation" (ICCV 2025 Workshop) — https://openaccess.thecvf.com/content/ICCV2025W/CVPPA/papers/Saltik_Improving_Lightweight_Weed_Detection_via_Knowledge_Distillation_ICCVW_2025_paper.pdf
5. huangzongmou/yolov8_Distillation — https://github.com/huangzongmou/yolov8_Distillation
6. KefanZhan/YOLOv8-KD — https://github.com/KefanZhan/YOLOv8-KD
7. OpenMMLab mmrazor — https://github.com/open-mmlab/mmrazor
8. Fan et al. (2024), NAS + CWD for marine organism detection (referenced in Scientific Reports 2026)
9. PMC Survey "Knowledge Distillation in Object Detection" — https://pmc.ncbi.nlm.nih.gov/articles/PMC12788226/
