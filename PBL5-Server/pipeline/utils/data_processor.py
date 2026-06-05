import os
import zipfile
from ..config import YOLO_CLASSES


class DataProcessor:
    @staticmethod
    def parse_yolo_to_cvat(txt_content: str, frame_idx: int,
                           label_map: dict, img_size: tuple) -> list:
        """Chuyển đổi nội dung 1 file YOLO txt sang danh sách shape của CVAT.

        Args:
            txt_content: Nội dung file .txt YOLO format.
            frame_idx: Index của frame trong task CVAT.
            label_map: Dict mapping {label_name: cvat_label_id}.
            img_size: Tuple (width, height) của ảnh.

        Returns:
            List các shape dict tương thích CVAT API.
        """
        shapes = []
        w, h = img_size

        if w <= 0 or h <= 0:
            print(f"⚠️ [DataProcessor] Invalid image size: {img_size}")
            return shapes

        # Tạo map từ YOLO class index → CVAT label ID
        idx_to_id = {}
        for idx, name in enumerate(YOLO_CLASSES):
            if name in label_map:
                idx_to_id[idx] = label_map[name]

        if not txt_content or not txt_content.strip():
            return shapes

        for line_num, line in enumerate(txt_content.strip().split('\n'), start=1):
            parts = line.strip().split()
            if len(parts) < 5:
                continue

            try:
                cid = int(parts[0])
                if cid not in idx_to_id:
                    continue

                x, y, bw, bh = map(float, parts[1:5])

                # Validate normalized coordinates (phải trong khoảng [0, 1])
                if not all(0.0 <= v <= 1.0 for v in (x, y, bw, bh)):
                    print(f"⚠️ [DataProcessor] Line {line_num}: coordinates out of [0,1] range, skipping")
                    continue

                # Chuyển từ normalized center x,y sang absolute x1,y1,x2,y2
                x1 = (x - bw / 2) * w
                y1 = (y - bh / 2) * h
                x2 = (x + bw / 2) * w
                y2 = (y + bh / 2) * h

                # Clamp vào trong biên ảnh
                x1 = max(0, min(int(x1), w))
                y1 = max(0, min(int(y1), h))
                x2 = max(0, min(int(x2), w))
                y2 = max(0, min(int(y2), h))

                # Skip nếu bounding box bị suy biến (diện tích = 0)
                if x1 >= x2 or y1 >= y2:
                    continue

                shapes.append({
                    "type": "rectangle",
                    "label_id": idx_to_id[cid],
                    "points": [x1, y1, x2, y2],
                    "frame": frame_idx,
                    "occluded": False,
                    "outside": False,
                    "attributes": [],
                })
            except (ValueError, IndexError) as e:
                print(f"⚠️ [DataProcessor] Line {line_num}: parse error: {e}")
                continue
        return shapes

    @staticmethod
    def create_zip(file_paths: list, output_zip: str):
        """Gộp các file vào một file zip.

        Args:
            file_paths: Danh sách đường dẫn file cần nén.
            output_zip: Đường dẫn file zip đầu ra.
        """
        added = 0
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as z:
            for fpath in file_paths:
                if os.path.exists(fpath):
                    z.write(fpath, os.path.basename(fpath))
                    added += 1
                else:
                    print(f"⚠️ [DataProcessor] File not found, skipping: {fpath}")

        if added == 0:
            print("⚠️ [DataProcessor] Warning: Created empty zip file!")
