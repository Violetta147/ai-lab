# Tóm tắt kiến thức & thao tác (từ các buổi discuss)

Tài liệu này gom lại các ý quan trọng: knowledge distillation + logits/MSE, `resume=True`, tuning Ray/W&B, Jetson Nano, và chỉnh sửa script.

---

## 1. Knowledge distillation — vì sao nói “spatial info mất dần” và MSE trên logits là gì?

### Luồng dữ liệu trong mạng (rút gọn)

```
Ảnh đầu vào
  → Backbone (CNN): tạo **feature maps** (bản đồ không gian, còn “hình dạng / vị trí”)
  → Head: gom thành vector **logits** (mỗi lớp một số thô, chưa chuẩn hóa)
  → Softmax: đổi logits → **xác suất** (0–1, tổng = 1)
```

- **Feature**: còn nhiều thông tin không gian (vùng nào có biên, texture…).
- **Logits**: đã nén thành “điểm số” theo từng lớp — không còn bản đồ 2D như feature.
- **Xác suất**: còn nén hơn nữa — chỉ còn “mức tin” cuối cùng cho mỗi lớp.

Vì vậy khi nói “spatial info gone by the time you reach logits/probabilities” ý là: **so với feature map**, logits và đặc biệt là softmax **đã mất phần lớn thông tin không gian**; distillation thường không học trực tiếp từng pixel feature map của teacher, mà học từ **đầu ra gần cuối** (logits hoặc phân phối mềm).

### “Học logits với MSE” nghĩa là gì?

- **Logit** của một lớp là một số thực (ví dụ: xe 8.2, xe buýt 1.5, xe tải 0.3…).
- **Softmax** làm các số lớn càng lớn, số nhỏ càng bị “dìm” → thành xác suất kiểu 0.97 vs 0.01.
- **MSE trên logits**: loss = trung bình bình phương sai khác **từng logit** giữa student và teacher. Student bị ép **khớp cả “độ lớn” và thứ tự tương đối** của các logit, không chỉ lớp argmax.

Ví dụ trực giác:

- Teacher logits: `[8.2, 1.5, 0.3]` → softmax có thể cho xe ≈ 0.97.
- Nếu chỉ dùng **nhãn cứng** hoặc chỉ nhìn **xác suất**, student có thể học “chỉ cần đoán đúng xe” mà **bỏ qua** rằng teacher còn tin tưởng một chút vào “xe buýt” (logit 1.5 vẫn là tín hiệu có ý nghĩa so với 0.3).
- **MSE trên logits** giữ lại kiểu tín hiệu đó vì nó so trực tiếp các số trước softmax.

### KL divergence (thường dùng với “soft labels” + nhiệt độ T)

- Thường so **phân phối mềm** sau softmax với nhiệt độ T>1 — mượt hơn, dễ truyền “quan hệ giữa các lớp”.
- Không mâu thuẫn với Bayesian/TPE: đây là **cách định nghĩa loss khác** (KL vs MSE), cả hai đều có thể dùng trong distillation.
- Một số paper/bài tổng hợp cho thấy **MSE trên logits** có thể thực nghiệm tốt tùy kiến trúc/setup; không phải lúc nào KL cũng thắng.

**Tóm một câu**: Distillation trên logits/MSE không “khôi phục” feature không gian; nó **chuyển kiến thức đã mã hóa trong vector điểm số lớp** từ teacher sang student, và MSE giữ **chi tiết tỉ lệ** giữa các logit tốt hơn softmax làm phẳng.

---

## 2. `resume=True` trong vòng lặp `model.train(epochs=1, ...)` (Ray Tune / ASHA) là gì?

Trong `hyperparametertuning2.py`, mỗi **trial** Ray là một process; ta train **1 epoch mỗi lần** rồi `train.report(...)` để ASHA có metric theo từng epoch.

- **Epoch đầu** (`epoch_idx == 0`): `resume=False` — bắt đầu run train mới từ trọng số pretrained (ví dụ `yolo26n.pt`).
- **Các epoch sau** (`epoch_idx > 0`): `resume=True` — **tiếp tục huấn luyện từ checkpoint của cùng một run vừa rồi** (không load lại từ đầu file `.pt` gốc), để trọng số **nối tiếp** epoch 1 → 2 → … → 10.

Nếu không `resume=True` sau epoch 1, mỗi lần gọi `train(epochs=1)` có thể coi như **một run mới** hoặc reset — ASHA vẫn nhận metric nhưng **quá trình học không liên tục**, không đúng ý “10 epoch cho một bộ hyperparams”.

