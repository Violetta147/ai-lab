#!/usr/bin/env bash
# =============================================================================
# DeepStream RTSP-First Pipeline for Jetson Nano (DS 6.0.1) — v3 Enhanced
#
# Features:
#   - YOLOv8n FP16 detection (bus/car/motor/truck)
#   - Per-class bbox colors (green/blue/yellow/red)
#   - NvDCF tracker (accurate tracking through occlusion)
#   - nvdsanalytics: vehicle line-crossing counter
#   - RTSP input/output with configurable quality
#
# Input:  Laptop RTSP stream  -> Jetson DeepStream
# Output: Jetson RTSP stream  -> viewed/recorded on Laptop
#
# Usage:
#   LAPTOP_RTSP_URI=rtsp://192.168.1.154:8554/mystream bash setup_deepstream_jetson.sh
#
# Windows firewall (Admin PowerShell):
#   netsh advfirewall firewall add rule name="RTSP 8554" dir=in action=allow protocol=TCP localport=8554
# =============================================================================
set -euo pipefail

# ======================== CONFIGURATION ======================================

# --- Paths ---
WORK_DIR="${WORK_DIR:-$HOME/deepstream_yolo}"
DEEPSTREAM_YOLO_DIR="${DEEPSTREAM_YOLO_DIR:-$HOME/DeepStream-Yolo}"
CUDA_VER="${CUDA_VER:-10.2}"

# --- RTSP ---
LAPTOP_RTSP_URI="${LAPTOP_RTSP_URI:-}"
JETSON_RTSP_PORT="${JETSON_RTSP_PORT:-8555}"
JETSON_UDP_PORT="${JETSON_UDP_PORT:-5400}"
JETSON_RTSP_MOUNT="${JETSON_RTSP_MOUNT:-/ds-test}"

# --- Inference ---
PRE_CLUSTER_THRESHOLD="${PRE_CLUSTER_THRESHOLD:-0.25}"
NMS_IOU_THRESHOLD="${NMS_IOU_THRESHOLD:-0.45}"
# interval=N → inference every (N+1)th frame. Tracker fills gaps.
INFER_INTERVAL="${INFER_INTERVAL:-2}"

# --- Video Quality ---
STREAMMUX_WIDTH="${STREAMMUX_WIDTH:-1280}"
STREAMMUX_HEIGHT="${STREAMMUX_HEIGHT:-720}"
OUTPUT_BITRATE="${OUTPUT_BITRATE:-4000000}"

# --- Tracker: "iou" (fast/CPU) or "nvdcf" (accurate/GPU) ---
TRACKER_TYPE="${TRACKER_TYPE:-nvdcf}"

# --- Analytics: line-crossing vehicle counter ---
ENABLE_ANALYTICS="${ENABLE_ANALYTICS:-1}"
# Line crossing coordinates (x1;y1;x2;y2) in streammux resolution.
# Default: horizontal line at 60% height, spanning 10%-90% width.
LC_X1="${LC_X1:-$(( STREAMMUX_WIDTH * 10 / 100 ))}"
LC_Y1="${LC_Y1:-$(( STREAMMUX_HEIGHT * 60 / 100 ))}"
LC_X2="${LC_X2:-$(( STREAMMUX_WIDTH * 90 / 100 ))}"
LC_Y2="${LC_Y2:-$(( STREAMMUX_HEIGHT * 60 / 100 ))}"

# --- Control ---
RUN_PIPELINE="${RUN_PIPELINE:-1}"
SKIP_SOURCE_CHECK="${SKIP_SOURCE_CHECK:-0}"

# =============================================================================

ONNX_FILE="${WORK_DIR}/best_deepstream.onnx"
LABELS_FILE="${WORK_DIR}/labels.txt"
CUSTOM_LIB="${WORK_DIR}/libnvdsinfer_custom_impl_Yolo.so"
INFER_CFG="${WORK_DIR}/config_infer_primary_yolov8.txt"
APP_CFG="${WORK_DIR}/deepstream_app_yolov8_rtsp.txt"
ANALYTICS_CFG="${WORK_DIR}/config_nvdsanalytics.txt"

DS_DIR="/opt/nvidia/deepstream/deepstream-6.0"

echo "============================================"
echo "[INFO] DeepStream v3 Enhanced Pipeline"
echo "[INFO] WORK_DIR      = ${WORK_DIR}"
echo "[INFO] RTSP Source   = ${LAPTOP_RTSP_URI}"
echo "[INFO] Resolution    = ${STREAMMUX_WIDTH}x${STREAMMUX_HEIGHT}"
echo "[INFO] Tracker       = ${TRACKER_TYPE}"
echo "[INFO] Analytics     = $([ "${ENABLE_ANALYTICS}" = "1" ] && echo "ON (line@${LC_Y1}px)" || echo "OFF")"
echo "[INFO] Interval      = ${INFER_INTERVAL}"
echo "[INFO] Output bitrate= ${OUTPUT_BITRATE}"
echo "============================================"

