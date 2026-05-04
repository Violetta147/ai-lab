"""
Batch-run ONNX models with the same postprocess as test_onnx_official.py.

Per model: sample N images from a dataset folder, print TICK or X.
  X  → runtime error, label out of range for expected class count, or too many boxes
  TICK → otherwise

Example:
  python test_onnx_batch_official.py --images-root datasets/work3yolov8 --sample 3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

_REPO = Path(__file__).resolve().parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from test_onnx_official import run_onnx_on_bgr  # noqa: E402


def draw_result_on_image(img_bgr: np.ndarray, result: dict, label_prefix: str) -> np.ndarray:
    out = img_bgr.copy()
    indices = np.asarray(result.get("indices_flat", []), dtype=np.int64).flatten()
    if indices.size == 0:
        return out

    boxes_xyxy = result["boxes_xyxy"]
    scores = result["scores"]
    labels = result["labels"]
    ratio = float(result["ratio"])
    dw = float(result["dw"])
    dh = float(result["dh"])
    h0, w0 = out.shape[:2]

    for i in indices:
        x1, y1, x2, y2 = boxes_xyxy[i]
        score = float(scores[i])
        label = int(labels[i])

        # Undo letterbox scale to original image space
        x1 = (x1 - dw) / ratio
        y1 = (y1 - dh) / ratio
        x2 = (x2 - dw) / ratio
        y2 = (y2 - dh) / ratio

        x1 = max(0, min(int(x1), w0))
        y1 = max(0, min(int(y1), h0))
        x2 = max(0, min(int(x2), w0))
        y2 = max(0, min(int(y2), h0))

        color = (0, 255, 0)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        text = f"{label_prefix} cls{label} {score:.2f}"
        cv2.putText(out, text, (x1, max(y1 - 5, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    return out


def default_onnx_list(repo: Path) -> list[Path]:
    m = repo / "models"
    weights = [
        m / "yolo-prune_archive_200_epochs/runs/detect/fine-tuning2/weights/best.onnx",
        m / "yolo-prune_archive_50epochs/runs/detect/fine-tuning/weights/best.onnx",
        m / "yolo-prune_archive_1_33/runs/detect/fine-tuning/weights/best.onnx",
        m / "yolo-prune_archive_1_25/runs/detect/fine-tuning2/weights/best.onnx",
        m / "YOLO26n_Pruned_v2_Final/weights/best.onnx",
        m / "yolo-prune_archive_1_2_fixed_labels/runs/detect/fine-tuning/weights/best.onnx",
        m / "yolo_all_exports_p2n/content/yolo-prune/runs/detect/yolo26_p2_train/base_model/weights/best.onnx",
        m / "yolo_all_exports_p2n/content/yolo-prune_archive/runs/detect/yolo26_p2_train/base_model/weights/best.onnx",
        m / "yolo_all_exports_p2n/content/runs/detect/yolo26_p2_train/base_model/weights/best.onnx",
        m / "yolo_all_exports_p2n/content/pruned_model_lamp.onnx",
        m / "yolo_all_exports_p2n/content/yolo26n-p2.onnx",
        m / "yolo_all_exports_p2n/content/fine-tuning2/weights/best.onnx",
    ]
    return [p.resolve() for p in weights]


def infer_nc_from_sidecar_labels(onnx_path: Path) -> int | None:
    """
    Matches batch export naming: `{weights_stem}_labels.txt`; ONNX stem equals weights stem.
    """
    candidate = onnx_path.parent / f"{onnx_path.stem}_labels.txt"
    if not candidate.is_file():
        return None
    lines = [
        ln
        for ln in candidate.read_text(encoding="utf-8").splitlines()
        if ln.strip() != ""
    ]
    return len(lines)


def collect_val_images(images_root: Path, limit: int) -> list[Path]:
    sub = images_root
    for cand in ("images/val", "val/images", "images/train", "train/images"):
        p = images_root / cand
        if p.is_dir():
            sub = p
            break
    exts = {".jpg", ".jpeg", ".png", ".bmp"}
    found: list[Path] = []
    for pat in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        for f in sorted(sub.glob(pat)):
            if f.suffix.lower() in exts:
                found.append(f)
            if len(found) >= limit:
                return found
    for f in sorted(sub.rglob("*")):
        if f.is_file() and f.suffix.lower() in exts:
            found.append(f)
        if len(found) >= limit:
            break
    return found


def evaluate_onnx(
    onnx_path: Path,
    image_paths: list[Path],
    conf_thresh: float,
    iou_thresh: float,
    imgsz: int,
    max_nms_boxes: int,
    max_raw_boxes: int,
    expect_num_classes: int | None,
    save_vis: bool,
    vis_max_per_model: int,
) -> tuple[bool, str]:
    if not onnx_path.is_file():
        return False, "missing onnx"

    try:
        sess = ort.InferenceSession(str(onnx_path))
    except Exception as exc:
        return False, f"load error: {exc}"

    worst_raw = 0
    worst_nms = 0
    worst_label = -1

    saved_vis = 0
    for im_p in image_paths:
        bgr = cv2.imread(str(im_p))
        if bgr is None:
            return False, f"bad image {im_p}"
        res = run_onnx_on_bgr(sess, bgr, conf_thresh, iou_thresh, imgsz)
        worst_raw = max(worst_raw, res["raw_n"])
        worst_nms = max(worst_nms, res["nms_n"])
        if res["max_label"] is not None:
            worst_label = max(worst_label, res["max_label"])
        if expect_num_classes is not None and res["max_label"] is not None:
            if res["max_label"] > expect_num_classes - 1:
                return (
                    False,
                    f"label {res['max_label']} out of range for nc={expect_num_classes}",
                )
        if res["raw_n"] > max_raw_boxes:
            return False, f"raw boxes {res['raw_n']} > {max_raw_boxes}"
        if res["nms_n"] > max_nms_boxes:
            return False, f"nms boxes {res['nms_n']} > {max_nms_boxes} (too many boxes)"
        if save_vis and saved_vis < vis_max_per_model:
            model_dir = onnx_path.parent
            model_dir.mkdir(parents=True, exist_ok=True)
            drawn = draw_result_on_image(bgr, res, onnx_path.stem)
            out_name = f"{onnx_path.stem}__{im_p.stem}__nms{res['nms_n']}.jpg"
            out_file = model_dir / out_name
            cv2.imwrite(str(out_file), drawn)
            saved_vis += 1

    detail = f"raw_max={worst_raw} nms_max={worst_nms} label_max={worst_label}"
    return True, detail


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Batch ONNX smoke test (TICK/X)")
    p.add_argument(
        "--images-root",
        type=Path,
        help="Dataset root (searches images/val, val/images, ...)",
        default=_REPO / "datasets" / "work3yolov8",
    )
    p.add_argument("--sample", type=int, help="Max images per ONNX", default=5)
    p.add_argument("--conf", type=float, help="Confidence threshold", default=0.25)
    p.add_argument("--iou", type=float, help="IoU for NMS", default=0.45)
    p.add_argument("--imgsz", type=int, help="Letterbox size", default=640)
    p.add_argument(
        "--max-nms",
        type=int,
        help="Fail (X) if any image exceeds this many boxes after NMS",
        default=40,
    )
    p.add_argument(
        "--max-raw",
        type=int,
        help="Fail (X) if raw grid count before conf filter exceeds this",
        default=50000,
    )
    p.add_argument(
        "--expect-nc",
        type=int,
        help="Fail when label > nc-1. If omitted, tries `{stem}_labels.txt` beside each ONNX.",
        default=None,
    )
    p.add_argument(
        "--onnx",
        type=Path,
        nargs="*",
        help="Explicit ONNX paths (default: batch list beside each best.pt)",
        default=None,
    )
    p.add_argument(
        "--save-vis",
        action="store_true",
        help="Save prediction visualization images (bbox) for each ONNX model",
    )
    p.add_argument(
        "--vis-out",
        type=Path,
        help="Deprecated: ignored. Visualizations are saved beside each ONNX model.",
        default=_REPO / "runs" / "onnx_batch_vis",
    )
    p.add_argument(
        "--vis-max-per-model",
        type=int,
        help="Max number of visualized images to save per ONNX model",
        default=5,
    )
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    repo = _REPO

    images_root = ns.images_root.resolve()
    image_paths = collect_val_images(images_root, ns.sample)
    if not image_paths:
        print(
            "ERROR: No images under",
            images_root,
            "— run scripts/fetch_hub_work3_dataset.py first or pass --images-root.",
            file=sys.stderr,
        )
        return 1

    onnx_list = [p.resolve() for p in ns.onnx] if ns.onnx else default_onnx_list(repo)

    print("Images:", len(image_paths), "from", images_root)
    for im in image_paths:
        print("  ", im)

    print("\n" + "-" * 88)
    print(f"{'RESULT':6}  {'ONNX'}")
    print("-" * 88)

    for onnx_p in onnx_list:
        if ns.expect_nc is not None:
            expect_nc_use = ns.expect_nc
            nc_kind = "explicit"
        else:
            inferred = infer_nc_from_sidecar_labels(onnx_p)
            expect_nc_use = inferred
            nc_kind = "labels_txt" if inferred is not None else ""

        ok, msg = evaluate_onnx(
            onnx_p,
            image_paths,
            ns.conf,
            ns.iou,
            ns.imgsz,
            ns.max_nms,
            ns.max_raw,
            expect_nc_use,
            ns.save_vis,
            ns.vis_max_per_model,
        )
        mark = "TICK" if ok else "X"
        try:
            rel = onnx_p.relative_to(repo)
        except ValueError:
            rel = onnx_p
        nc_hint = ""
        if expect_nc_use is not None:
            nc_hint = f" nc={expect_nc_use}({nc_kind})"
        print(f"{mark:6}  {rel}  |{nc_hint} {msg}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
