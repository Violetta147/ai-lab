# Hướng dẫn dọn dẹp và cài đặt lại Docker sang ổ D

Lỗi `The command 'docker' could not be found in this WSL 2 distro` đã tiết lộ sự thật: **Bạn đang cài Docker Desktop trên Windows, chứ không cài trực tiếp vào Kali Linux.**

Và vì Docker Desktop của bạn đã bị crash (hỏng) ở lệnh trước, cục rác 16GB đó đang bị kẹt bên trong file hệ thống ẩn của Docker Desktop trên Windows mà các lệnh thông thường không thể đụng tới được.

Cách nhanh nhất và sạch sẽ nhất bây giờ là **Factory Reset (Cài lại Docker Desktop)**. Bạn không cần dùng lệnh nữa, hãy làm theo 3 bước sau bằng chuột:

### BƯỚC 1: XÓA DOCKER DESKTOP (Lấy lại 20GB ngay lập tức)
1. Bấm nút **Start (Windows)** trên bàn phím, gõ chữ `Add or remove programs` (Thêm hoặc xóa chương trình) và nhấn Enter.
2. Tìm ứng dụng **Docker Desktop** trong danh sách.
3. Bấm **Uninstall** (Gỡ cài đặt). Quá trình này sẽ tự động báo cho Windows xóa sạch cục VHDX 16GB đang chiếm chỗ trên ổ C của bạn.
4. (Tùy chọn) Mở file Explorer, gõ `%LOCALAPPDATA%` lên thanh địa chỉ, tìm thư mục `Docker` và xóa nó đi cho sạch tận gốc.

*(Sau khi Uninstall xong, hãy mở My Computer (This PC) lên xem, ổ C của bạn chắc chắn đã lấy lại được 20GB trống!)*

### BƯỚC 2: CÀI ĐẶT LẠI DOCKER SANG Ổ D
1. Tải lại Docker Desktop (nếu bạn chưa có file cài).
2. Chạy file cài đặt, nhưng **khi nó hỏi**, hãy chắc chắn rằng bạn đánh dấu tích vào ô **"Use WSL 2 instead of Hyper-V"**.
3. Sau khi cài xong và mở Docker Desktop lên, **đừng chạy code vội!** 
4. Bấm vào icon **Bánh răng (Settings)** ở góc phải trên cùng của Docker Desktop.
5. Vào mục **Resources > Advanced**. Ở phần **Disk image location**, chọn nút **Browse** và trỏ nó sang thư mục trên ổ D (Ví dụ: `D:\DockerData`).
6. **RẤT QUAN TRỌNG:** Vào mục **Resources > WSL Integration**. Bật công tắc gạt (ON) cho **`kali-linux`**. (Đó chính là cái distro integration mà bạn từng thấy đó!).
7. Bấm **Apply & restart**.

### BƯỚC 3: BUILD LẠI PROJECT
Bây giờ Docker của bạn đã có một ngôi nhà mới siêu rộng rãi trên ổ D. Bạn chỉ cần mở lại PowerShell và chạy:

```powershell
cd D:\datas\Final.yolov8\data_pipeline\pipeline
docker-compose build
docker-compose up -d
```
(Lưu ý file `docker-compose.yml` mình đã tối ưu, nên giờ nó chỉ build 1 lần duy nhất thay vì 3 lần, cực kỳ nhanh).
