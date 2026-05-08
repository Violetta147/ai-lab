"""
Batch YOLO26 → ONNX for DeepStream, aligned with upstream:

  https://github.com/marcoslucianops/DeepStream-Yolo/blob/master/utils/export_yolo26.py

  - ONNX: ``torch.onnx.export`` (**--modern-onnx-export**) or legacy ``torch_utils._export``
    (auto when ``--opset`` ≤12 — avoids PyTorch ONNX down-convert failures).
  - Simplify: **onnxslim** if installed, else **onnxsim**.

Reuse `yolo26_export` / `DeepStreamOutput` from local `export_yolo26_official.py`.

Registers pickled `prune_module.*` checkpoints. Prints pre-export fused metrics (--inspect-only).
Writes labels next to each weight: `{stem}_labels.txt`
"""

from __future__ import annotations

import io
import os
import sys
from copy import deepcopy
from pathlib import Path

import onnx
import torch
import torch.nn as nn

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXPORT_DIR = Path(__file__).resolve().parent
if str(_EXPORT_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPORT_DIR))

import prune_module  # noqa: E402

sys.modules.setdefault("prune_module", prune_module)

from export_yolo26_official import (  # noqa: E402
    DeepStreamOutput,
    suppress_warnings,
    yolo26_export,
)
from ultralytics import YOLO  # noqa: E402


def default_weight_paths(repo_root: Path) -> list[Path]:
    m = repo_root / "models"
    rels = [
        m / "yolo-prune_archive_200_epochs/runs/detect/fine-tuning2/weights/best.pt",
        m / "yolo-prune_archive_50epochs/runs/detect/fine-tuning/weights/best.pt",
        m / "yolo-prune_archive_1_33/runs/detect/fine-tuning/weights/best.pt",
        m / "yolo-prune_archive_1_25/runs/detect/fine-tuning2/weights/best.pt",
        m / "YOLO26n_Pruned_v2_Final/weights/best.pt",
        m / "yolo-prune_archive_1_2_fixed_labels/runs/detect/fine-tuning/weights/best.pt",
        m / "yolo_all_exports_p2n/content/yolo-prune/runs/detect/yolo26_p2_train/base_model/weights/best.pt",
        m / "yolo_all_exports_p2n/content/yolo-prune_archive/runs/detect/yolo26_p2_train/base_model/weights/best.pt",
        m / "yolo_all_exports_p2n/content/runs/detect/yolo26_p2_train/base_model/weights/best.pt",
        m / "yolo_all_exports_p2n/content/pruned_model_lamp.pt",
        m / "yolo_all_exports_p2n/content/yolo26n-p2.pt",
        m / "yolo_all_exports_p2n/content/fine-tuning2/weights/best.pt",
    ]
    return [p.resolve() for p in rels]


def print_pre_export_metrics(weights_path: str, imgsz: int) -> None:
    """
    Mirrors export_yolo26_official fuse=True inference: fused model on CPU then
    torch_utils.model_info (params/FLOPs). Falls back if fuse fails on odd checkpoints.
    """
    print("\n" + "=" * 72)
    print("Pre-export metrics (target fuse like ONNX path):", weights_path)
    print("=" * 72)

    import torch as _torch
    from ultralytics.utils import torch_utils

    yo = YOLO(weights_path)
    names = dict(yo.names)
    backbone = getattr(yo.model, "model", yo.model)
    last_layer = backbone[-1] if backbone is not None else None
    nc_val = getattr(last_layer, "nc", "?")

    inner = deepcopy(yo.model).to(_torch.device("cpu"))
    inner.eval()
    inner.float()
    fused_ok = True
    try:
        inner = inner.fuse()
    except Exception as exc:
        fused_ok = False
        print(f"WARNING fuse() failed ({type(exc).__name__}: {exc}); metrics below may be unfused.")

    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        torch_utils.model_info(inner, detailed=True, verbose=True, imgsz=imgsz)
    finally:
        sys.stdout = old_stdout
    txt = buf.getvalue()
    if txt.strip():
        print(txt, end="")
    else:
        npar = sum(p.numel() for p in inner.parameters())
        print(f"(model_info empty) parameters={npar:,} fused_attempted={fused_ok}")

    npar_final = sum(p.numel() for p in inner.parameters())
    print("--- summary ---")
    print("classes (names):", names)
    print("nc:", nc_val)
    print("parameter_count:", f"{npar_final:,}")
    print("(FLOPs / GFLOPs in block above when model_info printed successfully)")


