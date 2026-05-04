#!/bin/bash

# ==============================================================================
# DeepStream Dirty Build Script (v4.0 - DIRECT LINKING)
# Designed for building inside a Samples container without internet.
# ==============================================================================

echo "[BUILD] Performing Dirty Build inside Docker..."

# 1. Borrow Headers from Host (Mounted at /host/usr/include)
HOST_INC="/host/usr/include"
HOST_LIB_INC="/host/usr/lib/aarch64-linux-gnu"

# 2. Direct paths to Docker's internal libraries (No -l required)
# We point to the .so.0 files directly because the .so symlinks are missing.
GST_SO="/usr/lib/aarch64-linux-gnu/libgstreamer-1.0.so.0"
GLIB_SO="/usr/lib/aarch64-linux-gnu/libglib-2.0.so.0"
GOBJ_SO="/usr/lib/aarch64-linux-gnu/libgobject-2.0.so.0"
CUDA_SO="/usr/local/cuda/lib64/libcudart.so"

# 3. Include Paths (Standard GStreamer + GLib)
INC="-I. "
INC+="-I${HOST_INC}/gstreamer-1.0 "
INC+="-I${HOST_INC}/glib-2.0 "
INC+="-I${HOST_LIB_INC}/glib-2.0/include "
INC+="-I/usr/local/cuda/include "

echo "[BUILD] Compiling..."

g++ -o minimal_ds_docker \
    main_ds.cpp \
    ${INC} \
    ${GST_SO} ${GLIB_SO} ${GOBJ_SO} ${CUDA_SO} \
    -lstdc++

if [ $? -eq 0 ]; then
    echo "--------------------------------------------------------"
    echo "[SUCCESS] Dirty Build successful: minimal_ds_docker"
    echo "Run it now: ./minimal_ds_docker"
    echo "--------------------------------------------------------"
else
    echo "[ERROR] Build failed! Check if the paths to .so.0 are correct."
    exit 1
fi
