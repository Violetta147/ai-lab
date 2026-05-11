#!/usr/bin/env bash
# =============================================================================
# C2 Center — DeepStream Multi-Stream Pipeline (ROI Version)
#
# Version optimized for Polygon ROI filtering at the Edge.
# Optimized for Jetson Nano (Headless, Batch=1, Hardware limits).
# =============================================================================
set -euo pipefail

# ======================== CONFIGURATION ======================================
# --- RCA Fix: Global Variable Sanitization ---
# Strip hidden Windows carriage returns (\r) from ALL environment variables
LAPTOP_A_IP=$(echo "${LAPTOP_A_IP:-172.16.1.162}" | tr -d '\r\n ')
NUM_SOURCES=$(echo "${NUM_SOURCES:-1}" | tr -d '\r\n ')
WORK_DIR=$(echo "${WORK_DIR:-$(pwd)}" | tr -d '\r\n ')
KAFKA_TOPIC=$(echo "${KAFKA_TOPIC:-c2_metadata}" | tr -d '\r\n ')
RTSP_PATHS=$(echo "${RTSP_PATHS:-}" | tr -d '\r\n ')

resolve_ds_dir() {
    local candidate_dir=""
    for candidate in /opt/nvidia/deepstream/deepstream-6.0.1-devel /opt/nvidia/deepstream/deepstream-6.0.1 /opt/nvidia/deepstream/deepstream-6.0; do
        if [ -d "${candidate}" ]; then candidate_dir="${candidate}"; break; fi
    done
    [ -z "${candidate_dir}" ] && candidate_dir="/opt/nvidia/deepstream/deepstream-6.0"
    echo "${candidate_dir}" | tr -d '\r\n '
}

DS_DIR="/opt/nvidia/deepstream/deepstream-6.0"
SAMPLES_DIR="${DS_DIR}/samples"

# Ensure the plugin is in a standard search path for dlopen
cp "${WORK_DIR}/libnvds_msgconv_c2.so" /usr/lib/libnvds_msgconv_c2.so 2>/dev/null || true

MODEL_NAME=$(echo "${MODEL_NAME:-yolo_all_exports_p2n_fine-tuning2_best}" | tr -d '\r\n ')
MODEL_ENGINE_FILE=$(echo "${WORK_DIR}/${MODEL_NAME}.engine" | tr -d '\r\n ')
MODEL_ONNX_FILE=$(echo "${WORK_DIR}/${MODEL_NAME}.onnx" | tr -d '\r\n ')
MODEL_LABELS_FILE=$(echo "${WORK_DIR}/${MODEL_NAME}_labels.txt" | tr -d '\r\n ')
CUSTOM_LIB_Y26=$(echo "${WORK_DIR}/libnvdsinfer_custom_impl_Yolo26.so" | tr -d '\r\n ')

KAFKA_BROKER=$(echo "${LAPTOP_A_IP}:9092" | tr -d '\r\n ')
RTSP_BASE_PORT=$(echo "${RTSP_BASE_PORT:-8554}" | tr -d '\r\n ')

INFER_CFG="${WORK_DIR}/config_infer_c2.txt"
ANALYTICS_CFG="${WORK_DIR}/config_nvdsanalytics_roi.txt"
KAFKA_CFG="${WORK_DIR}/cfg_kafka.txt"
NVMSGCONV_CFG="${WORK_DIR}/nvmsgconv_c2_config.txt"
APP_CFG="${WORK_DIR}/deepstream_c2_roi.txt"

mkdir -p "${WORK_DIR}/debug_payloads"

echo "[C2] ROI Version — Laptop A IP: ${LAPTOP_A_IP}, Sources: ${NUM_SOURCES}"

# --- Validation ---
[ ! -f "${MODEL_ONNX_FILE}" ] && echo "[ERROR] Missing ONNX: ${MODEL_ONNX_FILE}" && exit 1
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
network-mode=2
num-detected-classes=${MODEL_NUM_CLASSES}
interval=1
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
# CONFIG: nvdsanalytics (ROI)
# =============================================================================
echo "[C2] Writing Analytics ROI config..."
cat > "${ANALYTICS_CFG}" << EOF
[property]
enable=1
config-width=1920
config-height=1080
osd-display=0
EOF