def infer_size_hw(size_arg: list[int]) -> tuple[int, int]:
    tup = tuple(size_arg * 2 if len(size_arg) == 1 else size_arg)
    if len(tup) != 2:
        raise RuntimeError("size must be one int [S] or two ints [H, W]")
    return int(tup[0]), int(tup[1])


def export_onnx_github_style(
    weights_path: str,
    img_size_hw: tuple[int, int],
    opset: int,
    do_simplify: bool,
    do_dynamic_batch: bool,
    batch_dim: int,
    labels_txt_path: str | None,
    use_modern_torch_onnx_export: bool,
) -> str:
    """DeepStream‑Yolo ONNX: modern ``torch.onnx.export`` or legacy traced ``_export``."""

    suppress_warnings()

    device = torch.device("cpu")
    inner = yolo26_export(weights_path, device)

    if labels_txt_path is not None:
        name_map = getattr(inner, "names", None)
        if name_map is not None and len(name_map.keys()) > 0:
            print(f"Writing labels → {labels_txt_path}")
            with open(labels_txt_path, "w", encoding="utf-8") as fhandle:
                for name in inner.names.values():
                    fhandle.write(f"{name}\n")

    sequential = nn.Sequential(inner, DeepStreamOutput())

    onnx_input_im = torch.zeros(batch_dim, 3, img_size_hw[0], img_size_hw[1]).to(device)
    onnx_output_file = weights_path.rsplit(".", 1)[0] + ".onnx"

    dynamic_axes = {"input": {0: "batch"}, "output": {0: "batch"}}
    dyn_arg = dynamic_axes if do_dynamic_batch else None

    if use_modern_torch_onnx_export:
        print(
            "Exporting ONNX (torch.onnx.export — upstream export_yolo26.py; "
            "needs opset compatible with your PyTorch exporter)"
        )
        torch.onnx.export(
            sequential,
            onnx_input_im,
            onnx_output_file,
            verbose=False,
            opset_version=opset,
            do_constant_folding=True,
            input_names=["input"],
            output_names=["output"],
            dynamic_axes=dyn_arg,
        )
    else:
        print(
            "Export ONNX (legacy torch.onnx.utils._export — TorchScript tracer, "
            f"recommended for opset={opset} on newer PyTorch / DeepStream 6.0)"
        )
        from torch.onnx import utils as torch_utils

        torch_utils._export(
            sequential,
            onnx_input_im,
            onnx_output_file,
            verbose=False,
            opset_version=opset,
            do_constant_folding=True,
            input_names=["input"],
            output_names=["output"],
            dynamic_axes=dyn_arg,
        )

    if do_simplify:
        model_onnx = onnx.load(onnx_output_file)
        used_onnxslim = False
        try:
            import onnxslim

            model_onnx = onnxslim.slim(model_onnx)
            used_onnxslim = True
            print("Simplified with onnxslim (DeepStream‑Yolo upstream)")
        except ImportError:
            try:
                import onnxsim
            except ImportError as exc2:
                raise RuntimeError(
                    "Install onnxslim (preferred): pip install onnxslim\n"
                    "or onnxsim: pip install onnxsim"
                ) from exc2
            model_simp, simp_ok = onnxsim.simplify(model_onnx)
            if not simp_ok:
                raise RuntimeError("onnxsim.simplify failed (check=False)")
            model_onnx = model_simp
            print("onnxslim not installed; simplified with onnxsim instead")

        onnx.save(model_onnx, onnx_output_file)

    print(f"Done: {onnx_output_file}\n")
    return onnx_output_file


