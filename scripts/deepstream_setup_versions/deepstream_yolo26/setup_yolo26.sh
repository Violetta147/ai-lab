#!/usr/bin/env bash
# =============================================================================
# YOLO26 RTSP SETUP (v5.5 - Marcos Optimized)
# 
# Usage:
#   LAPTOP_RTSP_URI=rtsp://192.168.55.100:8554/mystream bash setup_yolo26.sh
# =============================================================================
set -euo pipefail

# --- CONFIG ---
LAPTOP_RTSP_URI="${LAPTOP_RTSP_URI:-}"
WORK_DIR="/root/deepstream_yolo"
DEPLOY_DIR="${WORK_DIR}/deepstream_yolo26"
ENGINE_FILE="${WORK_DIR}/YOLO26n_Pruned_Final.engine"
ONNX_FILE="${WORK_DIR}/YOLO26n_Pruned_Final.onnx"

# Non-destructive file names
LABELS_FILE="${WORK_DIR}/labels_yolo26.txt"
CUSTOM_LIB_Y26="${WORK_DIR}/libnvdsinfer_custom_impl_Yolo26.so"
INFER_CFG_Y26="${DEPLOY_DIR}/config_infer_primary_yolo26.txt"
APP_CFG_Y26="${DEPLOY_DIR}/deepstream_app_yolo26_rtsp.txt"

DS_DIR="/opt/nvidia/deepstream/deepstream-6.0"

echo "============================================"
echo "[INFO] YOLO26 DeepStream Pipeline Starting..."
echo "[INFO] RTSP Source: ${LAPTOP_RTSP_URI}"
echo "============================================"

# --- 1. Validation ---
if [ -z "${LAPTOP_RTSP_URI}" ]; then
    echo "[ERROR] Missing LAPTOP_RTSP_URI environment variable."
    exit 1
fi
[ ! -f "${ENGINE_FILE}" ] && echo "[ERROR] Missing Engine: ${ENGINE_FILE}" && exit 1

# --- 2. Auto-generate Labels ---
if [ ! -f "${LABELS_FILE}" ]; then
    echo "[INFO] Generating labels_yolo26.txt..."
    printf "bus\ncar\nmotor\ntruck\n" > "${LABELS_FILE}"
fi

# --- 3. Build Parser (In-container Build Support) ---
if [ ! -f "${CUSTOM_LIB_Y26}" ]; then
    echo "[INFO] Custom Parser not found. Attempting build..."
    if ! command -v make &> /dev/null; then
        echo "[INFO] Installing build tools (Apt update)..."
        apt-get update && apt-get install -y build-essential
    fi
    if [ -d "/root/DeepStream-Yolo/nvdsinfer_custom_impl_Yolo" ]; then
        cd /root/DeepStream-Yolo/nvdsinfer_custom_impl_Yolo
        export CUDA_VER=10.2
        make clean && make
        cp libnvdsinfer_custom_impl_Yolo.so "${CUSTOM_LIB_Y26}"
        cd "${DEPLOY_DIR}"
        echo "[SUCCESS] Parser built and saved to ${CUSTOM_LIB_Y26}"
    else
        echo "[ERROR] Repo DeepStream-Yolo not found at /root/DeepStream-Yolo"
        exit 1
    fi
fi

# --- 4. DeepStream System Cleanup ---
echo "[INFO] Clearing GStreamer cache and optimizing..."
rm -rf /root/.cache/gstreamer-1.0/
ldconfig
unset DISPLAY || true

# --- 5. Generate YOLO26 Inference Config (NMS-free Optimized) ---
echo "[INFO] Writing inference config..."
cat > "${INFER_CFG_Y26}" << EOF
[property]
gpu-id=0
net-scale-factor=0.00392156862745098
model-color-format=0
onnx-file=${ONNX_FILE}
model-engine-file=${ENGINE_FILE}
labelfile-path=../labels_yolo26.txt
batch-size=1
network-mode=2
num-detected-classes=4
interval=2
gie-unique-id=1
process-mode=1
network-type=0
maintain-aspect-ratio=1
symmetric-padding=1
parse-bbox-func-name=NvDsInferParseYolo
custom-lib-path=../libnvdsinfer_custom_impl_Yolo26.so
engine-create-func-name=NvDsInferYoloCudaEngineGet
# cluster-mode=4 is required for NMS-free models (YOLO26/v10)
cluster-mode=4

[class-attrs-all]
pre-cluster-threshold=0.25
topk=100
EOF

# --- 6. Generate Application Config ---
echo "[INFO] Writing application config..."
cat > "${APP_CFG_Y26}" << EOF
[application]
enable-perf-measurement=1
perf-measurement-interval-sec=5

[source0]
enable=1
type=4
uri=${LAPTOP_RTSP_URI}
gpu-id=0
select-rtp-protocol=4
latency=150
rtsp-reconnect-interval-sec=5

[streammux]
gpu-id=0
live-source=1
batch-size=1
width=640
height=640
batched-push-timeout=40000

[primary-gie]
enable=1
gpu-id=0
gie-unique-id=1
config-file=config_infer_primary_yolo26.txt

[tracker]
enable=1
tracker-width=640
tracker-height=384
gpu-id=0
ll-lib-file=${DS_DIR}/lib/libnvds_nvmultiobjecttracker.so
ll-config-file=${DS_DIR}/samples/configs/deepstream-app/config_tracker_NvDCF_perf.yml
enable-past-frame=1
display-tracking-id=1

[osd]
enable=1
gpu-id=0
process-mode=2
border-width=3
text-size=15

[sink0]
enable=1
type=4
codec=1
sync=0
bitrate=2000000
rtsp-port=8555
udp-port=5400
EOF

# --- 7. Final Execution ---
echo "[INFO] Starting deepstream-app..."
deepstream-app -c "${APP_CFG_Y26}"
