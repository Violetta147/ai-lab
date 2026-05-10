#!/usr/bin/env bash
# =============================================================================
# C2 Center — DeepStream Multi-Stream Pipeline (Crossing Version)
#
# Version optimized for Line Crossing (Entry/Exit) filtering at the Edge.
# Optimized for Jetson Nano (Headless, Batch=1, Hardware limits).
# =============================================================================
set -euo pipefail

# ======================== CONFIGURATION ======================================
LAPTOP_A_IP="${LAPTOP_A_IP:-192.168.1.196}"
NUM_SOURCES="${NUM_SOURCES:-2}"
WORK_DIR="${WORK_DIR:-$(pwd)}"

resolve_ds_dir() {
    if [ -n "${DS_DIR:-}" ] && [ -d "${DS_DIR}" ]; then
        echo "${DS_DIR}"
        return 0
    fi
    for candidate in /opt/nvidia/deepstream/deepstream-6.0.1-devel /opt/nvidia/deepstream/deepstream-6.0.1 /opt/nvidia/deepstream/deepstream-6.0; do
        if [ -d "${candidate}" ]; then echo "${candidate}"; return 0; fi
    done
    echo "/opt/nvidia/deepstream/deepstream-6.0"
}

DS_DIR="$(resolve_ds_dir)"
SAMPLES_DIR="${DS_DIR}/samples"
[ ! -d "${SAMPLES_DIR}" ] && SAMPLES_DIR="/opt/nvidia/deepstream/deepstream-6.0/samples"

MODEL_NAME="${MODEL_NAME:-yolo_all_exports_p2n_fine-tuning2_best}"
MODEL_ENGINE_FILE="${MODEL_ENGINE_FILE:-${WORK_DIR}/${MODEL_NAME}.engine}"
MODEL_ONNX_FILE="${MODEL_ONNX_FILE:-${WORK_DIR}/${MODEL_NAME}.onnx}"
MODEL_LABELS_FILE="${MODEL_LABELS_FILE:-${WORK_DIR}/${MODEL_NAME}_labels.txt}"
CUSTOM_LIB_Y26="${CUSTOM_LIB_Y26:-${WORK_DIR}/libnvdsinfer_custom_impl_Yolo26.so}"

KAFKA_BROKER="${LAPTOP_A_IP}:9092"
KAFKA_TOPIC="${KAFKA_TOPIC:-c2_metadata}"
RTSP_BASE_PORT="${RTSP_BASE_PORT:-8554}"
RTSP_PATHS="${RTSP_PATHS:-}"

INFER_CFG="${WORK_DIR}/config_infer_c2.txt"
APP_CFG="${WORK_DIR}/deepstream_c2_crossing.txt"
KAFKA_CFG="${WORK_DIR}/cfg_kafka.txt"
ANALYTICS_CFG="${WORK_DIR}/config_nvdsanalytics_crossing.txt"

echo "[C2] Crossing Version — Laptop A IP: ${LAPTOP_A_IP}, Sources: ${NUM_SOURCES}"

# --- Validation ---
[ ! -f "${MODEL_ENGINE_FILE}" ] && echo "[ERROR] Missing: ${MODEL_ENGINE_FILE}" && exit 1
[ ! -f "${MODEL_LABELS_FILE}" ] && echo "[ERROR] Missing: ${MODEL_LABELS_FILE}" && exit 1
[ ! -f "${CUSTOM_LIB_Y26}" ] && echo "[ERROR] Missing: ${CUSTOM_LIB_Y26}" && exit 1

# --- RCA Fix: Headless Mode ---
echo "[C2] Applying Headless Fix (RCA-2026-05-09)..."
# Strip EGL sink stub to prevent plugin blacklisting in headless containers
rm -f /usr/lib/aarch64-linux-gnu/gstreamer-1.0/libgsteglglessink.so 2>/dev/null || true
rm -rf /root/.cache/gstreamer-1.0/ 2>/dev/null || true
ldconfig
unset DISPLAY 2>/dev/null || true
export EGL_DISPLAY=none

# Sanitize variables (strip potential \r or spaces)
LAPTOP_A_IP=$(echo "${LAPTOP_A_IP}" | tr -d '\r\n ')
RTSP_PATHS=$(echo "${RTSP_PATHS}" | tr -d '\r\n ')

# --- Auto-detect num classes ---
MODEL_NUM_CLASSES="$(awk 'NF { c+=1 } END { print c+0 }' "${MODEL_LABELS_FILE}")"

