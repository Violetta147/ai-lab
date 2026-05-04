#!/bin/bash

# ==============================================================================
# Script setup và chạy DeepStream Traffic Analyzer (v2.5 - SUPER ROBUST)
# Sửa lỗi thiếu GStreamer, OpenCV và Eigen3 trong Docker
# ==============================================================================

echo "[1/3] Kiểm tra và cài đặt thư viện phát triển..."
# Cố gắng cài đặt các gói dev nếu có mạng
apt-get update
apt-get install -y libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libglib2.0-dev \
                   libopencv-dev libeigen-dev pkg-config

# 2. Xác định đường dẫn DeepStream
DS_DIR="/opt/nvidia/deepstream/deepstream-6.0"
DS_INC="${DS_DIR}/sources/includes"

# 3. Định nghĩa thủ công các Include Path (Phòng trường hợp pkg-config lỗi)
GST_INC="-I/usr/include/gstreamer-1.0 -I/usr/include/glib-2.0 -I/usr/lib/aarch64-linux-gnu/glib-2.0/include"
OCV_INC="-I/usr/include/opencv4 -I/usr/include/opencv"
EIGEN_INC="-I/usr/include/eigen3"
CUDA_INC="-I/usr/local/cuda/include"

echo "[2/3] Đang biên dịch ứng dụng..."

g++ -o traffic_analyzer_ds \
    main_ds.cpp \
    traffic_analyzer.cpp \
    bt_byte_tracker.cpp \
    bt_kalman.cpp \
    bt_strack.cpp \
    -I. \
    -I${DS_INC} \
    -I${DS_INC}/cvcore \
    ${GST_INC} \
    ${OCV_INC} \
    ${EIGEN_INC} \
    ${CUDA_INC} \
    `pkg-config --libs gstreamer-1.0 gstreamer-video-1.0 opencv4` \
    -L${DS_DIR}/lib/ \
    -lnvdsgst_meta -lnvds_meta -lnvds_analytics_meta -lcudart -lstdc++

if [ $? -eq 0 ]; then
    echo "[3/3] [SUCCESS] Biên dịch thành công: traffic_analyzer_ds"
    echo "--------------------------------------------------------"
    echo "Lệnh chạy: ./traffic_analyzer_ds"
else
    echo "[ERROR] Biên dịch thất bại!"
    echo "Gợi ý: Nếu vẫn thiếu Eigen, hãy copy folder eigen3 từ máy Host vào đây."
    exit 1
fi
