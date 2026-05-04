#!/usr/bin/env bash
# =============================================================================
# DeepStream RTSP-First Pipeline for Jetson Nano (DS 6.0.1)
#
# Input:  Laptop RTSP stream  -> Jetson DeepStream
# Output: Jetson RTSP stream  -> viewed/recorded on Laptop
# Record policy: MP4 is recorded on laptop by FFmpeg (not on Jetson)
#
# PREREQUISITE (Laptop): you MUST run a real RTSP server and publish a stream.
#   Plain "ffmpeg ... -f rtsp rtsp://localhost:8554/mystream" only works if an
#   RTSP server is listening on that host:port (e.g. MediaMTX, rtsp-simple-server).
#   DeepStream on Jetson then uses source0 type=4 uri=<that RTSP URL>.
#
# Windows firewall (Laptop, Admin PowerShell) — allow inbound RTSP server port:
#   netsh advfirewall firewall add rule name="RTSP Server 8554 TCP" dir=in action=allow protocol=TCP localport=8554
# Optional if you still want Jetson->Laptop ping to work:
#   netsh advfirewall firewall add rule name="ICMPv4 Allow Ping" protocol=icmpv4:8,any dir=in action=allow
#
# Verify from Jetson (after RTSP server is up): prefer ffprobe over curl for RTSP.
#   ffprobe -rtsp_transport tcp -loglevel error -show_entries stream=codec_name -of default=nw=1:nk=1 "rtsp://<LAPTOP_IP>:8554/mystream"
# =============================================================================
set -euo pipefail

# -------------------------- CONFIGURATION -------------------------------------
WORK_DIR="${WORK_DIR:-$HOME/deepstream_yolo}"
DEEPSTREAM_YOLO_DIR="${DEEPSTREAM_YOLO_DIR:-$HOME/DeepStream-Yolo}"
CUDA_VER="${CUDA_VER:-10.2}"

# REQUIRED: RTSP URL on the laptop (or LAN) that Jetson can reach, e.g.:
#   rtsp://192.168.55.100:8554/mystream   (USB RNDIS)
#   rtsp://192.168.1.154:8554/mystream    (same Wi-Fi/LAN as Jetson)
LAPTOP_RTSP_URI="${LAPTOP_RTSP_URI:-}"
JETSON_RTSP_PORT="${JETSON_RTSP_PORT:-8555}"
JETSON_UDP_PORT="${JETSON_UDP_PORT:-5400}"
# deepstream-app RTSP sink on DS 6.0.1 defaults to /ds-test.
JETSON_RTSP_MOUNT="${JETSON_RTSP_MOUNT:-/ds-test}"

PRE_CLUSTER_THRESHOLD="${PRE_CLUSTER_THRESHOLD:-0.25}"
NMS_IOU_THRESHOLD="${NMS_IOU_THRESHOLD:-0.45}"
# interval=N → run inference every (N+1)th frame; tracker fills gaps.
# 0=every frame (GPU-heavy), 1=every 2nd, 2=every 3rd (recommended for Nano)
INFER_INTERVAL="${INFER_INTERVAL:-2}"

# Video quality: higher = sharper but more GPU. 30 FPS is easy at 720p.
STREAMMUX_WIDTH="${STREAMMUX_WIDTH:-1280}"
STREAMMUX_HEIGHT="${STREAMMUX_HEIGHT:-720}"
OUTPUT_BITRATE="${OUTPUT_BITRATE:-4000000}"

RUN_PIPELINE="${RUN_PIPELINE:-1}"
# Set to 1 to skip ffprobe check against LAPTOP_RTSP_URI (not recommended).
SKIP_SOURCE_CHECK="${SKIP_SOURCE_CHECK:-0}"
# -----------------------------------------------------------------------------

ONNX_FILE="${WORK_DIR}/best_deepstream.onnx"
LABELS_FILE="${WORK_DIR}/labels.txt"
CUSTOM_LIB="${WORK_DIR}/libnvdsinfer_custom_impl_Yolo.so"
INFER_CFG="${WORK_DIR}/config_infer_primary_yolov8.txt"
APP_CFG="${WORK_DIR}/deepstream_app_yolov8_rtsp.txt"
TRACKER_CFG="/opt/nvidia/deepstream/deepstream-6.0/samples/configs/deepstream-app/config_tracker_NvDCF_perf.yml"

echo "============================================"
echo "[DEBUG] DeepStream RTSP-first setup starting"
echo "[DEBUG] WORK_DIR=${WORK_DIR}"
echo "[DEBUG] LAPTOP_RTSP_URI=${LAPTOP_RTSP_URI}"
echo "[DEBUG] JETSON_RTSP_PORT=${JETSON_RTSP_PORT}"
echo "============================================"

