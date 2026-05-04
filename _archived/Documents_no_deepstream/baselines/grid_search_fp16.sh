#!/bin/bash
set -euo pipefail

# Grid search tự động cho FP16 trên Jetson Nano.
# Bạn có thể để máy chạy qua đêm, kết quả sẽ được ghi vào:
#   - baselines/runs/scoreboard.csv
#   - mỗi run vẫn có summary riêng.
#
# Tham số chính:
# - WORKSPACES_MB: các giá trị workspace thử
# - STREAMS_LIST:  số streams cho trtexec (1 = latency, 2 = throughput)
#
# Lưu ý:
# - Mặc định dùng cùng ONNX / build_engine.sh như bạn đang dùng.
# - Mỗi cấu hình sẽ build 1 engine riêng trong baselines/engines/candidates/.

BASE_DIR="/home/jetson/Documents/baselines"
ENGINES_DIR="$BASE_DIR/engines/candidates"
CACHES_DIR="$BASE_DIR/caches"
mkdir -p "$ENGINES_DIR" "$CACHES_DIR"

ONNX_PATH="${ONNX_PATH:-/home/jetson/Documents/yolov8n.transd.onnx}"

# Không nên quá nhiều tổ hợp trên Nano, giữ grid nhỏ trước
WORKSPACES_MB=(${WORKSPACES_MB:-512 1024 1536})
STREAMS_LIST=(${STREAMS_LIST:-1 2})

echo "=== GRID SEARCH FP16 START ==="
echo "ONNX_PATH   : $ONNX_PATH"
echo "WORKSPACES  : ${WORKSPACES_MB[*]}"
echo "STREAMS     : ${STREAMS_LIST[*]}"
echo

run_id=0
for ws in "${WORKSPACES_MB[@]}"; do
  # Một timing cache cho mỗi ws để build nhanh các biến thể sau
  cache_file="$CACHES_DIR/y8_fp16_ws${ws}.cache"

  for streams in "${STREAMS_LIST[@]}"; do
    run_id=$((run_id + 1))
    engine_name="y8_fp16_ws${ws}_s${streams}.engine"
    engine_path="$ENGINES_DIR/$engine_name"

    echo "[$run_id] === Config: ws=${ws}MB, streams=${streams} ==="
    echo "Engine : $engine_path"
    echo "Cache  : $cache_file"

    # 1) Build engine (FP16) với timing cache
    PRECISION=fp16 \
    ONNX_PATH="$ONNX_PATH" \
    ENGINE_OUT="$engine_path" \
    WORKSPACE_MB="$ws" \
    TIMING_CACHE_FILE="$cache_file" \
    bash "$BASE_DIR/build_engine.sh"

    # 2) Benchmark engine so với baseline fp32_ws1024
    echo
    echo ">>> Benchmark TEST_ENGINE=$engine_path với streams=$streams"
    TEST_ENGINE="$engine_path" \
    TRT_STREAMS="$streams" \
    bash "$BASE_DIR/run_pipeline.sh"

    echo
    echo "=== DONE config ws=${ws}, streams=${streams} ==="
    echo
    # (Tuỳ bạn có muốn nghỉ giữa các run để hạ nhiệt hay không)
    sleep 3
  done
done

echo "=== GRID SEARCH FP16 DONE ==="
echo "Xem tổng hợp tại: $BASE_DIR/runs/scoreboard.csv"

