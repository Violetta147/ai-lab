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
WORK_DIR="${WORK_DIR:-/workspace/deepstream_yolo26}"
DS_DIR="${DS_DIR:-/opt/nvidia/deepstream/deepstream-6.0}"

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

# RTSP source ports (cam1=8554, cam2=8556, cam3=8558, ...)
RTSP_BASE_PORT="${RTSP_BASE_PORT:-8554}"

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
batch-size=${NUM_SOURCES}
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
# =============================================================================
echo "[C2] Writing Kafka config..."
cat > "${KAFKA_CFG}" << EOF
bootstrap.servers=${KAFKA_BROKER}
EOF

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
for i in $(seq 0 $((NUM_SOURCES - 1))); do
    PORT=${RTSP_BASE_PORT}  # Keep port 8554 for ALL streams
    CAM_NUM=$((i + 1))
    cat >> "${APP_CFG}" << EOF

[source${i}]
enable=1
type=4
uri=rtsp://${LAPTOP_A_IP}:${PORT}/cam${CAM_NUM}
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
ll-config-file=${DS_DIR}/samples/configs/deepstream-app/config_tracker_NvDCF_perf.yml
enable-past-frame=1
display-tracking-id=1

[tiled-display]
enable=0

[osd]
enable=0

[sink0]
enable=1
type=6
msg-conv-config=${WORK_DIR}/nvmsgconv_c2_config.txt
msg-conv-payload-type=256
msg-conv-msg2p-lib=${WORK_DIR}/libnvds_msgconv_c2.so
msg-broker-proto-lib=${DS_DIR}/lib/libnvds_kafka_proto.so
msg-broker-conn-str=${LAPTOP_A_IP};9092;${KAFKA_TOPIC}
msg-broker-config=${KAFKA_CFG}

[sink1]
enable=1
type=1
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