# --- Validation ---
if [ -z "${LAPTOP_RTSP_URI}" ]; then
    echo "[ERROR] LAPTOP_RTSP_URI is empty."
    echo "  LAPTOP_RTSP_URI=rtsp://<LAPTOP_IP>:8554/mystream bash $0"
    exit 1
fi
[ ! -f "${ONNX_FILE}" ] && echo "[ERROR] Missing: ${ONNX_FILE}" && exit 1
[ ! -f "${LABELS_FILE}" ] && echo "[ERROR] Missing: ${LABELS_FILE}" && exit 1

# --- Source check ---
if [ "${SKIP_SOURCE_CHECK}" != "1" ]; then
    if command -v ffprobe >/dev/null 2>&1; then
        echo "[INFO] Probing RTSP source..."
        if ! ffprobe -rtsp_transport tcp -loglevel error -show_entries stream=codec_name \
             -of default=nw=1:nk=1 "${LAPTOP_RTSP_URI}" >/dev/null 2>&1; then
            echo "[ERROR] Cannot reach ${LAPTOP_RTSP_URI}"
            echo "  → Is MediaMTX running? Is FFmpeg pushing? Firewall open?"
            echo "  → Set SKIP_SOURCE_CHECK=1 to bypass."
            exit 1
        fi
        echo "[INFO] RTSP source OK."
    else
        echo "[WARN] ffprobe not found; skipping source probe."
    fi
fi

# --- DeepStream install hooks ---
echo "[INFO] Running DeepStream install hooks..."
cd "${DS_DIR}"
./install.sh
unset DISPLAY || true
rm -rf /root/.cache/gstreamer-1.0/
ldconfig

# --- Build custom YOLO parser ---
if [ ! -f "${CUSTOM_LIB}" ]; then
    echo "[INFO] Building YOLO parser library..."
    if [ ! -d "${DEEPSTREAM_YOLO_DIR}" ]; then
        git clone https://github.com/marcoslucianops/DeepStream-Yolo "${DEEPSTREAM_YOLO_DIR}"
    fi
    CUDA_VER="${CUDA_VER}" make -C "${DEEPSTREAM_YOLO_DIR}/nvdsinfer_custom_impl_Yolo"
    cp "${DEEPSTREAM_YOLO_DIR}/nvdsinfer_custom_impl_Yolo/libnvdsinfer_custom_impl_Yolo.so" "${CUSTOM_LIB}"
fi

# =============================================================================
# CONFIG: Inference (per-class colors & thresholds)
# =============================================================================
echo "[INFO] Writing inference config..."
cat > "${INFER_CFG}" << EOF
[property]
gpu-id=0
net-scale-factor=0.00392156862745098
model-color-format=0
onnx-file=${ONNX_FILE}
model-engine-file=${ONNX_FILE}_b1_gpu0_fp16.engine
labelfile-path=${LABELS_FILE}
batch-size=1
network-mode=2
num-detected-classes=4
interval=${INFER_INTERVAL}
gie-unique-id=1
process-mode=1
network-type=0
cluster-mode=2
maintain-aspect-ratio=1
parse-bbox-func-name=NvDsInferParseYolo
custom-lib-path=${CUSTOM_LIB}

## Class 0: bus — GREEN bbox
[class-attrs-0]
pre-cluster-threshold=0.25
nms-iou-threshold=${NMS_IOU_THRESHOLD}
topk=50
border-color=0.1;0.9;0.2;1

## Class 1: car — BLUE bbox
[class-attrs-1]
pre-cluster-threshold=0.25
nms-iou-threshold=${NMS_IOU_THRESHOLD}
topk=100
border-color=0.2;0.5;1.0;1

## Class 2: motor — YELLOW bbox (lower threshold for small objects)
[class-attrs-2]
pre-cluster-threshold=0.20
nms-iou-threshold=${NMS_IOU_THRESHOLD}
topk=100
border-color=1.0;0.9;0.1;1

## Class 3: truck — RED bbox
[class-attrs-3]
pre-cluster-threshold=0.25
nms-iou-threshold=${NMS_IOU_THRESHOLD}
topk=50
border-color=1.0;0.2;0.1;1
EOF