def resolve_use_modern_onnx(force_modern: bool, force_legacy: bool, opset_val: int) -> bool:
    """Use ``torch.onnx.export`` (modern) vs ``torch_utils._export`` (legacy traced)."""
    if force_modern and force_legacy:
        raise RuntimeError("cannot combine --modern-onnx-export and --legacy-onnx-export")
    if force_modern:
        return True
    if force_legacy:
        return False
    return opset_val > 12


def run_one(
    weights_path: Path,
    img_size_hw: tuple[int, int],
    model_info_imgsz: int,
    opset: int,
    do_simplify: bool,
    do_dynamic: bool,
    batch_dim: int,
    use_modern_onnx_export: bool,
) -> str | None:
    w = str(weights_path)
    if not weights_path.is_file():
        print("SKIP missing file:", w)
        return None

    print_pre_export_metrics(w, model_info_imgsz)

    stem = weights_path.stem
    labels_path = str(weights_path.parent / f"{stem}_labels.txt")

    onnx_path = export_onnx_github_style(
        w,
        img_size_hw,
        opset,
        do_simplify,
        do_dynamic,
        batch_dim,
        labels_path,
        use_modern_onnx_export,
    )
    return onnx_path


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Batch YOLO26 → DeepStream ONNX (upstream export_yolo26.py parity)")
    parser.add_argument(
        "-s",
        "--size",
        nargs="+",
        type=int,
        default=[640],
        help="Inference size [H,W] or single int [S]→[S,S] (default [640])",
    )
    parser.add_argument("--opset", type=int, help="ONNX opset version", default=17)
    parser.add_argument(
        "--simplify",
        action="store_true",
        help="ONNX simplify via onnxslim (same as DeepStream-Yolo export_yolo26.py)",
    )
    parser.add_argument("--dynamic", action="store_true", help="Dynamic batch-size (input/output axis 0)")
    parser.add_argument("--batch", type=int, help="Static batch when not --dynamic", default=1)
    parser.add_argument(
        "--modern-onnx-export",
        action="store_true",
        help="Force torch.onnx.export (upstream); else opset≤12 defaults to legacy torch_utils._export",
    )
    parser.add_argument(
        "--legacy-onnx-export",
        action="store_true",
        help="Force legacy torch_utils._export (TorchScript ONNX path)",
    )
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="Only print fused params/FLOPs/nc/names per checkpoint; skip ONNX export",
    )
    ns = parser.parse_args()

    if ns.dynamic and ns.batch > 1:
        raise RuntimeError("Cannot set dynamic batch-size and static batch-size at same time")

    img_hw = infer_size_hw(list(ns.size))
    model_info_imgsz = img_hw[0] if img_hw[0] == img_hw[1] else max(img_hw)
    use_modern = resolve_use_modern_onnx(
        ns.modern_onnx_export,
        ns.legacy_onnx_export,
        ns.opset,
    )

    paths = default_weight_paths(_REPO_ROOT)

    if ns.inspect_only:
        print("Inspect only (no ONNX). Weights:", len(paths))
        for p in paths:
            w = str(p)
            if not p.is_file():
                print("SKIP missing:", w)
                continue
            print_pre_export_metrics(w, model_info_imgsz)
        return 0

    print("Planned exports:", len(paths))
    print("ONNX backend:", "torch.onnx.export" if use_modern else "torch.onnx.utils._export (legacy)")
    for p in paths:
        run_one(
            p,
            img_hw,
            model_info_imgsz,
            ns.opset,
            ns.simplify,
            ns.dynamic,
            ns.batch,
            use_modern,
        )
    return 0


if __name__ == "__main__":
    os.chdir(_REPO_ROOT)
    raise SystemExit(main())
