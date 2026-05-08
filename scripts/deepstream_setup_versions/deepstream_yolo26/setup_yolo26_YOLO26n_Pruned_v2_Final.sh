#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_NAME="YOLO26n_Pruned_v2_Final_best"
MODEL_ONNX_FILE="/root/deepstream_yolo/YOLO26n_Pruned_v2_Final_best.onnx"
MODEL_ENGINE_FILE="/root/deepstream_yolo/YOLO26n_Pruned_v2_Final_best.engine"
MODEL_LABELS_FILE="/root/deepstream_yolo/YOLO26n_Pruned_v2_Final_best_labels.txt"
export MODEL_NAME MODEL_ONNX_FILE MODEL_ENGINE_FILE MODEL_LABELS_FILE
bash "${SCRIPT_DIR}/setup_yolo26_model.sh"
