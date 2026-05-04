#!/bin/bash

# ==============================================================================
# Script setup và chạy DeepStream Traffic Analyzer (v2.0)
# Tương thích: DeepStream 6.0.1, Jetson Nano
# ==============================================================================

# 1. Biến môi trường cho Profiling
export NVDS_ENABLE_LATENCY_MEASUREMENT=1
export NVDS_ENABLE_COMPONENT_LATENCY_MEASUREMENT=1
export PIPELINE_PROFILE=1

echo "[SETUP] Đang thiết lập môi trường cho Jetson Nano..."
sudo nvpmodel -m 0
sudo jetson_clocks

# 2. Compile App mới (main_ds.cpp)
echo "[BUILD] Đang biên dịch ứng dụng DeepStream mới..."
g++ -o traffic_analyzer_ds \
    jetson/Documents/infer/deepstream_app/src/main_ds.cpp \
    jetson/Documents/infer/src/traffic_analyzer.cpp \
    -I/opt/nvidia/deepstream/deepstream/sources/includes \
    -I/usr/local/cuda/include \
    -Ijetson/Documents/infer/src \
    `pkg-config --cflags --libs gstreamer-1.0 opencv4` \
    -L/opt/nvidia/deepstream/deepstream/lib/ -lnvdsgst_meta -lnvds_meta -lnvds_analytics_meta -lcudart

if [ $? -eq 0 ]; then
    echo "[SUCCESS] Biên dịch thành công: traffic_analyzer_ds"
else
    echo "[ERROR] Biên dịch thất bại!"
    exit 1
fi

# 3. Chạy thử nghiệm
echo "[RUN] Bạn muốn chạy gì?"
echo "1. Chạy App Traffic Analyzer mới (Webcam)"
echo "2. Chạy Sample Test 1 với Profiling (File .h264)"
read -p "Lựa chọn của bạn (1/2): " choice

if [ "$choice" == "1" ]; then
    echo "[INFO] Đang chạy Traffic Analyzer DS..."
    ./traffic_analyzer_ds
elif [ "$choice" == "2" ]; then
    # Compile Sample Test 1 Profile
    gcc -o ds_test1_profile \
        jetson/apps/sample_apps/deepstream-test1/deepstream_test1_profiling.c \
        -I/opt/nvidia/deepstream/deepstream/sources/includes \
        -I/usr/local/cuda/include \
        `pkg-config --cflags --libs gstreamer-1.0` \
        -L/opt/nvidia/deepstream/deepstream/lib/ -lnvdsgst_meta -lnvds_meta -lcudart
    
    echo "[INFO] Đang chạy Sample Test 1 Profile..."
    ./ds_test1_profile /opt/nvidia/deepstream/deepstream/samples/streams/sample_720p.h264
fi
