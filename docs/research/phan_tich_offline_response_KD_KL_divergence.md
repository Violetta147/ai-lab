# Offline Response-based KD (KL Divergence) cho YOLOv8

> Phương pháp gốc: **Hinton et al., "Distilling the Knowledge in a Neural Network" (2015)**
> arXiv: https://arxiv.org/abs/1503.02531
> Repos chính:
> - https://github.com/huangzongmou/yolov8_Distillation (CWD/MGD cho YOLOv8, fork Ultralytics)
> - https://github.com/KefanZhan/YOLOv8-KD (Multi-method KD cho YOLOv8 + Hybrid Quantization)
> - Ultralytics Issue #2858: Community discussion on YOLOv8m→YOLOv8n distillation

---

## 1. Khái niệm cốt lõi

### 1.1 Hard Labels vs Soft Labels

- **Hard labels**: One-hot vector, ví dụ `[0, 0, 1, 0]` (class "motor")
- **Soft labels**: Phân phối xác suất từ teacher, ví dụ `[0.02, 0.05, 0.88, 0.05]`

Soft labels chứa **dark knowledge** — thông tin về quan hệ giữa các class mà hard labels phá hủy. Ví dụ: teacher nói "ảnh này 88% là motor, 5% là car" → student học được motor và car có visual similarity.

### 1.2 Temperature Scaling

Softmax chuẩn tạo ra phân phối quá "nhọn" (peaky) — class đúng gần 1.0, còn lại gần 0.0. Temperature $T$ làm mềm phân phối:

$$p_i(T) = \frac{\exp(z_i / T)}{\sum_j \exp(z_j / T)}$$

| Temperature | Hiệu ứng |
|---|---|
| $T = 1$ | Softmax chuẩn (peaky) — dùng cho hard prediction |
| $T = 3$ | Mềm vừa — **starting point được khuyến nghị** |
| $T = 5$ | Mềm hơn — dùng khi student học chậm hoặc teacher quá confident |
| $T \to \infty$ | Uniform distribution — mất hết thông tin |

**Tại sao $T = 3$ trước?** Nghiên cứu của Hinton (2015) và các follow-up cho thấy $T \in [2, 5]$ là range tối ưu cho classification. Với object detection, $T = 3$ cân bằng giữa giữ dark knowledge và không over-smooth.

### 1.3 KL Divergence

$$\text{KL}(p \| q) = \sum_i p_i \log \frac{p_i}{q_i}$$

- $p$: teacher's soft probability (target distribution)
- $q$: student's soft probability (predicted distribution)
- KL = 0 khi student hoàn hảo match teacher
- KL > 0 luôn (non-negative)

**Forward KL vs Reverse KL:**
- Forward KL: $\text{KL}(p_T \| p_S)$ — **mode-covering**, student cố gắng cover toàn bộ teacher distribution
- Reverse KL: $\text{KL}(p_S \| p_T)$ — **mode-seeking**, student tập trung vào peak chính

Trong KD chuẩn (Hinton 2015), dùng **Forward KL**.

---

## 2. Công thức Loss (Hinton 2015)

### 2.1 Total Loss

$$\mathcal{L}_{total} = (1 - \alpha) \cdot \mathcal{L}_{hard} + \alpha \cdot T^2 \cdot \mathcal{L}_{KD}$$

Trong đó:
- $\mathcal{L}_{hard}$: Cross-entropy giữa student prediction (tại $T=1$) và ground-truth hard labels
- $\mathcal{L}_{KD}$: KL divergence giữa soft outputs của teacher và student (tại temperature $T$)
- $\alpha$: trọng số distillation (thường 0.5)
- $T^2$: **compensation factor** — cần thiết vì khi $T$ tăng, gradient bị scale xuống $1/T^2$

### 2.2 Tại sao nhân $T^2$?

Khi temperature tăng, softmax outputs trở nên phẳng hơn → gradient nhỏ hơn. Cụ thể, gradient theo logit $z_i$ bị chia cho $T^2$. Nhân $T^2$ vào loss bù lại hiệu ứng này, giữ gradient magnitude ổn định bất kể giá trị $T$.

