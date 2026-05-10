#!/usr/bin/env bash
# =============================================================================
# C2 Center — DeepStream Multi-Stream Pipeline (Edge AI)
#
# Extends the proven single-stream pattern from setup_yolo26_model.sh
# Changes: multi-source + Kafka sink (text-only, no video output)
#
# Usage (inside DeepStream Docker container):
#   LAPTOP_A_IP=192.168.1.196 \
#   NUM_SOURCES=2 \
#   bash setup_c2_multistream.sh
#
# Prerequisites:
#   - DeepStream 6.0.1 Docker container running on WSL2
#   - Model .engine + labels.txt in WORK_DIR
#   - Custom parser libnvdsinfer_custom_impl_Yolo26.so built
#   - Kafka broker running on Laptop A :9092
#   - MediaMTX + FFmpeg cameras running on Laptop A
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

    for candidate in \
        /opt/nvidia/deepstream/deepstream-6.0.1-devel \
        /opt/nvidia/deepstream/deepstream-6.0.1 \
        /opt/nvidia/deepstream/deepstream-6.0; do
        if [ -d "${candidate}" ]; then
            echo "${candidate}"
            return 0
        fi
    done

    echo "/opt/nvidia/deepstream/deepstream-6.0"
}

DS_DIR="$(resolve_ds_dir)"
SAMPLES_DIR="${DS_DIR}/samples"
if [ ! -d "${SAMPLES_DIR}" ] && [ -d "/opt/nvidia/deepstream/deepstream-6.0/samples" ]; then
    SAMPLES_DIR="/opt/nvidia/deepstream/deepstream-6.0/samples"
fi

# Model files (same as single-stream)
MODEL_NAME="${MODEL_NAME:-yolo_all_exports_p2n_fine-tuning2_best}"
MODEL_ENGINE_FILE="${MODEL_ENGINE_FILE:-${WORK_DIR}/${MODEL_NAME}.engine}"
MODEL_ONNX_FILE="${MODEL_ONNX_FILE:-${WORK_DIR}/${MODEL_NAME}.onnx}"
MODEL_LABELS_FILE="${MODEL_LABELS_FILE:-${WORK_DIR}/${MODEL_NAME}_labels.txt}"
CUSTOM_LIB_Y26="${CUSTOM_LIB_Y26:-${WORK_DIR}/libnvdsinfer_custom_impl_Yolo26.so}"

# Inference (same as single-stream)
MODEL_INTERVAL="${MODEL_INTERVAL:-2}"
MODEL_PRE_CLUSTER_THRESHOLD="${MODEL_PRE_CLUSTER_THRESHOLD:-0.25}"
MODEL_TOPK="${MODEL_TOPK:-100}"
MODEL_NUM_CLASSES="${MODEL_NUM_CLASSES:-}"

# Kafka
KAFKA_BROKER="${LAPTOP_A_IP}:9092"
KAFKA_TOPIC="${KAFKA_TOPIC:-c2_metadata}"

# RTSP source paths (override with: RTSP_PATHS="muahe,camera_parking")
# Defaults to cam1,cam2,...,camN if not provided
RTSP_BASE_PORT="${RTSP_BASE_PORT:-8554}"
RTSP_PATHS="${RTSP_PATHS:-}"

# Output files
INFER_CFG="${WORK_DIR}/config_infer_c2.txt"
APP_CFG="${WORK_DIR}/deepstream_c2_multistream.txt"
KAFKA_CFG="${WORK_DIR}/cfg_kafka.txt"
# =============================================================================

echo "============================================"
echo "[C2] DeepStream Multi-Stream Pipeline"
echo "[C2] Laptop A IP:   ${LAPTOP_A_IP}"
echo "[C2] Sources:       ${NUM_SOURCES}"
echo "[C2] Kafka:         ${KAFKA_BROKER} → topic: ${KAFKA_TOPIC}"
echo "[C2] Model:         ${MODEL_NAME}"
echo "[C2] Work Dir:      ${WORK_DIR}"
echo "============================================"

# --- Auto-detect num classes ---
if [ -z "${MODEL_NUM_CLASSES}" ]; then
    MODEL_NUM_CLASSES="$(awk 'NF { c+=1 } END { print c+0 }' "${MODEL_LABELS_FILE}")"
fi
echo "[C2] Classes:       ${MODEL_NUM_CLASSES}"

# --- Inference Batch Size ---
# Force batch-size=1 for Jetson Nano to prevent TRT engine rebuild and OOM.
# The streammux can still handle multiple streams, but inferencing will process 1 frame at a time.
INFER_BATCH_SIZE=1

# --- Validation ---
[ ! -f "${MODEL_ENGINE_FILE}" ] && echo "[ERROR] Missing: ${MODEL_ENGINE_FILE}" && exit 1
[ ! -f "${MODEL_LABELS_FILE}" ] && echo "[ERROR] Missing: ${MODEL_LABELS_FILE}" && exit 1
[ ! -f "${CUSTOM_LIB_Y26}" ] && echo "[ERROR] Missing: ${CUSTOM_LIB_Y26}" && exit 1

