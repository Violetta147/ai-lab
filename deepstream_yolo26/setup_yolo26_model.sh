#!/usr/bin/env bash
# =============================================================================
# YOLO26 RTSP SETUP (model-specific wrapper friendly)
#
# Usage:
#   LAPTOP_RTSP_URI=rtsp://... MODEL_ONNX_FILE=/root/deepstream_yolo/model.onnx \
#   MODEL_ENGINE_FILE=/root/deepstream_yolo/model.engine \
#   MODEL_LABELS_FILE=/root/deepstream_yolo/model_labels.txt \
#   bash setup_yolo26_model.sh
# =============================================================================
set -euo pipefail

LAPTOP_RTSP_URI="${LAPTOP_RTSP_URI:-}"
WORK_DIR="${WORK_DIR:-/root/deepstream_yolo}"
DEPLOY_DIR="${DEPLOY_DIR:-${WORK_DIR}/deepstream_yolo26}"
DS_DIR="${DS_DIR:-/opt/nvidia/deepstream/deepstream-6.0}"

MODEL_NAME="${MODEL_NAME:-yolo26_model}"
MODEL_ONNX_FILE="${MODEL_ONNX_FILE:-${WORK_DIR}/${MODEL_NAME}.onnx}"
MODEL_ENGINE_FILE="${MODEL_ENGINE_FILE:-${WORK_DIR}/${MODEL_NAME}.engine}"
MODEL_LABELS_FILE="${MODEL_LABELS_FILE:-${WORK_DIR}/${MODEL_NAME}_labels.txt}"
MODEL_INTERVAL="${MODEL_INTERVAL:-2}"
MODEL_PRE_CLUSTER_THRESHOLD="${MODEL_PRE_CLUSTER_THRESHOLD:-0.25}"
MODEL_TOPK="${MODEL_TOPK:-100}"
MODEL_NUM_CLASSES="${MODEL_NUM_CLASSES:-}"

CUSTOM_LIB_Y26="${CUSTOM_LIB_Y26:-${WORK_DIR}/libnvdsinfer_custom_impl_Yolo26.so}"
INFER_CFG_Y26="${DEPLOY_DIR}/config_infer_primary_${MODEL_NAME}.txt"
APP_CFG_Y26="${DEPLOY_DIR}/deepstream_app_${MODEL_NAME}_rtsp.txt"

echo "============================================"
echo "[INFO] YOLO26 DeepStream Pipeline Starting..."
echo "[INFO] MODEL_NAME: ${MODEL_NAME}"
echo "[INFO] ONNX: ${MODEL_ONNX_FILE}"
echo "[INFO] ENGINE: ${MODEL_ENGINE_FILE}"
echo "[INFO] LABELS: ${MODEL_LABELS_FILE}"
echo "[INFO] RTSP Source: ${LAPTOP_RTSP_URI}"
echo "============================================"

if [ -z "${LAPTOP_RTSP_URI}" ]; then
    echo "[ERROR] Missing LAPTOP_RTSP_URI environment variable."
    exit 1
fi
if [ ! -f "${MODEL_ENGINE_FILE}" ]; then
    echo "[ERROR] Missing Engine: ${MODEL_ENGINE_FILE}"
    echo "[INFO] Build engine first from ONNX on Jetson."
    exit 1
fi

if [ ! -f "${MODEL_LABELS_FILE}" ]; then
    echo "[INFO] Labels not found. Generating default labels at ${MODEL_LABELS_FILE}..."
    printf "bus\ncar\nmotor\ntruck\n" > "${MODEL_LABELS_FILE}"
fi

if [ -z "${MODEL_NUM_CLASSES}" ]; then
    MODEL_NUM_CLASSES="$(awk 'NF { c+=1 } END { print c+0 }' "${MODEL_LABELS_FILE}")"
fi
if [ "${MODEL_NUM_CLASSES}" -le 0 ]; then
    echo "[ERROR] Invalid class count (${MODEL_NUM_CLASSES}) from ${MODEL_LABELS_FILE}"
    exit 1
fi

if [ ! -f "${CUSTOM_LIB_Y26}" ]; then
    echo "[INFO] Custom Parser not found. Attempting build..."
    if ! command -v make >/dev/null 2>&1; then
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

echo "[INFO] Clearing GStreamer cache and optimizing..."
rm -rf /root/.cache/gstreamer-1.0/
ldconfig
unset DISPLAY || true

echo "[INFO] Writing inference config..."
cat > "${INFER_CFG_Y26}" << EOF
[property]
gpu-id=0
net-scale-factor=0.00392156862745098
model-color-format=0
onnx-file=${MODEL_ONNX_FILE}
model-engine-file=${MODEL_ENGINE_FILE}
labelfile-path=${MODEL_LABELS_FILE}
batch-size=1
network-mode=2
num-detected-classes=${MODEL_NUM_CLASSES}
interval=${MODEL_INTERVAL}
gie-unique-id=1
process-mode=1
network-type=0
maintain-aspect-ratio=1
symmetric-padding=1
parse-bbox-func-name=NvDsInferParseYolo
custom-lib-path=${CUSTOM_LIB_Y26}
engine-create-func-name=NvDsInferYoloCudaEngineGet
cluster-mode=4

[class-attrs-all]
pre-cluster-threshold=${MODEL_PRE_CLUSTER_THRESHOLD}
topk=${MODEL_TOPK}
EOF

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
config-file=${INFER_CFG_Y26}

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
iframeinterval=30
profile=1
rtsp-port=8555
udp-port=5400
EOF

echo "[INFO] Starting deepstream-app with ${APP_CFG_Y26}..."
deepstream-app -c "${APP_CFG_Y26}"
