Dưới đây là phần tiếp theo của Knowledge Base dạng Q&A, đi sâu vào **chi tiết triển khai lập trình, thuật toán, công thức toán học và thiết kế hàm Loss** dựa trên các tài liệu đã cung cấp:

### PHẦN 7: CÔNG THỨC TOÁN HỌC VÀ THIẾT KẾ HÀM LOSS TRONG CHƯNG CẤT TRI THỨC

**Q: Công thức toán học cốt lõi của hàm mất mát trong Chưng cất Logit (Response-based KD) là gì? Tại sao phải nhân với $t^2$?**
**A:** Trong Chưng cất Logit, hàm phân phối xác suất dự đoán được làm "mềm" bằng hàm Softmax có kèm theo nhiệt độ $t$ (hoặc $T$):
$y_i(x|t) = \frac{e^{z_i(x)/t}}{\sum_j e^{z_j(x)/t}}$.
Hàm mất mát chưng cất ($E$) kết hợp giữa Cross-Entropy của Soft Target (với Teacher) và Cross-Entropy của Hard Target (với Nhãn gốc ở $t=1$) được biểu diễn bằng công thức:
$E(x|t) = -t^2 \sum_i \hat{y}_i(x|t) \log y_i(x|t) - \sum_i \bar{y}_i \log y_i(x|1)$.
*(Trong đó: $\hat{y}_i$ là output của Teacher, $y_i$ là output của Student, $\bar{y}_i$ là nhãn thực tế).*
**Lý do nhân với $t^2$:** Khi nhiệt độ $t$ tăng lên, đạo hàm (gradient) của hàm mất mát theo trọng số mô hình sẽ bị thu nhỏ lại theo tỷ lệ $\frac{1}{t^2}$. Do đó, việc nhân thành phần loss của Soft Target với $t^2$ giúp cân bằng độ lớn gradient, đảm bảo Student vừa học từ Teacher vừa học từ nhãn gốc một cách đồng đều. Về mặt toán học, khi $t$ tiến tới vô cực, phần KD Loss này tương đương với hàm sai số toàn phương trung bình (MSE) giữa các logit gốc ($z_i$) của hai mô hình.

**Q: Thuật toán Chưng cất Đặc trưng (Feature-based) và Chưng cất Quan hệ (Relation-based) được định nghĩa bằng toán học như thế nào?**
**A:** 
*   **Feature-based KD:** Tối ưu hóa khoảng cách giữa các bản đồ đặc trưng ở các lớp trung gian. Công thức:
    $L_{FeaD}(f_t(x), f_s(x)) = L_F(\phi_t(f_t(x)), \phi_s(f_s(x)))$.
    *(Trong đó $\phi_t, \phi_s$ là các hàm biến đổi (transformation functions / adapter) dùng để đồng bộ kích thước kênh (channels) hoặc kích thước bản đồ đặc trưng giữa Teacher và Student; $L_F$ thường là L2-loss hoặc L1-loss)*.
*   **Relation-based KD:** Khai thác quan hệ giữa các lớp trong cùng một mạng. Một thuật toán tiêu biểu là sử dụng **ma trận FSP (Flow of Solution Procedure)** tính bằng tích vô hướng giữa hai feature map ở hai lớp khác nhau ($F_1$ và $F_2$):
    $G_{i,j}(x; W) = \frac{1}{h \times w} \sum_{s=1}^{h} \sum_{t=1}^{w} F_1^{s,t,i}(x; W) \times F_2^{s,t,j}(x; W)$.
    Loss sẽ là khoảng cách L2 giữa ma trận FSP của Teacher và Student: $L_{KD} = \frac{1}{N} \sum_x \sum_i \lambda_i ||G_{T_i} - G_{S_i}||_2^2$.

**Q: Thuật toán SOKD (Semi-Online Knowledge Distillation) xây dựng hàm Loss như thế nào để KBM và Student cùng học?**
**A:** Trong framework SOKD, Teacher bị đóng băng, trong khi module trung gian KBM (Knowledge Bridge Module) và Student được cập nhật đồng thời.
*   **Loss của KBM:** $L_{kbm} = \alpha_1 L_{kbm}^{ce} + \alpha_2 KL(p_{kbm}, p_t) + \alpha_3 KL(p_{kbm}, p_s)$.
    *(KBM học từ nhãn gốc $ce$, học biểu diễn của Teacher $p_t$, và nhận phản hồi ngược từ Student $p_s$ để không quá khó so với khả năng của Student)*.
*   **Loss của Student:** $L_s = \lambda_1 L_s^{ce} + \lambda_2 KL(p_s, p_{kbm})$.
    *(Student học từ nhãn gốc và cố gắng bắt chước KBM thay vì bắt chước trực tiếp Teacher)*.