for i in $(seq 0 $((NUM_SOURCES - 1))); do
    # ROI polygon coordinates at config-width=1920, config-height=1080.
    # SCHEMA CONTRACT: These values MUST match config/stream_profiles.json
    # on the backend.  Format: x1;y1;x2;y2;x3;y3;x4;y4
    # To update, edit BOTH this file AND stream_profiles.json.
    ROI_POINTS="759;306;1077;325;1477;957;292;917"

    # Try reading from shared config if jq is available
    PROFILE_FILE="${WORK_DIR}/../config/stream_profiles.json"
    if command -v jq &>/dev/null && [ -f "${PROFILE_FILE}" ]; then
        CAM_PATH="${RTSP_PATH_ARR[$i]:-muahe}"
        JQ_RESULT=$(jq -r --arg s "$CAM_PATH" '.streams[$s].roi_polygon // empty | map(tostring) | join(";")' "${PROFILE_FILE}" 2>/dev/null || true)
        if [ -n "${JQ_RESULT}" ]; then
            ROI_POINTS="${JQ_RESULT}"
            echo "[C2] Loaded ROI from stream_profiles.json for ${CAM_PATH}: ${ROI_POINTS}"
        fi
    fi

    cat >> "${ANALYTICS_CFG}" << EOF

[roi-filtering-stream-${i}]
enable=1
# Specific ROI from user request
roi-polygon-ROI_Area=${ROI_POINTS}
EOF
done

# =============================================================================
# CONFIG: nvmsgconv & Kafka
# =============================================================================
# Write files FIRST so realpath works
# Write files FIRST so realpath works
cat > "${NVMSGCONV_CFG}" << EOF
[property]
payload-type=257
msg2p-lib=/usr/lib/libnvds_msgconv_c2.so
msg2p-newapi=1
frame-interval=1
EOF

cat > "${KAFKA_CFG}" << EOF
[message-broker]
bootstrap.servers=${KAFKA_BROKER}
topic=${KAFKA_TOPIC}
EOF

# Now resolve absolute paths
NVMSGCONV_CFG_DST="$(realpath -m "${WORK_DIR}/nvmsgconv_c2_config.txt")"
MSGCONV_LIB_DST="$(realpath -m "${WORK_DIR}/libnvds_msgconv_c2.so")"
INFER_CFG_DST="$(realpath -m "${INFER_CFG}")"
ANALYTICS_CFG_DST="$(realpath -m "${ANALYTICS_CFG}")"
KAFKA_CFG_DST="$(realpath -m "${KAFKA_CFG}")"

echo "[C2] Writing app config..."
cat > "${APP_CFG}" << EOF
[application]
enable-perf-measurement=1
perf-measurement-interval-sec=5

[tiled-display]
enable=0

[osd]
enable=1
gpu-id=0
border-width=2
text-size=12
text-color=1;1;1;1
text-bg-color=0.3;0.3;0.3;1
font=Serif
show-clock=1
clock-x-offset=500
clock-y-offset=20
clock-text-size=12
process-mode=0

[streammux]
gpu-id=0
live-source=1
batch-size=1
width=640
height=640
batched-push-timeout=20000
nvbuf-memory-type=0

[primary-gie]
enable=1
gpu-id=0
gie-unique-id=1
config-file=${INFER_CFG_DST}

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
config-file=${ANALYTICS_CFG_DST}

[sink0]
enable=1
type=6
gpu-id=0
msg-conv-payload-type=257
msg-conv-msg2p-lib=/usr/lib/libnvds_msgconv_c2.so
msg-conv-msg2p-new-api=1
msg-conv-frame-interval=1
msg-broker-proto-lib=/opt/nvidia/deepstream/deepstream-6.0/lib/libnvds_kafka_proto.so
msg-broker-conn-str=${LAPTOP_A_IP};9092;${KAFKA_TOPIC}
msg-broker-config=${KAFKA_CFG_DST}
sync=0

[sink1]
enable=1
type=4
# RTSP Streaming (Annotated Video)
rtsp-port=8555
udp-port=5400
gpu-id=0
bitrate=4000000
iframeinterval=30
codec=1
# codec: 1=h264, 2=h265
sync=0
EOF

IFS=',' read -ra RTSP_PATH_ARR <<< "${RTSP_PATHS}"
for i in $(seq 0 $((NUM_SOURCES - 1))); do
    # Correctly handle empty array elements for default path
    CAM_PATH="${RTSP_PATH_ARR[$i]:-}"
    if [ -z "${CAM_PATH}" ]; then
        CAM_PATH="muahe"
    fi
    cat >> "${APP_CFG}" << EOF

[source${i}]
enable=1
type=4
uri=rtsp://${LAPTOP_A_IP}:${RTSP_BASE_PORT}/${CAM_PATH}
gpu-id=0
EOF
done

echo "[C2] Starting deepstream-app (ROI Mode)..."

# --- RCA Fix: Unix Line Endings ---
# Strip all Windows \r characters from generated configs before running
sed -i 's/\r//g' "${INFER_CFG}" "${APP_CFG}" "${KAFKA_CFG}" "${ANALYTICS_CFG}" "${NVMSGCONV_CFG_DST}" 2>/dev/null || true

# Using deepstream-app with the Inlined Golden Solution (Bypassing parser bug)
deepstream-app -c "${APP_CFG}"