# --- RCA Fix: Batch Size 1 for Jetson Nano ---
INFER_BATCH_SIZE=1

# =============================================================================
# CONFIG: Inference
# =============================================================================
cat > "${INFER_CFG}" << EOF
[property]
gpu-id=0
net-scale-factor=0.00392156862745098
model-color-format=0
onnx-file=${MODEL_ONNX_FILE}
model-engine-file=${MODEL_ENGINE_FILE}
labelfile-path=${MODEL_LABELS_FILE}
batch-size=${INFER_BATCH_SIZE}
network-mode=0
num-detected-classes=${MODEL_NUM_CLASSES}
interval=2
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
pre-cluster-threshold=0.25
topk=100
EOF

# =============================================================================
# CONFIG: nvdsanalytics (Crossing)
# =============================================================================
echo "[C2] Writing Analytics Crossing config..."
cat > "${ANALYTICS_CFG}" << EOF
[property]
enable=1
config-width=640
config-height=640
osd-display=0
EOF

for i in $(seq 0 $((NUM_SOURCES - 1))); do
    cat >> "${ANALYTICS_CFG}" << EOF

[line-crossing-stream-${i}]
enable=1
# Format: x1;y1;x2;y2;x3;y3;x4;y4 (Line then direction)
line-crossing-Entry=100;200;500;200;100;150;500;150
line-crossing-Exit=100;400;500;400;100;450;500;450
EOF
done

# =============================================================================
# CONFIG: Kafka & Application
# =============================================================================
cat > "${KAFKA_CFG}" << EOF
[message-broker]
bootstrap.servers=${KAFKA_BROKER}
EOF

NVMSGCONV_CFG_DST="${WORK_DIR}/nvmsgconv_c2_config.txt"
MSGCONV_LIB_DST="${WORK_DIR}/libnvds_msgconv_c2.so"

echo "[C2] Writing msgconv config..."
cat > "${NVMSGCONV_CFG_DST}" << EOF
[property]
payload-type=257
msg2p-lib=/usr/lib/libnvds_msgconv_c2.so
msg2p-newapi=1
frame-interval=1
EOF

echo "[C2] Writing app config..."
cat > "${APP_CFG}" << EOF
[application]
enable-perf-measurement=1
perf-measurement-interval-sec=5

[tiled-display]
enable=0

[osd]
enable=0

[streammux]
gpu-id=0
live-source=1
# RCA Fix: Force batch-size=1 even for multi-source to match static ONNX batch=1
batch-size=1
width=640
height=640
batched-push-timeout=40000
# Jetson Unified Memory
nvbuf-memory-type=0

[primary-gie]
enable=1
gpu-id=0
gie-unique-id=1
config-file=${INFER_CFG}

[tracker]
enable=1
tracker-width=640
tracker-height=384
gpu-id=0
ll-lib-file=${DS_DIR}/lib/libnvds_nvmultiobjecttracker.so
ll-config-file=${SAMPLES_DIR}/configs/deepstream-app/config_tracker_NvDCF_perf.yml
enable-past-frame=1
display-tracking-id=1

[nvds-analytics]
enable=1
config-file=${ANALYTICS_CFG}

[sink0]
enable=1
type=6
msg-conv-config=${NVMSGCONV_CFG_DST}
msg-conv-payload-type=257
msg-conv-msg2p-lib=/usr/lib/libnvds_msgconv_c2.so
msg-conv-msg2p-new-api=1
msg-conv-frame-interval=1
msg-broker-proto-lib=${DS_DIR}/lib/libnvds_kafka_proto.so
msg-broker-conn-str=${LAPTOP_A_IP};9092;${KAFKA_TOPIC}
msg-broker-config=${KAFKA_CFG}
sync=0
EOF

IFS=',' read -ra RTSP_PATH_ARR <<< "${RTSP_PATHS}"
for i in $(seq 0 $((NUM_SOURCES - 1))); do
    # Default to 'muahe' if RTSP_PATHS is empty
    CAM_PATH="${RTSP_PATH_ARR[$i]:-muahe}"
    cat >> "${APP_CFG}" << EOF

[source${i}]
enable=1
type=4
uri=rtsp://${LAPTOP_A_IP}:${RTSP_BASE_PORT}/${CAM_PATH}
gpu-id=0
select-rtp-protocol=4
latency=150
rtsp-reconnect-interval-sec=5
EOF
done

echo "[C2] Starting deepstream-app (Crossing Mode)..."
deepstream-app -c "${APP_CFG}"
