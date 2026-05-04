# Baselines

Thư mục này dùng để lưu và so sánh các baseline hiệu năng.

## Cấu trúc
- runs/    : kết quả chạy theo từng lần test
- engines/ : các file `.engine` dùng để test
- configs/ : lệnh và cấu hình test (trtexec, app, camera)
- notes/   : ghi chú phân tích, so sánh
- logs/    : log thô của các lần chạy

## Quy ước đặt tên
- engine: `<model>_<prec>_<shape>_<date>.engine`
- run: `<date>_<mode>_<model>_<prec>.txt`
  - mode: `gpu` (thuần GPU), `e2e` (camera end-to-end)

## Mẫu thao tác nhanh
1) Lưu engine vào `engines/`
2) Lưu lệnh test vào `configs/`
3) Lưu log vào `logs/`
4) Tóm tắt kết quả vào `runs/` hoặc `notes/`
