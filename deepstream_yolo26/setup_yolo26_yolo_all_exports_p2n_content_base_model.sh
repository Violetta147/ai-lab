#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_NAME="yolo_all_exports_p2n_content_base_model_best"
MODEL_ONNX_FILE="/root/deepstream_yolo/yolo_all_exports_p2n_content_base_model_best.onnx"
MODEL_ENGINE_FILE="/root/deepstream_yolo/yolo_all_exports_p2n_content_base_model_best.engine"
MODEL_LABELS_FILE="/root/deepstream_yolo/yolo_all_exports_p2n_content_base_model_best_labels.txt"
export MODEL_NAME MODEL_ONNX_FILE MODEL_ENGINE_FILE MODEL_LABELS_FILE
bash "${SCRIPT_DIR}/setup_yolo26_model.sh"
