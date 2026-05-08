#!/usr/bin/env bash
set -euo pipefail

# Jetson-side long-run validation for RTSP-first DeepStream pipeline.
# Input:  RTSP from laptop
# Output: RTSP out from Jetson (no local MP4 sink)

APP_CFG="${APP_CFG:-$HOME/deepstream_yolo/deepstream_app_yolov8_rtsp.txt}"
LOG_DIR="${LOG_DIR:-$HOME/deepstream_yolo/logs}"
RUN_TAG="${RUN_TAG:-rtsp_scale_$(date +%Y%m%d_%H%M%S)}"
LOG_FILE="${LOG_DIR}/${RUN_TAG}.log"

mkdir -p "${LOG_DIR}"

echo "[DEBUG] APP_CFG=${APP_CFG}"
echo "[DEBUG] LOG_FILE=${LOG_FILE}"

if [ ! -f "${APP_CFG}" ]; then
  echo "[ERROR] Missing app config: ${APP_CFG}"
  exit 1
fi

unset DISPLAY || true

echo "[DEBUG] Starting DeepStream scale run..."
deepstream-app -c "${APP_CFG}" 2>&1 | tee "${LOG_FILE}"

echo "[DEBUG] Run completed. Log saved to ${LOG_FILE}"
echo "[DEBUG] Quick summary:"
rg "PERF|App run successful|ERROR|WARN" "${LOG_FILE}" || true
