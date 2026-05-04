import os
from pathlib import Path

# Thư mục chứa labels cần kiểm tra
LABEL_DIR = r"d:\datas\Final.yolov8\models\yolo-prune_archive_1_33\datasets\work3yolov8\labels"

def check_and_fix_duplicate_labels(label_dir, fix=False):
    label_path = Path(label_dir)
    if not label_path.exists():
        print(f"❌ Không tìm thấy thư mục: {label_dir}")
        return

    txt_files = list(label_path.rglob("*.txt"))
    total_files = len(txt_files)
    files_with_duplicates = 0
    total_duplicates = 0

    print(f"🔍 Đang quét {total_files} file labels...")

    for file_path in txt_files:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # Bỏ qua dòng trống và khoảng trắng thừa
        lines_cleaned = [line.strip() for line in lines if line.strip()]
        
        # Tìm duplicates
        unique_lines = list(dict.fromkeys(lines_cleaned)) # Dùng dict để giữ nguyên thứ tự
        num_duplicates = len(lines_cleaned) - len(unique_lines)

        if num_duplicates > 0:
            files_with_duplicates += 1
            total_duplicates += num_duplicates
            print(f"⚠️ Phát hiện {num_duplicates} duplicate(s) trong file: {file_path.name}")
            
            # Nếu bật chế độ fix, sẽ ghi đè file với dữ liệu đã lọc
            if fix:
                with open(file_path, "w", encoding="utf-8") as f:
                    for line in unique_lines:
                        f.write(line + "\n")
                print(f"  ✅ Đã fix: {file_path.name}")

    print("\n" + "="*40)
    print("📊 TỔNG KẾT:")
    print(f"Tổng số file đã quét: {total_files}")
    print(f"Số file bị lỗi duplicate: {files_with_duplicates}")
    print(f"Tổng số label bị trùng lặp: {total_duplicates}")
    
    if fix and files_with_duplicates > 0:
        print("✨ Tất cả các lỗi duplicate đã được sửa (xóa dòng trùng)!")
    elif not fix and files_with_duplicates > 0:
        print("💡 CẢNH BÁO: Đang chạy ở chế độ CHỈ KIỂM TRA (dry-run).")
        print("   Để tự động sửa lỗi, hãy đổi tham số `fix=True` trong code.")
    elif files_with_duplicates == 0:
        print("🎉 Tuyệt vời! Dataset hoàn toàn sạch, không có duplicate label.")

if __name__ == "__main__":
    # Chỉ kiểm tra trước (đổi True để sửa)
    check_and_fix_duplicate_labels(LABEL_DIR, fix=False)