**Lưu ý thực tế**: Ultralytics lưu checkpoint trong thư mục `project/name` (ví dụ `YOLO26n-Vehicle-Tuning-v2`). Nếu nhiều trial chạy song song cùng `project`/`name`, có thể cần tách `name` theo trial (ví dụ dùng `train.get_context().get_trial_id()`) để tránh đè checkpoint — tùy phiên bản và cách Ray gán thư mục.

---

## 3. Trial vs Run (Ray Tune & W&B)

| Thuật ngữ | Ý nghĩa ngắn |
|-----------|----------------|
| **Trial** (Ray) | Một lần thử **một bộ hyperparameter** cụ thể; train + đo metric. |
| **Run** (W&B) | Thường là **một phiên log** trên dashboard; với Ray, **mỗi trial/worker** có thể hiện thành một “run” riêng → dễ nhầm với “run” theo nghĩa toàn bộ experiment. |

---

## 4. HyperOpt / TPE và “Bayesian”

- **TPE** (Tree-structured Parzen Estimator) là một dạng **tối ưu dựa trên mô hình** (sequential model-based optimization), thường được xếp vào họ **Bayesian optimization** vì nó cập nhật “niềm tin” về vùng hyperparam tốt dựa trên các trial đã chạy.
- **Random search**: mỗi lần chọn hyperparam **ngẫu nhiên**, không dùng lịch sử trial để chọn thông minh hơn.
- Câu kiểu “TPE là random search” là **không chính xác**; HyperOpt mặc định dùng TPE (có cấu trúc), không phải random thuần.

---

## 5. `hyperparametertuning.py` vs W&B

- `wandb.init()` ở **process chính** (notebook) **không tự** sang các **worker Ray**.
- Cần **`WANDB_API_KEY` trong môi trường** để worker/Ultralytics có thể tự log; có issue về **tên run / project** khi dùng Ray — nên **nâng `ultralytics`** (khuyến nghị bản có fix liên quan Ray+tune) và kiểm tra dashboard theo từng trial.

---

## 6. `hyperparametertuning2.py` — đã sửa chính

- Lỗi `python -m pi` → **`pip`**.
- Validate `ULTRALYTICS_API_KEY`, `DATASET_URI`.
- **ASHA** cần metric **mỗi epoch** → vòng lặp `epochs=1` + `train.report` sau mỗi epoch; epoch sau dùng **`resume=True`**.
- Mỗi trial load model mới là **bình thường** (process tách biệt).
- Output JSON có thể là `best_hyperparams_v2.json` (tránh trùng file script 1).

---

## 7. Jetson Nano & pipeline thực tế

- **TensorRT**: engine nên build **trên GPU đích** (Nano Maxwell) — không mang engine từ GPU khác.
- **ONNX cho DeepStream (tài liệu)**: thường **`opset=12`**, **không dynamic** (shape cố định).
- **`imgsz` 640** trên Nano thường quá nặng → thử **320, 416**, đo mAP để đánh đổi tốc độ/chính xác.
- **SAHI** (slice lớn) **không** hướng tới realtime trên Nano.
- **DeepStream vs C++ CUDA repo**: Nano 4GB + OS/JetPack chuẩn (thường 18.04 + JP4) có thể **xung đột** với môi trường Ubuntu 20.04/Python 3.8 tùy chỉnh; DeepStream cũng **tốn tài nguyên** hơn pipeline inference tối giản. Nên **ưu tiên ONNX → TensorRT trên Nano** hoặc giữ C++ CUDA nếu đã ổn định; so sánh benchmark thực tế.

---

## 8. Thứ tự ưu tiên gợi ý (khi ít dữ liệu)

1. Thu thập / làm sạch thêm dữ liệu (nếu < ~5000 ảnh, tuning hưởng ít).
2. Cải thiện model (distillation, có thể kết hợp prune theo chiến lược đã bàn).
3. Sau đó mới hyperparameter tuning quy mô lớn.

---

## 9. File liên quan trong repo

| File | Mục đích |
|------|-----------|
| `hyperparametertuning.py` | `model.tune(..., use_ray=True)` — Ultralytics + Ray |
| `hyperparametertuning2.py` | Ray `Tuner` + HyperOptSearch + ASHA, loop per-epoch |
| `tmp/plan_tuning_and_next_steps.md` | Bản tiếng Anh + link issue/paper |
| `test.ipynb` | So sánh độ phân giải val, export ONNX Nano-friendly |

---

*Nếu cần, có thể bổ sung mục “feature-based distillation” (học trung gian layer) so với logit-only — đó là hướng khác trong nghiên cứu.*
