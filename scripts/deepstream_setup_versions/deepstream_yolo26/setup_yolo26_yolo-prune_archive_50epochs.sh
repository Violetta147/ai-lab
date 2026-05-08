#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_NAME="yolo-prune_archive_50epochs_best"
MODEL_ONNX_FILE="/root/deepstream_yolo/yolo-prune_archive_50epochs_best.onnx"
MODEL_ENGINE_FILE="/root/deepstream_yolo/yolo-prune_archive_50epochs_best.engine"
MODEL_LABELS_FILE="/root/deepstream_yolo/yolo-prune_archive_50epochs_best_labels.txt"
export MODEL_NAME MODEL_ONNX_FILE MODEL_ENGINE_FILE MODEL_LABELS_FILE
bash "${SCRIPT_DIR}/setup_yolo26_model.sh"