if [ -z "${LAPTOP_RTSP_URI}" ]; then
    echo "[ERROR] LAPTOP_RTSP_URI is empty."
    echo "Set it when running this script, e.g.:"
    echo "  LAPTOP_RTSP_URI=rtsp://192.168.55.100:8554/mystream bash $0"
    exit 1
fi

if [ ! -f "${ONNX_FILE}" ]; then
    echo "[ERROR] Missing ONNX file: ${ONNX_FILE}"
    exit 1
fi
if [ ! -f "${LABELS_FILE}" ]; then
    echo "[ERROR] Missing labels file: ${LABELS_FILE}"
    exit 1
fi

if [ "${SKIP_SOURCE_CHECK}" != "1" ]; then
    if command -v ffprobe >/dev/null 2>&1; then
        echo "[DEBUG] Probing laptop RTSP source (ffprobe)..."
        if ! ffprobe -rtsp_transport tcp -loglevel error -show_entries stream=codec_name -of default=nw=1:nk=1 "${LAPTOP_RTSP_URI}" >/dev/null 2>&1; then
            echo "[ERROR] ffprobe failed for LAPTOP_RTSP_URI=${LAPTOP_RTSP_URI}"
            echo "Fix: start RTSP server + publish stream on laptop, open Windows firewall TCP 8554, then retry."
            echo "Or set SKIP_SOURCE_CHECK=1 to bypass this check."
            exit 1
        fi
        echo "[DEBUG] ffprobe OK for laptop RTSP source."
    else
        echo "[WARNING] ffprobe not found in PATH; skipping RTSP source probe."
        echo "Install ffmpeg/ffprobe in the container or use SKIP_SOURCE_CHECK=1."
    fi
fi

echo "[DEBUG] Running DeepStream install hooks..."
cd /opt/nvidia/deepstream/deepstream-6.0
./install.sh
unset DISPLAY || true
rm -rf /root/.cache/gstreamer-1.0/
ldconfig

if [ ! -f "${CUSTOM_LIB}" ]; then
    echo "[DEBUG] Custom parser library not found in ${WORK_DIR}, building..."
    if [ ! -d "${DEEPSTREAM_YOLO_DIR}" ]; then
        git clone https://github.com/marcoslucianops/DeepStream-Yolo "${DEEPSTREAM_YOLO_DIR}"
    fi
    CUDA_VER="${CUDA_VER}" make -C "${DEEPSTREAM_YOLO_DIR}/nvdsinfer_custom_impl_Yolo"
    cp "${DEEPSTREAM_YOLO_DIR}/nvdsinfer_custom_impl_Yolo/libnvdsinfer_custom_impl_Yolo.so" "${CUSTOM_LIB}"
fi

echo "[DEBUG] Writing inference config: ${INFER_CFG}"
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

[class-attrs-all]
nms-iou-threshold=${NMS_IOU_THRESHOLD}
pre-cluster-threshold=${PRE_CLUSTER_THRESHOLD}
topk=100
EOF

echo "[DEBUG] Writing app config: ${APP_CFG}"
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
## Force TCP for RTP transport (0=UDP, 4=TCP).
## Must match MediaMTX rtspTransports setting.
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
## IOU tracker runs on CPU (idle ~20%), freeing GPU.
ll-config-file=/opt/nvidia/deepstream/deepstream-6.0/samples/configs/deepstream-app/config_tracker_IOU.yml
tracker-width=${STREAMMUX_WIDTH}
tracker-height=${STREAMMUX_HEIGHT}
gpu-id=0
ll-lib-file=/opt/nvidia/deepstream/deepstream-6.0/lib/libnvds_nvmultiobjecttracker.so
enable-batch-process=1

[osd]
enable=1
gpu-id=0
border-width=3
text-size=15
text-color=1;1;1;1
text-bg-color=0.2;0.2;0.2;0.8
font=Serif

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
echo "[DEBUG] Config generation done."
echo "[DEBUG] Jetson RTSP output URL:"
echo "[DEBUG]   rtsp://<JETSON_IP>:${JETSON_RTSP_PORT}${JETSON_RTSP_MOUNT}"
echo ""
echo "[DEBUG] Record on laptop with FFmpeg:"
echo "ffmpeg -rtsp_transport tcp -i rtsp://<JETSON_IP>:${JETSON_RTSP_PORT}${JETSON_RTSP_MOUNT} -c copy output_jetson_processed.mp4"
echo "============================================"

if [ "${RUN_PIPELINE}" = "1" ]; then
    echo "[DEBUG] Starting deepstream-app..."
    deepstream-app -c "${APP_CFG}"
else
    echo "[DEBUG] RUN_PIPELINE=${RUN_PIPELINE}, skip pipeline start."
fi
