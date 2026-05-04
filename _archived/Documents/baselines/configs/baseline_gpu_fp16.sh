#!/bin/bash
set -euo pipefail

TRTEXEC="${TRTEXEC:-/usr/src/tensorrt/bin/trtexec}"
if [ ! -x "$TRTEXEC" ]; then
  TRTEXEC="/usr/bin/trtexec"
fi

# Baseline thuần GPU (bỏ H2D/D2H) cho YOLOv8n 640x640
"$TRTEXEC" --onnx=workspace/yolov8n.transd.onnx \
  --shapes=images:1x3x640x640 \
  --fp16 \
  --noDataTransfers \
  --useCudaGraph \
  --useSpinWait \
  --warmUp=200 \
  --duration=10