Khi $T \to \infty$: $T^2 \cdot \text{KL}(p_T(T) \| p_S(T)) \approx \frac{1}{2} ||z_T - z_S||_2^2$ → tương đương MSE trên raw logits.

---

## 3. Áp dụng cho YOLOv8 Detection

### 3.1 Thách thức: Detection ≠ Classification

YOLOv8 detection head output có **2 thành phần** cần distill riêng:

1. **Classification logits**: $(B, \text{nc}, H \times W)$ — áp dụng KL divergence trực tiếp
2. **Regression logits (DFL)**: $(B, 4 \times \text{reg\_max}, H \times W)$ — Distribution Focal Loss representation

### 3.2 Cách tách logits từ Detect head output

```python
# Detect head output per scale: (B, C, H, W) where C = 4*reg_max + num_classes
output = detect_head_output  # shape: (B, 4*reg_max+nc, H, W)

# Reshape to (B, H*W, C)
B, C, H, W = output.shape
reshaped = output.permute(0, 2, 3, 1).reshape(B, H * W, C)

# Split
reg_logits = reshaped[..., :4 * reg_max]   # DFL regression
cls_logits = reshaped[..., 4 * reg_max:]    # Classification
```

### 3.3 KL Divergence cho Classification

```python
cls_kd_loss = F.kl_div(
    F.log_softmax(student_cls / T, dim=-1),  # student log-probs
    F.softmax(teacher_cls / T, dim=-1),       # teacher probs
    reduction="batchmean",
) * (T ** 2)
```

### 3.4 KL Divergence cho DFL Regression

DFL regression logits cũng là probability distribution (softmax over reg_max bins). Có thể distill bằng KL tương tự:

```python
# Reshape DFL: (B, H*W, 4, reg_max) → apply KL per coordinate
student_dfl = student_reg.reshape(B, -1, 4, reg_max)
teacher_dfl = teacher_reg.reshape(B, -1, 4, reg_max)

dfl_kd_loss = F.kl_div(
    F.log_softmax(student_dfl / T, dim=-1),
    F.softmax(teacher_dfl / T, dim=-1),
    reduction="batchmean",
) * (T ** 2)
```

### 3.5 Tổng Distillation Loss

$$\mathcal{L}_{distill} = \mathcal{L}_{cls\_kd} + \lambda_{dfl} \cdot \mathcal{L}_{dfl\_kd}$$

$$\mathcal{L}_{total} = (1 - \alpha) \cdot \mathcal{L}_{det} + \alpha \cdot \mathcal{L}_{distill}$$

- $\mathcal{L}_{det}$: Standard YOLO detection loss (BCE cls + CIoU box + DFL)
- $\lambda_{dfl}$: trọng số cho DFL distillation (thường 0.5–1.0)

---

## 4. Pipeline thực thi

```
Step 1: Train teacher (YOLOv8l hoặc YOLOv8m)
    model_t = YOLO('yolov8l.pt')
    model_t.train(data=data, epochs=100)

Step 2: Freeze teacher
    teacher = model_t.model.eval()
    for p in teacher.parameters():
        p.requires_grad = False

Step 3: Forward cả hai trên cùng batch
    with torch.no_grad():
        t_preds = teacher(batch["img"])      # teacher predictions
    s_preds = student(batch["img"])          # student predictions (from training loop)

Step 4: Compute KD loss
    L_det = standard_detection_loss(s_preds, batch)
    L_kd = kl_distillation_loss(s_preds, t_preds, T=3)
    L_total = (1 - alpha) * L_det + alpha * L_kd

Step 5: Backprop qua student only
    L_total.backward()
    optimizer.step()
```

---

## 5. Repos phân tích

### 5.1 huangzongmou/yolov8_Distillation

- **URL**: https://github.com/huangzongmou/yolov8_Distillation
- **Cơ chế**: Fork Ultralytics, thêm `Distillation` parameter vào `model.train()`
- **Sử dụng**:
  ```python
  model_t = YOLO('yolov8l.pt')
  model_t.train(data=data, epochs=100, Distillation=None)

  model_s = YOLO('yolov8s.pt')
  model_s.train(data=data, epochs=100, Distillation=model_t.model)
  ```
