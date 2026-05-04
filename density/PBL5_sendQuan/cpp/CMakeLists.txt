cmake_minimum_required(VERSION 3.16)
project(DensityAnalysis CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── OpenCV ────────────────────────────────────────────────────────────────────
# On Jetson: sudo apt install libopencv-dev  or  use JetPack OpenCV
# On desktop: set OpenCV_DIR to your OpenCV build dir if needed
find_package(OpenCV REQUIRED COMPONENTS core dnn imgproc highgui videoio)
include_directories(${OpenCV_INCLUDE_DIRS})
message(STATUS "OpenCV version: ${OpenCV_VERSION}")

# ── Common header (header-only, included in each target) ─────────────────────
# density_common.h is the shared infrastructure (no compiled object needed)

# ── Target 1: Absolute Count ──────────────────────────────────────────────────
add_executable(density_absolute density_absolute_count.cpp)
target_link_libraries(density_absolute ${OpenCV_LIBS})

# ── Target 2: Area Occupancy (BEV) ───────────────────────────────────────────
add_executable(density_area density_area_occupancy.cpp)
target_link_libraries(density_area ${OpenCV_LIBS})

# ── Target 3: Fundamental Equation (k = q/v) ─────────────────────────────────
add_executable(density_fundamental density_fundamental_equation.cpp)
target_link_libraries(density_fundamental ${OpenCV_LIBS})

# ── Target 4: PCE-Aware Density ───────────────────────────────────────────────
add_executable(density_pce density_pce_aware.cpp)
target_link_libraries(density_pce ${OpenCV_LIBS})

# ── CUDA backend hint (Jetson) ────────────────────────────────────────────────
# OpenCV DNN automatically uses DNN_BACKEND_CUDA if OpenCV was built with CUDA.
# On Jetson Nano / JetPack 4.6 this is included in the OpenCV 4.x system package.
# Verify with: python3 -c "import cv2; print(cv2.cuda.getCudaEnabledDeviceCount())"

# ── Optional: Release build flags ────────────────────────────────────────────
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()
target_compile_options(density_absolute    PRIVATE -O2)
target_compile_options(density_area        PRIVATE -O2)
target_compile_options(density_fundamental PRIVATE -O2)
target_compile_options(density_pce         PRIVATE -O2)
