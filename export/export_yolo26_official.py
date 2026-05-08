import os
import sys
import types
import onnx
import torch
import torch.nn as nn
from copy import deepcopy

from ultralytics import YOLO
from ultralytics.nn.modules import C2f, Detect, v10Detect
import ultralytics.utils
import ultralytics.models.yolo
import ultralytics.utils.tal as _m

sys.modules["ultralytics.yolo"] = ultralytics.models.yolo
sys.modules["ultralytics.yolo.utils"] = ultralytics.utils


def _dist2bbox(distance, anchor_points, xywh=False, dim=-1):
    lt, rb = distance.chunk(2, dim)
    x1y1 = anchor_points - lt
    x2y2 = anchor_points + rb
    return torch.cat((x1y1, x2y2), dim)


_m.dist2bbox.__code__ = _dist2bbox.__code__


class DeepStreamOutput(nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, x):
        x = x.transpose(1, 2)
        boxes = x[:, :, :4]
        scores, labels = torch.max(x[:, :, 4:], dim=-1, keepdim=True)
        return torch.cat([boxes, scores, labels.to(boxes.dtype)], dim=-1)


def forward_deepstream(self, x):
    x_detach = [xi.detach() for xi in x]
    if hasattr(self, "inference"):
        one2one = [
            torch.cat((self.one2one_cv2[i](x_detach[i]), self.one2one_cv3[i](x_detach[i])), 1) for i in range(self.nl)
        ]
        y = self.inference(one2one)
    else:
        one2one = self.forward_head(x_detach, **self.one2one)
        y = self._inference(one2one)
    return y


def yolo26_export(weights, device, fuse=True):
    model = YOLO(weights)
    model = deepcopy(model.model).to(device)
    for p in model.parameters():
        p.requires_grad = False
    model.eval()
    model.float()
    if fuse:
        model = model.fuse()
    for k, m in model.named_modules():
        if isinstance(m, (Detect, v10Detect)):
            m.dynamic = False
            m.export = True
            m.format = "onnx"
            if m.__class__.__name__ == "Detect":
                m.forward = types.MethodType(forward_deepstream, m)
        elif isinstance(m, C2f):
            m.forward = m.forward_split
    return model


def suppress_warnings():
    import warnings
    warnings.filterwarnings("ignore", category=torch.jit.TracerWarning)
    warnings.filterwarnings("ignore", category=UserWarning)
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=FutureWarning)
    warnings.filterwarnings("ignore", category=ResourceWarning)


def export_deepstream_onnx(
    weights_path: str,
    img_size_hw: tuple[int, int],
    opset: int,
    do_simplify: bool,
    do_dynamic_batch: bool,
    batch_dim: int,
    labels_txt_path: str | None,
) -> str:
    suppress_warnings()

    device = torch.device("cpu")
    inner = yolo26_export(weights_path, device)

    if labels_txt_path is not None:
        if len(inner.names.keys()) > 0:
            print(f"Writing labels → {labels_txt_path}")
            with open(labels_txt_path, "w", encoding="utf-8") as f:
                for name in inner.names.values():
                    f.write(f"{name}\n")

    model = nn.Sequential(inner, DeepStreamOutput())

    onnx_input_im = torch.zeros(batch_dim, 3, img_size_hw[0], img_size_hw[1]).to(device)
    onnx_output_file = weights_path.rsplit(".", 1)[0] + ".onnx"

    dynamic_axes = {
        "input": {0: "batch"},
        "output": {0: "batch"},
    }

    print("Exporting the model to ONNX")
    from torch.onnx import utils as torch_utils
    torch_utils._export(
        model,
        onnx_input_im,
        onnx_output_file,
        verbose=False,
        opset_version=opset,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes=dynamic_axes if do_dynamic_batch else None,
    )

    if do_simplify:
        print("Simplifying the ONNX model")
        import onnxsim

        model_onnx = onnx.load(onnx_output_file)
        model_simplified, check = onnxsim.simplify(model_onnx)
        if check:
            onnx.save(model_simplified, onnx_output_file)
        else:
            print("Simplify failed, keeping original")

    print(f"Done: {onnx_output_file}\n")
    return onnx_output_file


def main(args):
    suppress_warnings()

    print(f"\nStarting: {args.weights}")
    print("Opening YOLO26 model")

    img_size_tuple = tuple(args.size * 2 if len(args.size) == 1 else args.size)
    if len(img_size_tuple) != 2:
        raise RuntimeError("size must resolve to exactly H,W (length 2)")

    export_deepstream_onnx(
        args.weights,
        img_size_tuple,
        args.opset,
        args.simplify,
        args.dynamic,
        args.batch,
        "labels.txt",
    )


def parse_args():
    import argparse
    parser = argparse.ArgumentParser(description="DeepStream YOLO26 conversion")
    parser.add_argument("-w", "--weights", required=True, type=str, help="Input weights (.pt) file path (required)")
    parser.add_argument("-s", "--size", nargs="+", type=int, default=[640], help="Inference size [H,W] (default [640])")
    parser.add_argument("--opset", type=int, default=17, help="ONNX opset version")
    parser.add_argument("--simplify", action="store_true", help="ONNX simplify model")
    parser.add_argument("--dynamic", action="store_true", help="Dynamic batch-size")
    parser.add_argument("--batch", type=int, default=1, help="Static batch-size")
    args = parser.parse_args()
    if not os.path.isfile(args.weights):
        raise RuntimeError("Invalid weights file")
    if args.dynamic and args.batch > 1:
        raise RuntimeError("Cannot set dynamic batch-size and static batch-size at same time")
    return args


if __name__ == "__main__":
    args = parse_args()
    main(args)
