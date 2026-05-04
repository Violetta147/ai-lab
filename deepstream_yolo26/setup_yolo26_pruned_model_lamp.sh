#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_NAME="pruned_model_lamp"
MODEL_ONNX_FILE="/root/deepstream_yolo/pruned_model_lamp.onnx"
MODEL_ENGINE_FILE="/root/deepstream_yolo/pruned_model_lamp.engine"
MODEL_LABELS_FILE="/root/deepstream_yolo/pruned_model_lamp_labels.txt"
export MODEL_NAME MODEL_ONNX_FILE MODEL_ENGINE_FILE MODEL_LABELS_FILE
bash "${SCRIPT_DIR}/setup_yolo26_model.sh"
