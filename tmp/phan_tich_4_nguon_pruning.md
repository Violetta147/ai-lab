# Phân tích 4 nguồn về pruning và thứ tự prune/quantize

## 1) Reddit: prune-then-quantize hay quantize-then-prune?

Nguồn này là một thread hỏi đáp cộng đồng, không phải paper/benchmark chuẩn hóa. Ý chính trong phần trả lời:
- Một số ý kiến nghiêng về **quantize trước, prune sau** khi làm post-training optimization.
- Lý do trực giác được nêu: quantization ảnh hưởng toàn mạng, nên làm sớm để fine-tune trong điều kiện quantized; pruning phức tạp hơn thì làm sau.
- Có lập luận rằng nếu prune trước thì một số “đường dự phòng” đã mất, khiến fine-tune sau quantization khó hồi phục hơn.

Đánh giá độ tin cậy:
- Giá trị tham khảo **thực chiến**, nhưng không đủ để kết luận tổng quát.
- Không có thiết kế thí nghiệm chuẩn (model/dataset/metric thống nhất).

Nguồn: [Reddit r/MachineLearning thread](https://old.reddit.com/r/MachineLearning/comments/qsi0u2/r_prunethenquantize_or_quantizethenprune_for/)

---

## 2) Alignment Forum: train-first vs prune-first

Bài viết dùng toy experiment để so sánh:
- **Train rồi prune** vs **prune rồi train**.
- Kết quả cho thấy với random pruning thì hai phép này không “giao hoán” (không cho kết quả tương đương).
- Với non-random pruning (ví dụ prune node có độ biến thiên activation thấp), mô hình sau pruning có thể gần như giữ chất lượng; prune trước rồi train lại cho kết quả “na ná” nhưng vẫn khác.

Điểm quan trọng:
- Thứ tự thao tác ảnh hưởng kết quả học.
- Có dấu hiệu rằng một phần neuron “ít đóng góp” có thể cắt tương đối an toàn.

Giới hạn:
- Bài mang tính khám phá trên toy setting, không đại diện đầy đủ cho YOLO/object detection quy mô lớn.

Nguồn: [Train first VS prune first in neural networks](https://www.alignmentforum.org/posts/PLqopCagHKo2EK5cE/train-first-vs-prune-first-in-neural-networks)

---

## 3) PyTorch Pruning Tutorial: cơ chế chuẩn của `torch.nn.utils.prune`

Tài liệu chính thức mô tả rõ cơ chế kỹ thuật:

### 3.1 Re-parameterization khi prune
- Khi prune `weight`, PyTorch tạo:
  - `weight_orig` (tham số gốc),
  - `weight_mask` (buffer mask),
  - `weight` (tensor hiệu dụng = `weight_orig * weight_mask`).
- Pruning được áp dụng qua `forward_pre_hooks`.

### 3.2 Local / Iterative / Structured / Global pruning
- **Local pruning**: prune theo từng tensor/layer.
- **Iterative pruning**: prune nhiều vòng, mask mới kết hợp với mask cũ (qua `PruningContainer`).
- **Structured pruning**: ví dụ `ln_structured(..., dim=0)` để cắt theo channel.
- **Global pruning**: prune trên toàn mô hình bằng ngưỡng chung (`global_unstructured`), nên mỗi layer có tỷ lệ sparse khác nhau nhưng global sparsity đạt mục tiêu.

### 3.3 Lưu và “đóng” pruning
- Trạng thái pruning nằm trong `state_dict` (bao gồm `*_orig`, `*_mask`).
- `prune.remove(module, 'weight')` dùng để **làm pruning thành vĩnh viễn** trên parameter `weight` (không hoàn tác pruning, chỉ bỏ re-param/hook).

### 3.4 Mở rộng custom pruning
- Có thể subclass `BasePruningMethod`, cài `compute_mask`, khai báo `PRUNING_TYPE` (`unstructured`, `structured`, `global`) để tương thích iterative mask composition.

Nguồn: [PyTorch Pruning Tutorial](https://docs.pytorch.org/tutorials/intermediate/pruning_tutorial.html)

---

## 4) GeeksforGeeks: pruning cho Decision Tree (khác domain với NN pruning)

Bài này nói về **cây quyết định**:
- **Pre-pruning** (early stopping): giới hạn cây ngay khi train (`max_depth`, `min_samples_split`, ...).
- **Post-pruning**: cho cây grow đầy đủ rồi cắt nhánh yếu (vd. cost-complexity pruning với `ccp_alpha`).
- Mục tiêu: giảm overfitting, cải thiện generalization, mô hình gọn hơn.

Điểm cần phân biệt:
- Đây là pruning cho **tree models**, không phải pruning trọng số/channel trong neural network.
- Triết lý giống nhau ở mức cao (giảm độ phức tạp để tăng tổng quát hóa), nhưng kỹ thuật và công cụ khác hẳn.

Nguồn: [Pruning Decision Trees - GeeksforGeeks](https://www.geeksforgeeks.org/machine-learning/pruning-decision-trees/)

---

## Tổng hợp chéo 4 nguồn

### Điều các nguồn cùng gợi ý
- Pruning có thể giúp giảm kích thước/chi phí tính toán.
- Thứ tự các bước tối ưu (train, prune, quantize, finetune) **quan trọng**, không nên coi là hoán đổi tự do.

### Điều chưa có “đáp án tuyệt đối”
- Không có một quy tắc duy nhất luôn đúng “prune trước hay quantize trước” cho mọi mô hình/dataset/hardware.
- Reddit + Alignment Forum cho trực giác tốt, nhưng chưa thay được benchmark chính thức theo bài toán của bạn.

### Cách áp dụng thực tế cho YOLO/Jetson
- Dựa trên PyTorch/Ultralytics pipeline, nên làm A/B test có kiểm soát:
  1. Nhánh A: prune -> finetune -> quantize -> calibrate
  2. Nhánh B: quantize -> finetune -> prune -> finetune
  3. So sánh: mAP50-95, latency, FPS, RAM/VRAM, năng lượng.
- Quyết định cuối cùng nên theo metric deployment trên thiết bị đích (Jetson), không chỉ theo trực giác.

---

## Kết luận ngắn

- **PyTorch tutorial** là nguồn kỹ thuật cốt lõi để triển khai pruning đúng cơ chế.
- **Reddit** và **Alignment Forum** cho insight về thứ tự tối ưu, nhưng chủ yếu mang tính định hướng.
- **GeeksforGeeks** hữu ích để hiểu tư duy pre/post pruning, nhưng thuộc decision tree nên chỉ tham khảo ở mức khái niệm.