- **KD methods**: CWD (Channel-Wise Distillation) và MGD (Masked Generative Distillation)
- **Thay đổi code**: `/ultralytics/yolo/engine/trainer.py` dòng ~176 — thay đổi channel count + chọn CWDLoss hoặc MGDLoss
- **Expected gain** (theo tác giả): **+0.2–0.5 mAP** ("炼丹需要看各位施主的缘分")
- **Lưu ý quan trọng** (từ tác giả): "大学教授不一定教好小学生" — Teacher quá mạnh không chắc dạy tốt student yếu

**Vấn đề đã biết (Issues)**:
- Issue #15: CUDA OOM khi forward cả teacher + student — cần giảm batch size
- Repo cũ, dựa trên Ultralytics version cũ — có thể cần port sang version mới

### 5.2 KefanZhan/YOLOv8-KD

- **URL**: https://github.com/KefanZhan/YOLOv8-KD
- **Cơ chế**: Hỗ trợ nhiều KD methods trên YOLOv8 (newer, 2025)
- **Features**:
  - Multiple KD methods (trong thư mục `OtherKD/`)
  - Hybrid Quantization kết hợp với KD
  - Extra args cho KD trong `main.py`
- **Ưu điểm**: Mới hơn, code structure rõ ràng hơn huangzongmou

### 5.3 StackOverflow Case Study: YOLO11x → YOLO11n

- **URL**: https://datascience.stackexchange.com/questions/134136/
- **Vấn đề**: KD performance **tệ hơn** native training
- **Implementation chi tiết** (rất có giá trị tham khảo):
  ```python
  def distillation_loss(student_raw_outputs, teacher_raw_outputs, temperature, num_classes, reg_max):
      for each scale:
          # Split cls and reg logits
          student_cls = reshaped[..., -num_classes:]
          teacher_cls = reshaped[..., -num_classes:]

          # KL for classification
          cls_kd = F.kl_div(
              F.log_softmax(student_cls / T, dim=-1),
              F.softmax(teacher_cls / T, dim=-1),
              reduction="batchmean"
          ) * (T ** 2)

          # KL for DFL regression
          dfl_kd = F.kl_div(
              F.log_softmax(student_dfl / T, dim=-1),
              F.softmax(teacher_dfl / T, dim=-1),
              reduction="batchmean"
          ) * (T ** 2)
  ```
- **Bài học**: Temperature=5, alpha=0.5 vẫn không đủ. Nguyên nhân có thể:
  - Capacity gap quá lớn (11x → 11n)
  - Data không đủ đa dạng
  - Classification KD trên detection head không hiệu quả bằng feature-based

---

## 6. Temperature Guidelines

| Scenario | T | Lý do |
|---|---|---|
| Starting point | 3 | Cân bằng giữa dark knowledge và signal clarity |
| Student học chậm | 5 | Mềm hơn, teacher's dark knowledge rõ hơn |
| Teacher rất confident | 5–10 | Phá vỡ overconfident peaks |
| Few classes (nc ≤ 5) | 2–3 | Ít class → ít dark knowledge cần transfer |
| Many classes (nc > 20) | 5–10 | Nhiều inter-class relationships cần transfer |
| Student gần bằng teacher | 1–3 | Student đã tốt, chỉ cần fine signal |
| **Project hiện tại** (4 classes: bus/car/motor/truck) | **3** | Ít class, vehicles có visual similarity → T=3 đủ |

**Nếu T=3 không hiệu quả**: Tăng lên T=5. Nếu vẫn không → vấn đề không phải temperature mà là capacity gap hoặc loss formulation.

---

## 7. So sánh: KL Divergence vs MSE on Logits

| Tiêu chí | KL Divergence (soft labels) | MSE on raw logits |
|---|---|---|
| **Input** | Softmax probabilities (soft labels) | Raw logits (trước activation) |
| **Temperature** | Cần T > 1 để làm mềm | Không cần (logits đã có full scale) |
| **Dark knowledge** | Tốt ở T phù hợp | Tốt hơn ở scale nhỏ (giữ nguyên magnitude) |
| **Gradient behavior** | Cần $T^2$ compensation | Gradient tỷ lệ trực tiếp với logit gap |
| **Khi $T \to \infty$** | KL → MSE (Hinton 2015 chứng minh) | Là chính nó |
| **Phù hợp cho detection** | Tốt cho classification head | Tốt cho feature-based / regression |
| **Implementation** | Phức tạp hơn (cần tách cls/dfl, chọn T) | Đơn giản hơn (MSE trực tiếp) |
| **Dùng trong Untitled15.ipynb** | ✗ | ✓ (MSE on preds[1]) |

