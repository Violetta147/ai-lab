#!/usr/bin/env bash
# =============================================================================
# YOLO26 RTSP ULTIMATE SETUP (v5.3 - Self-Contained)
# 
# Chức năng:
#   1. Tự động tạo labels.txt (bus, car, motor, truck)
#   2. Tự động sinh file config_infer_primary_yolo26.txt
#   3. Tự động sinh file deepstream_app_yolo26_rtsp.txt
#   4. Khởi chạy DeepStream Pipeline cho YOLO26
#
# Cách dùng:
#   LAPTOP_IP=192.168.1.xxx bash setup_yolo26_ultimate.sh
# =============================================================================
set -euo pipefail

# --- CONFIG ---
LAPTOP_IP="${LAPTOP_IP:-192.168.1.154}"
WORK_DIR="/root/deepstream_yolo"
ENGINE_FILE="${WORK_DIR}/YOLO26n_Pruned_Final.engine"
ONNX_FILE="${WORK_DIR}/YOLO26n_Pruned_Final.onnx"

# FILE NAMES (Non-destructive)
LABELS_FILE="${WORK_DIR}/labels_yolo26.txt"
CUSTOM_LIB_Y26="${WORK_DIR}/libnvdsinfer_custom_impl_Yolo26.so"
INFER_CFG_Y26="${WORK_DIR}/config_infer_primary_yolo26.txt"
APP_CFG_Y26="${WORK_DIR}/deepstream_app_yolo26_rtsp.txt"

DS_DIR="/opt/nvidia/deepstream/deepstream-6.0"

echo "============================================"
echo "[INFO] YOLO26 Ultimate Setup starting..."
echo "============================================"

# --- 1. Tự động tạo Labels File ---
if [ ! -f "${LABELS_FILE}" ]; then
    echo "[INFO] Creating labels file: ${LABELS_FILE}"
    cat > "${LABELS_FILE}" << EOF
bus
car
motor
truck
EOF
fi

# --- 2. Check Engine File ---
if [ ! -f "${ENGINE_FILE}" ]; then
    echo "[ERROR] Không tìm thấy file Engine tại: ${ENGINE_FILE}"
    echo "Hãy chắc chắn bạn đã build engine và đặt đúng tên file."
    exit 1
fi

# --- 3. Logic build parser đặc thù cho YOLO26 ---
if [ ! -f "${CUSTOM_LIB_Y26}" ]; then
    echo "[INFO] Kiểm tra bộ biên dịch..."
    if ! command -v make &> /dev/null; then
        apt-get update && apt-get install -y build-essential
    fi

    echo "[INFO] Building YOLO26 Parser..."
    cd /root/DeepStream-Yolo/nvdsinfer_custom_impl_Yolo
    export CUDA_VER=10.2
    make clean && make
    cp libnvdsinfer_custom_impl_Yolo.so "${CUSTOM_LIB_Y26}"
    echo "[SUCCESS] Parser created: ${CUSTOM_LIB_Y26}"
fi

# --- 4. Generate Inference Config ---
echo "[INFO] Writing ${INFER_CFG_Y26}..."
cat > "${INFER_CFG_Y26}" << EOF
[property]
gpu-id=0
net-scale-factor=0.00392156862745098
model-color-format=0
onnx-file=${ONNX_FILE}
model-engine-file=${ENGINE_FILE}
labelfile-path=labels_yolo26.txt
batch-size=1
network-mode=2
num-detected-classes=4
interval=2
gie-unique-id=1
process-mode=1
network-type=0
cluster-mode=4
maintain-aspect-ratio=1
symmetric-padding=1
parse-bbox-func-name=NvDsInferParseYolo
custom-lib-path=libnvdsinfer_custom_impl_Yolo26.so
engine-create-func-name=NvDsInferYoloCudaEngineGet

[class-attrs-all]
pre-cluster-threshold=0.25
topk=100
EOF

# --- 5. Generate App Config ---
echo "[INFO] Writing ${APP_CFG_Y26}..."
cat > "${APP_CFG_Y26}" << EOF
[application]
enable-perf-measurement=1
perf-measurement-interval-sec=5

[source0]
enable=1
type=4
uri=rtsp://${LAPTOP_IP}:8554/mystream
gpu-id=0
select-rtp-protocol=4
latency=150

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

# --- 6. Clean & Run ---
echo "[INFO] Cleaning cache..."
rm -rf /root/.cache/gstreamer-1.0/
ldconfig

echo "[INFO] Launching DeepStream YOLO26..."
cd "${WORK_DIR}"
deepstream-app -c "${APP_CFG_Y26}"