# =============================================================================
# CONFIG: Analytics (line-crossing counter)
# =============================================================================
if [ "${ENABLE_ANALYTICS}" = "1" ]; then
    echo "[INFO] Writing analytics config (line crossing at y=${LC_Y1})..."
    cat > "${ANALYTICS_CFG}" << EOF
[property]
enable=1
config-width=${STREAMMUX_WIDTH}
config-height=${STREAMMUX_HEIGHT}
osd-mode=2
display-font-size=14

## Line crossing counter — counts vehicles crossing this line.
## Adjust coordinates to match your camera angle.
## Format: x1;y1;x2;y2 (in streammux pixel coordinates)
[line-crossing-stream-0]
enable=1
line-crossing-Entry=${LC_X1};${LC_Y1};${LC_X2};${LC_Y2}
class-id=-1
extended=0
mode=balanced
LC-label-Entry=Vehicles Counted
EOF
fi

# =============================================================================
# CONFIG: Tracker
# =============================================================================
if [ "${TRACKER_TYPE}" = "nvdcf" ]; then
    TRACKER_LL_CFG="${DS_DIR}/samples/configs/deepstream-app/config_tracker_NvDCF_perf.yml"
    echo "[INFO] Tracker: NvDCF Performance (GPU-accelerated)"
else
    TRACKER_LL_CFG="${DS_DIR}/samples/configs/deepstream-app/config_tracker_IOU.yml"
    echo "[INFO] Tracker: IOU (CPU-only, lightweight)"
fi

# =============================================================================
# CONFIG: App pipeline
# =============================================================================
echo "[INFO] Writing app config..."
cat > "${APP_CFG}" << EOF
[application]
enable-perf-measurement=1
perf-measurement-interval-sec=5

[tiled-display]
enable=0

[source0]
enable=1
type=4
uri=${LAPTOP_RTSP_URI}
num-sources=1
gpu-id=0
select-rtp-protocol=4
rtsp-reconnect-interval-sec=5

[streammux]
gpu-id=0
batch-size=1
batched-push-timeout=40000
width=${STREAMMUX_WIDTH}
height=${STREAMMUX_HEIGHT}
enable-padding=0

[primary-gie]
enable=1
gpu-id=0
gie-unique-id=1
config-file=${INFER_CFG}

[tracker]
enable=1
ll-config-file=${TRACKER_LL_CFG}
tracker-width=${STREAMMUX_WIDTH}
tracker-height=${STREAMMUX_HEIGHT}
gpu-id=0
ll-lib-file=${DS_DIR}/lib/libnvds_nvmultiobjecttracker.so
enable-batch-process=1
display-tracking-id=1

[osd]
enable=1
gpu-id=0
border-width=4
text-size=18
text-color=1;1;1;1
text-bg-color=0.1;0.1;0.1;0.7
font=Serif
clock-text-size=14
clock-x-offset=20
clock-y-offset=20
clock-color=1;1;0;0
EOF

# --- Append analytics section if enabled ---
if [ "${ENABLE_ANALYTICS}" = "1" ]; then
    cat >> "${APP_CFG}" << EOF

[nvds-analytics]
enable=1
config-file=${ANALYTICS_CFG}
EOF
fi

# --- Append sink ---
cat >> "${APP_CFG}" << EOF

[sink0]
enable=1
type=4
codec=1
sync=0
bitrate=${OUTPUT_BITRATE}
rtsp-port=${JETSON_RTSP_PORT}
udp-port=${JETSON_UDP_PORT}
EOF

echo "============================================"
echo "[INFO] Config generation done."
echo "[INFO] Jetson RTSP output:"
echo "  rtsp://<JETSON_IP>:${JETSON_RTSP_PORT}${JETSON_RTSP_MOUNT}"
echo ""
echo "[INFO] Record on laptop:"
echo "  ffmpeg -rtsp_transport tcp -i rtsp://<JETSON_IP>:${JETSON_RTSP_PORT}${JETSON_RTSP_MOUNT} -c copy output.mp4"
echo ""
echo "[INFO] Features enabled:"
echo "  ✓ Per-class colors: bus=🟢 car=🔵 motor=🟡 truck=🔴"
echo "  ✓ Tracker: ${TRACKER_TYPE}"
[ "${ENABLE_ANALYTICS}" = "1" ] && echo "  ✓ Line crossing counter at y=${LC_Y1}px"
echo "============================================"

if [ "${RUN_PIPELINE}" = "1" ]; then
    echo "[INFO] Starting deepstream-app..."
    deepstream-app -c "${APP_CFG}"
else
    echo "[INFO] RUN_PIPELINE=0, skipping pipeline start."
fi
