from models import TRTModule  # isort:skip
import argparse
from pathlib import Path
import time

import cv2
import torch

from config import CLASSES_DET, COLORS
from models.torch_utils import det_postprocess
from models.utils import blob, letterbox, path_to_list


def maybe_sync(device: torch.device) -> None:
    if device.type == 'cuda':
        torch.cuda.synchronize(device)


def main(args: argparse.Namespace) -> None:
    device = torch.device(args.device)
    Engine = TRTModule(args.engine, device)
    H, W = Engine.inp_info[0].shape[-2:]

    # set desired output names order
    Engine.set_desired(['num_dets', 'bboxes', 'scores', 'labels'])

    images = path_to_list(args.imgs)
    save_path = Path(args.out_dir)

    if not args.show and not save_path.exists():
        save_path.mkdir(parents=True, exist_ok=True)

    profile_count = 0
    stats = {
        'read': 0.0,
        'preprocess': 0.0,
        'infer': 0.0,
        'postprocess': 0.0,
        'draw': 0.0,
        'total': 0.0
    }
    if args.profile:
        print(f'[profile] enabled | warmup={args.profile_warmup} | every={args.profile_every}')

    for image in images:
        total_t0 = time.perf_counter()
        save_image = save_path / image.name

        t0 = time.perf_counter()
        bgr = cv2.imread(str(image))
        t1 = time.perf_counter()
        draw = bgr.copy()

        t2 = time.perf_counter()
        bgr, ratio, dwdh = letterbox(bgr, (W, H))
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        tensor = blob(rgb, return_seg=False)
        dwdh = torch.asarray(dwdh * 2, dtype=torch.float32, device=device)
        tensor = torch.asarray(tensor, device=device)
        t3 = time.perf_counter()
        # inference
        maybe_sync(device)
        t4 = time.perf_counter()
        data = Engine(tensor)
        maybe_sync(device)
        t5 = time.perf_counter()

        bboxes, scores, labels = det_postprocess(data)
        t6 = time.perf_counter()
        if bboxes.numel() == 0:
            # if no bounding box
            print(f'{image}: no object!')
            continue
        bboxes -= dwdh
        bboxes /= ratio

        for (bbox, score, label) in zip(bboxes, scores, labels):
            bbox = bbox.round().int().tolist()
            cls_id = int(label)
            cls = CLASSES_DET[cls_id]
            color = COLORS[cls]

            text = f'{cls}:{score:.3f}'
            x1, y1, x2, y2 = bbox

            (_w, _h), _bl = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX,
                                            0.8, 1)
            _y1 = min(y1 + 1, draw.shape[0])

            cv2.rectangle(draw, (x1, y1), (x2, y2), color, 2)
            cv2.rectangle(draw, (x1, _y1), (x1 + _w, _y1 + _h + _bl),
                          (0, 0, 255), -1)
            cv2.putText(draw, text, (x1, _y1 + _h), cv2.FONT_HERSHEY_SIMPLEX,
                        0.75, (255, 255, 255), 2)
        t7 = time.perf_counter()

        if args.show:
            cv2.imshow('result', draw)
            cv2.waitKey(0)
        else:
            cv2.imwrite(str(save_image), draw)
        total_t1 = time.perf_counter()

        if args.profile:
            profile_count += 1
            if profile_count > args.profile_warmup:
                stats['read'] += (t1 - t0) * 1000.0
                stats['preprocess'] += (t3 - t2) * 1000.0
                stats['infer'] += (t5 - t4) * 1000.0
                stats['postprocess'] += (t6 - t5) * 1000.0
                stats['draw'] += (t7 - t6) * 1000.0
                stats['total'] += (total_t1 - total_t0) * 1000.0

                measured = profile_count - args.profile_warmup
                if measured % args.profile_every == 0:
                    inv = 1.0 / args.profile_every
                    print(
                        '[profile] avg over '
                        f'{args.profile_every} imgs | '
                        f'read={stats["read"] * inv:.3f} ms | '
                        f'preprocess={stats["preprocess"] * inv:.3f} ms | '
                        f'infer={stats["infer"] * inv:.3f} ms | '
                        f'postprocess={stats["postprocess"] * inv:.3f} ms | '
                        f'draw={stats["draw"] * inv:.3f} ms | '
                        f'total={stats["total"] * inv:.3f} ms'
                    )
                    for k in stats:
                        stats[k] = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', type=str, help='Engine file')
    parser.add_argument('--imgs', type=str, help='Images file')
    parser.add_argument('--show',
                        action='store_true',
                        help='Show the detection results')
    parser.add_argument('--out-dir',
                        type=str,
                        default='./output',
                        help='Path to output file')
    parser.add_argument('--device',
                        type=str,
                        default='cuda:0',
                        help='TensorRT infer device')
    parser.add_argument('--profile',
                        action='store_true',
                        help='Enable per-stage profiling')
    parser.add_argument('--profile-every',
                        type=int,
                        default=30,
                        help='Print average every N measured images')
    parser.add_argument('--profile-warmup',
                        type=int,
                        default=10,
                        help='Skip first N images in profile stats')
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = parse_args()
    main(args)
