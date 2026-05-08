#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_NAME="yolo26n-p2"
MODEL_ONNX_FILE="/root/deepstream_yolo/yolo26n-p2.onnx"
MODEL_ENGINE_FILE="/root/deepstream_yolo/yolo26n-p2.engine"
MODEL_LABELS_FILE="/root/deepstream_yolo/yolo26n-p2_labels.txt"
export MODEL_NAME MODEL_ONNX_FILE MODEL_ENGINE_FILE MODEL_LABELS_FILE
bash "${SCRIPT_DIR}/setup_yolo26_model.sh"