**Kết luận**: Cho project hiện tại (4 classes, YOLOv8m→YOLOv8n), **MSE on spatial logits** (như Untitled15.ipynb) là lựa chọn pragmatic nhất. KL Divergence response-based phù hợp hơn khi:
- Muốn distill classification head riêng biệt
- Có nhiều classes (>10) với rich inter-class relationships
- Teacher và student cùng architecture (chỉ khác size)

---

## 8. Expected Gains & Effort

| Method | Effort | Expected mAP gain | Risk |
|---|---|---|---|
| **MSE on features** (current Untitled15.ipynb) | ✅ Done | +1–3% | Thấp |
| **KL Divergence response-based** | ~3 ngày | +0.5–2% | Trung bình (cần tune T, α) |
| **CWD** (channel-wise) | ~1 tuần | +2–3% | Thấp |
| **FGD** (focal + global) | ~2 tuần | +3–4% | Trung bình (hyper-param tuning) |
| **MGD** (masked generative) | ~3+ tuần | +3–4.5% | Cao (phức tạp) |

---

## 9. Áp dụng cho project hiện tại

### So với Untitled15.ipynb (MSE on preds[1])

Untitled15.ipynb đã implement **feature-based KD** bằng MSE loss trên spatial logits (preds[1]). Thêm KL Divergence response-based sẽ:

- **Bổ sung**: Distill thêm classification probability distribution (dark knowledge về class relationships)
- **Không thay thế**: Giữ MSE feature loss, thêm KL cls loss là phương pháp tốt nhất
- **Hybrid loss**:
  ```python
  L_total = (1 - α) * L_det + α_feat * L_mse_features + α_cls * L_kl_classification
  ```

### Khi nào nên thêm KL Divergence?

1. Khi MSE-only KD đã converge nhưng mAP chưa đủ
2. Khi confusion matrix cho thấy student nhầm giữa các class giống nhau (car↔truck, bus↔truck)
3. Khi có thời gian (~3 ngày thêm) và muốn squeeze thêm +0.5% mAP

### Khi nào KHÔNG cần?

1. Nếu MSE KD đã đạt target mAP
2. Nếu bottleneck là inference speed (KL không giúp speed)
3. Nếu chỉ có 4 classes → dark knowledge hạn chế

---

## Nguồn tham khảo

1. Hinton et al., "Distilling the Knowledge in a Neural Network" (2015) — https://arxiv.org/abs/1503.02531
2. huangzongmou/yolov8_Distillation — https://github.com/huangzongmou/yolov8_Distillation
3. KefanZhan/YOLOv8-KD — https://github.com/KefanZhan/YOLOv8-KD
4. Ultralytics Issue #2858 — https://github.com/ultralytics/ultralytics/issues/2858
5. StackOverflow YOLO KD case study — https://datascience.stackexchange.com/questions/134136/
6. Ultralytics Glossary: Knowledge Distillation — https://www.ultralytics.com/glossary/knowledge-distillation
7. PMC Survey "KD in Object Detection: CNN to Transformer" — https://pmc.ncbi.nlm.nih.gov/articles/PMC12788226/
8. Chandrasegaran et al., "Revisiting Label Smoothing and KD" (ICML 2022) — https://proceedings.mlr.press/v162/chandrasegaran22a
9. Cho & Hariharan, "On the Efficacy of Knowledge Distillation" (ICCV 2019) — https://openaccess.thecvf.com/content_ICCV_2019/papers/Cho_On_the_Efficacy_of_Knowledge_Distillation_ICCV_2019_paper.pdf
10. MMYOLO YOLOv8 Loss Description — https://mmyolo.readthedocs.io/en/stable/recommended_topics/algorithm_descriptions/yolov8_description.html