# --- Environment optimization ---
echo "[C2] Clearing GStreamer cache..."
rm -rf /root/.cache/gstreamer-1.0/ 2>/dev/null || true
ldconfig
unset DISPLAY 2>/dev/null || true

# =============================================================================
# CONFIG: Inference (identical to single-stream)
# =============================================================================
echo "[C2] Writing inference config..."
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

# =============================================================================
# CONFIG: Kafka connection
# Section header [message-broker] is REQUIRED by libnvds_kafka_proto.so
# =============================================================================
echo "[C2] Writing Kafka config..."
cat > "${KAFKA_CFG}" << EOF
[message-broker]
bootstrap.servers=${KAFKA_BROKER}
EOF

# =============================================================================
# CONFIG: nvmsgconv must live at WORK_DIR root so msg-conv-config path resolves.
# The source-of-truth file is in nvmsgconv_c2/; copy it up if not already there.
# =============================================================================
NVMSGCONV_CFG_SRC="${WORK_DIR}/nvmsgconv_c2/nvmsgconv_c2_config.txt"
NVMSGCONV_CFG_DST="${WORK_DIR}/nvmsgconv_c2_config.txt"
if [ -f "${NVMSGCONV_CFG_SRC}" ] && [ ! -f "${NVMSGCONV_CFG_DST}" ]; then
    echo "[C2] Copying nvmsgconv_c2_config.txt to WORK_DIR root..."
    cp "${NVMSGCONV_CFG_SRC}" "${NVMSGCONV_CFG_DST}"
fi
[ ! -f "${NVMSGCONV_CFG_DST}" ] && echo "[ERROR] Missing nvmsgconv config: ${NVMSGCONV_CFG_DST}" && exit 1

# Same for the msg2p shared library
MSGCONV_LIB_SRC="${WORK_DIR}/nvmsgconv_c2/libnvds_msgconv_c2.so"
MSGCONV_LIB_DST="${WORK_DIR}/libnvds_msgconv_c2.so"
if [ -f "${MSGCONV_LIB_SRC}" ] && [ ! -f "${MSGCONV_LIB_DST}" ]; then
    echo "[C2] Copying libnvds_msgconv_c2.so to WORK_DIR root..."
    cp "${MSGCONV_LIB_SRC}" "${MSGCONV_LIB_DST}"
fi
[ ! -f "${MSGCONV_LIB_DST}" ] && echo "[ERROR] Missing msg2p lib: ${MSGCONV_LIB_DST} (build it: cd nvmsgconv_c2 && make)" && exit 1

# =============================================================================
# CONFIG: App pipeline
# =============================================================================
echo "[C2] Writing app config (${NUM_SOURCES} sources)..."

cat > "${APP_CFG}" << EOF
[application]
enable-perf-measurement=1
perf-measurement-interval-sec=5
EOF

# --- Generate N source blocks ---
# RTSP_PATHS="muahe,camera_parking" overrides the default cam1,cam2,...
IFS=',' read -ra RTSP_PATH_ARR <<< "${RTSP_PATHS}"
for i in $(seq 0 $((NUM_SOURCES - 1))); do
    PORT=${RTSP_BASE_PORT}  # Keep port 8554 for ALL streams
    if [ -n "${RTSP_PATH_ARR[$i]:-}" ]; then
        CAM_PATH="${RTSP_PATH_ARR[$i]}"
    else
        CAM_PATH="cam$((i + 1))"
    fi
    cat >> "${APP_CFG}" << EOF

[source${i}]
enable=1
type=4
uri=rtsp://${LAPTOP_A_IP}:${PORT}/${CAM_PATH}
gpu-id=0
select-rtp-protocol=4
latency=150
rtsp-reconnect-interval-sec=5
EOF
done

# --- Streammux ---
cat >> "${APP_CFG}" << EOF

[streammux]
gpu-id=0
live-source=1
batch-size=${NUM_SOURCES}
width=640
height=640
batched-push-timeout=40000

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

[tiled-display]
enable=0

[osd]
enable=0

[sink0]
enable=1
type=6
msg-conv-config=${NVMSGCONV_CFG_DST}
msg-conv-payload-type=256
msg-conv-msg2p-lib=${MSGCONV_LIB_DST}
msg-broker-proto-lib=${DS_DIR}/lib/libnvds_kafka_proto.so
msg-broker-conn-str=${LAPTOP_A_IP};9092;${KAFKA_TOPIC}
msg-broker-config=${KAFKA_CFG}
sync=0
EOF

echo "============================================"
echo "[C2] Config generation complete."
echo "[C2] Inference:  ${INFER_CFG}"
echo "[C2] App:        ${APP_CFG}"
echo "[C2] Kafka:      ${KAFKA_CFG}"
echo ""
echo "[C2] Starting deepstream-app..."
echo "============================================"

deepstream-app -c "${APP_CFG}"