**Q: Công thức Ủ nhiệt (Temperature Annealing) dùng trong tối ưu hóa chưng cất mô hình cho Edge Computing là gì?**
**A:** Khi huấn luyện cho thiết bị biên, nhiệt độ có thể được giảm dần theo thời gian (các epoch) thay vì giữ cố định, giúp mô hình tập trung vào "dark knowledge" ở giai đoạn đầu và chuyển dần sang nhãn cứng (hard label) ở giai đoạn cuối. Công thức cập nhật nhiệt độ $\tau$ theo thời gian $t$:
$\tau(t) = \tau_{min} + (\tau_{max} - \tau_{min}) \cdot \exp(- \frac{t}{T} \ln \frac{\tau_{max}}{\tau_{min}})$.

---

### PHẦN 8: CHI TIẾT LẬP TRÌNH VÀ TRIỂN KHAI VỚI YOLO (ULTRALYTICS)

**Q: Làm thế nào để lập trình tích hợp thuật toán Knowledge Distillation vào YOLOv11 (ví dụ lấy YOLO11m làm Teacher dạy cho YOLO11n)?**
**A:** Trong framework của Ultralytics, bạn không thể thực hiện ngay qua dòng lệnh mà phải viết mã (code) kế thừa. Dưới đây là các bước triển khai thuật toán:
1.  **Kế thừa (Subclassing):** Tạo một lớp mới kế thừa từ `DetectionTrainer`.
2.  **Ghi đè quá trình truyền xuôi (Override):** Bạn cần ghi đè (override) phương thức `_do_train_epoch` hoặc ghi đè trực tiếp hàm `loss()` của mô hình (`BaseModel.loss()`) để tích hợp suy luận của Teacher vào vòng lặp huấn luyện.
3.  **Chặn lan truyền ngược (Stop Backpropagation) cho Teacher:** Vì Teacher chỉ để dự đoán, cần gọi hàm `.detach()` trên đầu ra của Teacher để chặn luồng gradient (ví dụ: `teacher_outputs = teacher_model(images).detach()`).
4.  **Tạo Adapter cho số lượng Kênh (Channel Mismatch):** Rất quan trọng! Kích thước kênh của YOLO11m và YOLO11n khác nhau. Khi tính Loss bằng MSE giữa hai feature maps, bạn **bắt buộc phải lập trình thêm một lớp Adapter/Projection nhỏ** (e.g., một lớp Convolution 1x1) để ép số chiều của Student ($f_s$) khớp với Teacher ($f_t$) trước khi tính lỗi.
5.  **Dùng Forward Pre-Hook:** Để bắt (capture) được feature map ở đầu vào của lớp `Detect` một cách "sạch" nhất mà không phải chỉnh sửa mã nguồn gốc, hãy đăng ký một `forward pre-hook` lên module `Detect` của mô hình PyTorch.

**Q: Nếu muốn tạo một hàm Loss chứa tham số có thể huấn luyện (trainable parameter) cho KD trong YOLO thì viết như thế nào?**
**A:** Bạn cần kế thừa lớp `v8DetectionLoss` (hoặc lớp Loss tương ứng của YOLO) và đăng ký tham số đó bằng `nn.Parameter` của PyTorch. Ví dụ:
`self.alpha = nn.Parameter(torch.tensor(0.5))`.
Điều này biến `alpha` thành một trọng số học được (trainable) và tự động đăng ký với bộ optimizer. Sau đó, bạn đưa Custom Loss này vào hàm `init_criterion` của custom `DetectionTrainer`.

**Q: Về mặt kiến trúc thuật toán, YOLO26 đã loại bỏ và thay đổi những gì để tối ưu mạnh mẽ cho việc triển khai (deployment) lên phần cứng Edge?**
**A:** YOLO26 thực hiện tái cấu trúc lớn ở phần hậu xử lý và tính loss:
1.  **Loại bỏ DFL (Distribution Focal Loss):** DFL dự đoán phân phối xác suất cho tọa độ bounding box giúp tăng độ chính xác nhưng lại gây ra overhead khi biên dịch mô hình (export). YOLO26 loại bỏ DFL, đưa bài toán trở về hồi quy tọa độ trực tiếp, giúp việc xuất mô hình sang ONNX, TensorRT, CoreML, TFLite "sạch" hơn và tăng tốc đáng kể.
2.  **Inference End-to-End Không NMS (NMS-free):** YOLO26 loại bỏ hoàn toàn thuật toán NMS (Non-Maximum Suppression). Kiến trúc head được thiết kế lại để xuất trực tiếp các bounding box duy nhất mà không cần dựa vào bước hậu xử lý cắt lọc trùng lặp. Việc này triệt tiêu độ trễ post-processing, giúp mô hình phiên bản "nano" nhanh hơn tới 43% trên CPU.
3.  **Thuật toán tối ưu hóa MuSGD:** Thay vì dùng SGD thuần hay AdamW, YOLO26 sử dụng MuSGD – một sự kết hợp thuật toán giữa SGD truyền thống và Muon optimizer (lấy cảm hứng từ quá trình huấn luyện LLM). Việc này cho phép mô hình hội tụ nhanh hơn, ổn định hơn trên nhiều tập dữ liệu với số epoch ít hơn.