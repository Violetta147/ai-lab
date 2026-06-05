cmake_minimum_required(VERSION 3.16)
project(edge_server_cplusplus LANGUAGES CXX CUDA)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find packages
find_package(CUDA REQUIRED)
find_package(OpenCV REQUIRED)
find_package(CURL REQUIRED)

# Try finding Paho MQTT
find_package(paho-mqtt3c QUIET)

# Set up include directories
include_directories(
    include
    ${OpenCV_INCLUDE_DIRS}
    /usr/local/cuda/include
    /usr/include/aarch64-linux-gnu
    /usr/include/eigen3
)

# Fetch nlohmann_json
include(FetchContent)
FetchContent_Declare(json
    URL https://github.com/nlohmann/json/releases/download/v3.11.2/json.tar.xz
)
FetchContent_MakeAvailable(json)

# Fetch GoogleTest for tests
set(GTEST_VERSION v1.14.0)
FetchContent_Declare(
  googletest
  URL https://github.com/google/googletest/archive/refs/tags/${GTEST_VERSION}.zip
)
FetchContent_MakeAvailable(googletest)

# Define source files
set(SOURCES
    src/main.cpp
    src/filters/active_learning.cpp
    src/filters/rule_ood.cpp
    src/filters/publish_gate.cpp
    src/clients/mqtt_client.cpp
    src/clients/minio_client.cpp
    src/core/disk_writer_thread.cpp
    src/core/sync_thread.cpp
    src/utils/base64.cpp
    src/utils/dotenv.cpp
    # Inference files
    src/infer/yolo.cu
    src/infer/infer.cu
    src/infer/bt_byte_tracker.cpp
    src/infer/bt_strack.cpp
    src/infer/bt_kalman.cpp
)

# Executable
add_executable(edge_server ${SOURCES})

# Libraries to link
target_link_libraries(edge_server
    ${OpenCV_LIBS}
    nvinfer
    cudart
    paho-mqtt3c
    ${CURL_LIBRARIES}
    nlohmann_json::nlohmann_json
    pthread
)

# Tests
enable_testing()
include(GoogleTest)

add_executable(edge_server_tests
    tests/test_filters.cpp
    src/filters/active_learning.cpp
    src/filters/rule_ood.cpp
    src/filters/publish_gate.cpp
)

target_link_libraries(edge_server_tests
    ${OpenCV_LIBS}
    GTest::gtest GTest::gmock GTest::gtest_main
    nlohmann_json::nlohmann_json
)

gtest_discover_tests(edge_server_tests)
