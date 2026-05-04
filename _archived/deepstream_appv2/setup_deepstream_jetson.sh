#!/bin/bash

# ==============================================================================
# Script setup và chạy DeepStream Minimal (v3.1 - FIX CUDA LINKING)
# ==============================================================================

echo "[BUILD] Đang biên dịch ứng dụng Minimal..."

# 1. Các Include Path (Dùng cho cả Host và Docker)
INC="-I/usr/include/gstreamer-1.0 "
INC+="-I/usr/include/glib-2.0 "
INC+="-I/usr/lib/aarch64-linux-gnu/glib-2.0/include "
INC+="-I/usr/local/cuda/include "

# 2. Các Library Path (Tìm thư viện CUDA)
LIB_PATH="-L/usr/local/cuda/lib64 "
LIB_PATH+="-L/usr/local/cuda/lib "
LIB_PATH+="-L/usr/lib/aarch64-linux-gnu "

# 3. Các thư viện cần link
LIBS="-lgstreamer-1.0 -lglib-2.0 -lgobject-2.0 -lcudart -lstdc++"

g++ -o minimal_ds \
    main_ds.cpp \
    ${INC} \
    ${LIB_PATH} \
    ${LIBS}

if [ $? -eq 0 ]; then
    echo "[SUCCESS] Biên dịch thành công: minimal_ds"
    echo "Lệnh chạy: ./minimal_ds"
else
    echo "[ERROR] Biên dịch thất bại!"
    echo "Gợi ý: Nếu chạy ngoài Host, hãy kiểm tra: ls /usr/local/cuda/lib64/libcudart.so"
    exit 1
fi
