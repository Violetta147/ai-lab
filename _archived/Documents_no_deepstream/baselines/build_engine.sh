#!/bin/bash
set -euo pipefail

# Build TensorRT engine từ ONNX với timing cache.
#
# Dùng biến môi trường để cấu hình:
# - ONNX_PATH            (default: /home/jetson/Documents/yolov8n.transd.onnx)
# - ENGINE_OUT           (default: /home/jetson/Documents/baselines/engines/candidate.engine)
# - WORKSPACE_MB         (default: 1024)
# - PRECISION            (fp32|fp16, default: fp32)
# - SHAPES               (vd: images:1x3x640x640)  [optional]
# - TIMING_CACHE_FILE    (path)                    [optional]
#
# Ví dụ:
#   PRECISION=fp16 TIMING_CACHE_FILE=baselines/caches/y8.cache \
#   ENGINE_OUT=baselines/engines/y8_fp16.engine \
#   bash baselines/build_engine.sh

ONNX_PATH="${ONNX_PATH:-/home/jetson/Documents/yolov8n.transd.onnx}"
ENGINE_OUT="${ENGINE_OUT:-/home/jetson/Documents/baselines/engines/candidate.engine}"
WORKSPACE_MB="${WORKSPACE_MB:-1024}"
PRECISION="${PRECISION:-fp32}"
SHAPES="${SHAPES:-}"
TIMING_CACHE_FILE="${TIMING_CACHE_FILE:-}"

TRTEXEC="${TRTEXEC:-/usr/src/tensorrt/bin/trtexec}"
if [ ! -x "$TRTEXEC" ]; then TRTEXEC="/usr/bin/trtexec"; fi

mkdir -p "$(dirname "$ENGINE_OUT")"
if [ -n "$TIMING_CACHE_FILE" ]; then
  mkdir -p "$(dirname "$TIMING_CACHE_FILE")"
fi

cmd=(
  "$TRTEXEC"
  --onnx="$ONNX_PATH"
  --workspace="$WORKSPACE_MB"
  --saveEngine="$ENGINE_OUT"
)

if [ -n "$SHAPES" ]; then
  cmd+=( --shapes="$SHAPES" )
fi

case "$PRECISION" in
  fp32) ;;
  fp16) cmd+=( --fp16 ) ;;
  *)
    echo "ERROR: PRECISION must be fp32|fp16 (got: $PRECISION)" >&2
    exit 2
    ;;
esac

if [ -n "$TIMING_CACHE_FILE" ]; then
  cmd+=( --timingCacheFile="$TIMING_CACHE_FILE" )
fi

echo "=== Build engine ==="
echo "ONNX        : $ONNX_PATH"
echo "ENGINE_OUT  : $ENGINE_OUT"
echo "WORKSPACE_MB: $WORKSPACE_MB"
echo "PRECISION   : $PRECISION"
echo "SHAPES      : ${SHAPES:-N/A}"
echo "TIMING_CACHE: ${TIMING_CACHE_FILE:-N/A}"
echo
echo "CMD:"
printf '  %q' "${cmd[@]}"
echo
echo

"${cmd[@]}"

echo
echo "DONE. Engine saved: $ENGINE_OUT"

