import argparse
import io
import json
import pathlib
import sys
from typing import List, Dict, Tuple

import numpy as np
import requests
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def load_ndjson(ndjson_path: pathlib.Path) -> List[Dict]:
    """Read a NDJSON file."""
    items = []
    with ndjson_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items

def parse_boxes(entry: Dict) -> List[Dict]:
    """Convert YOLO normalised boxes to absolute pixel coordinates."""
    w, h = entry["width"], entry["height"]
    boxes = []
    for ann in entry.get("annotations", {}).get("boxes", []):
        cls, cx, cy, bw, bh = ann
        x_center = cx * w
        y_center = cy * h
        box_w = bw * w
        box_h = bh * h
        x1 = int(x_center - box_w / 2)
        y1 = int(y_center - box_h / 2)
        x2 = int(x_center + box_w / 2)
        y2 = int(y_center + box_h / 2)
        boxes.append({"class": int(cls), "x1": x1, "y1": y1, "x2": x2, "y2": y2})
    return boxes

def iou(box_a: Tuple[int, int, int, int], box_b: Tuple[int, int, int, int]) -> float:
    xa1, ya1, xa2, ya2 = box_a
    xb1, yb1, xb2, yb2 = box_b
    inter_x1 = max(xa1, xb1)
    inter_y1 = max(ya1, yb1)
    inter_x2 = min(xa2, xb2)
    inter_y2 = min(ya2, yb2)
    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    area_a = (xa2 - xa1) * (ya2 - ya1)
    area_b = (xb2 - xb1) * (yb2 - yb1)
    union = area_a + area_b - inter_area
    return inter_area / union if union > 0 else 0.0

def containment_ratio(big: Tuple[int, int, int, int], small: Tuple[int, int, int, int]) -> float:
    """How much of the SMALL box is inside the BIG box?
    Returns intersection_area / small_area.
    1.0 = small box is fully contained inside big box.
    0.0 = no overlap at all.
    """
    xb1, yb1, xb2, yb2 = big
    xs1, ys1, xs2, ys2 = small
    # Compute the actual geometric intersection
    inter_x1 = max(xb1, xs1)
    inter_y1 = max(yb1, ys1)
    inter_x2 = min(xb2, xs2)
    inter_y2 = min(yb2, ys2)
    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    area_small = (xs2 - xs1) * (ys2 - ys1)
    return inter_area / area_small if area_small > 0 else 0.0

def center_distance(box_a: Tuple[int, int, int, int], box_b: Tuple[int, int, int, int]) -> float:
    xa1, ya1, xa2, ya2 = box_a
    xb1, yb1, xb2, yb2 = box_b
    ca_x = (xa1 + xa2) / 2.0
    ca_y = (ya1 + ya2) / 2.0
    cb_x = (xb1 + xb2) / 2.0
    cb_y = (yb1 + yb2) / 2.0
    return np.hypot(ca_x - cb_x, ca_y - cb_y)

# ---------------------------------------------------------------------------
# Duplicate detection logic (returns pairs and reasons)
# ---------------------------------------------------------------------------

def find_duplicate_pairs(
    boxes: List[Dict],
    iou_thr: float = 0.9,
    contain_thr: float = 0.8,
    center_dist_px: float = 5.0,
    size_diff_ratio: float = 0.05,
) -> List[Dict]:
    """Return pairs of box indices that are considered duplicates, with the reason."""
    duplicate_pairs = []
    n = len(boxes)
    for i in range(n):
        a = boxes[i]
        a_box = (a["x1"], a["y1"], a["x2"], a["y2"])
        for j in range(i + 1, n):
            b = boxes[j]
            if a["class"] != b["class"]:
                continue
            b_box = (b["x1"], b["y1"], b["x2"], b["y2"])
            
            # 1️⃣ IoU overlap
            iou_val = iou(a_box, b_box)
            if iou_val >= iou_thr:
                duplicate_pairs.append({"pair": (i, j), "reason": f"IoU={iou_val:.2f}"})
                continue
                
            # 2️⃣ Containment (big contains small)
            area_a = (a["x2"] - a["x1"]) * (a["y2"] - a["y1"])
            area_b = (b["x2"] - b["x1"]) * (b["y2"] - b["y1"])
            if area_a >= area_b:
                big_box, small_box = a_box, b_box
            else:
                big_box, small_box = b_box, a_box
            
            contain_val = containment_ratio(big_box, small_box)
            if contain_val >= contain_thr:
                duplicate_pairs.append({"pair": (i, j), "reason": f"Containment={contain_val:.2f}"})
                continue
                
            # 3️⃣ Tiny shift / size diff
            c_dist = center_distance(a_box, b_box)
            s_diff = abs(area_a - area_b) / max(area_a, area_b) if max(area_a, area_b) > 0 else 0
            if c_dist <= center_dist_px and s_diff <= size_diff_ratio:
                duplicate_pairs.append({"pair": (i, j), "reason": f"Shift (dist={c_dist:.1f}px, diff={s_diff:.2%})"})

    return duplicate_pairs

# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def main(ndjson_path: pathlib.Path, out_img_dir: pathlib.Path, limit: int = 10):
    if not ndjson_path.is_file():
        print(f"Error: NDJSON file not found at {ndjson_path}")
        sys.exit(1)

    out_img_dir.mkdir(parents=True, exist_ok=True)
    print(f"Loading entries from {ndjson_path}...")
    entries = load_ndjson(ndjson_path)
    
    entries = [e for e in entries if e.get("type") == "image"]
    print(f"Found {len(entries)} image annotation entries.")

    images_processed = 0

    for entry in entries:
        if images_processed >= limit:
            break
            
        boxes = parse_boxes(entry)
        if len(boxes) < 2:
            continue
            
        pairs = find_duplicate_pairs(
            boxes,
            iou_thr=0.9,
            contain_thr=0.8,
            center_dist_px=5.0,
            size_diff_ratio=0.05,
        )
        
        if not pairs:
            continue
            
        images_processed += 1
        img_name = entry.get("file", "unknown.jpg")
        img_url = entry.get("url")
        
        print(f"\n[{images_processed}/{limit}] Image: {img_name}")
        
        # Print detected duplicate pairs
        for p in pairs:
            idx1, idx2 = p["pair"]
            b1, b2 = boxes[idx1], boxes[idx2]
            print(f"  - Detected: {p['reason']}")
            print(f"    Box 1: class {b1['class']} {b1['x1']},{b1['y1']},{b1['x2']},{b1['y2']}")
            print(f"    Box 2: class {b2['class']} {b2['x1']},{b2['y1']},{b2['x2']},{b2['y2']}")
            
        # Download and draw
        if img_url:
            try:
                resp = requests.get(img_url, stream=True, timeout=15)
                resp.raise_for_status()
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                draw = ImageDraw.Draw(img)
                
                # Draw boxes
                drawn_indices = set()
                for p in pairs:
                    idx1, idx2 = p["pair"]
                    for idx, color in [(idx1, "red"), (idx2, "orange")]:
                        if idx not in drawn_indices:
                            b = boxes[idx]
                            draw.rectangle([b["x1"], b["y1"], b["x2"], b["y2"]], outline=color, width=3)
                            drawn_indices.add(idx)
                            
                save_path = out_img_dir / img_name
                img.save(save_path)
                print(f"  OK Saved annotated image to: {save_path}")
            except Exception as e:
                print(f"  ERROR downloading image: {e}")

    print(f"\nProcessed {images_processed} demo images containing duplicates.")
    print(f"Check the directory: {out_img_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download and draw duplicate boxes from Ultralytics.")
    parser.add_argument("--ndjson", default=r"d:\datas\Final.yolov8\scratch\work3yolov8.ndjson")
    parser.add_argument("--out-dir", default=r"d:\datas\Final.yolov8\scratch\duplicate_images")
    parser.add_argument("--limit", type=int, default=10, help="Max images to download and annotate.")
    args = parser.parse_args()
    main(
        ndjson_path=pathlib.Path(args.ndjson).resolve(),
        out_img_dir=pathlib.Path(args.out_dir).resolve(),
        limit=args.limit
    )
