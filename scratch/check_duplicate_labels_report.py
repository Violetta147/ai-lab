import pathlib, sys

LABEL_DIR = r"d:\datas\Final.yolov8\models\yolo-prune_archive_1_33\datasets\work3yolov8\labels"
path = pathlib.Path(LABEL_DIR)
if not path.exists():
    print(f"❌ Không tìm thấy thư mục: {LABEL_DIR}")
    sys.exit(0)

files = list(path.rglob('*.txt'))
print(f"🔍 Đang quét {len(files)} file label...")
files_with_dup = 0
total_dup = 0
for f in files:
    with open(f, 'r', encoding='utf-8') as fp:
        lines = [l.strip() for l in fp if l.strip()]
    unique = list(dict.fromkeys(lines))
    dup = len(lines) - len(unique)
    if dup:
        files_with_dup += 1
        total_dup += dup
        print(f"⚠️ {f.name}: {dup} duplicate line(s)")

print("\n=== Summary ===")
print(f"Tổng file được quét: {len(files)}")
print(f"File có duplicate: {files_with_dup}")
print(f"Tổng số dòng duplicate: {total_dup}")
