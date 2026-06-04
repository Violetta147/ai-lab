#!/bin/bash
set -euo pipefail

# ===== Cấu hình mặc định =====
# Baseline engine (fp32 ws1024) build sẵn và dùng lại mãi mãi
BASELINE_ENGINE="/home/jetson/Documents/baselines/engines/baseline/yolov8n_fp32_ws1024.engine"
# Engine đem đi benchmark (mặc định = baseline; có thể export TEST_ENGINE=... khi chạy)
TEST_ENGINE="${TEST_ENGINE:-$BASELINE_ENGINE}"

# trtexec options (benchmark-only)
TRT_WARMUP="${TRT_WARMUP:-200}"
TRT_DURATION_SEC="${TRT_DURATION_SEC:-10}"
TRT_STREAMS="${TRT_STREAMS:-1}"

# Baseline GPU (thuần GPU)
GPU_BASELINE_CMD=(
  trtexec
  --loadEngine="$BASELINE_ENGINE"
  --streams="$TRT_STREAMS"
  --warmUp="$TRT_WARMUP"
  --duration="$TRT_DURATION_SEC"
)

# Test GPU (thuần GPU) cho engine ứng viên
GPU_TEST_CMD=(
  trtexec
  --loadEngine="$TEST_ENGINE"
  --streams="$TRT_STREAMS"
  --warmUp="$TRT_WARMUP"
  --duration="$TRT_DURATION_SEC"
)

# End-to-End C++
CPP_APP_DIR="/home/jetson/Documents/infer"
CPP_CMD=("./main" "camera")
CPP_DURATION_SEC=30

# ===== Tự động hoá =====
BASE_DIR="/home/jetson/Documents/baselines"
LOG_DIR="$BASE_DIR/logs"
RUN_DIR="$BASE_DIR/runs"
mkdir -p "$LOG_DIR" "$RUN_DIR"

TS="$(date +%Y-%m-%d_%H-%M-%S)"
GPU_BASELINE_LOG="$LOG_DIR/${TS}_gpu_baseline_trtexec.log"
GPU_TEST_LOG="$LOG_DIR/${TS}_gpu_test_trtexec.log"
CPP_LOG="$LOG_DIR/${TS}_e2e_cpp.log"
TG_LOG="$LOG_DIR/${TS}_tegrastats.log"

# Đảm bảo luôn tắt tegrastats kể cả khi script bị Ctrl+C hoặc lỗi giữa chừng
TG_PID=""
stop_tegrastats() {
  # Ưu tiên kill đúng PID do script spawn; fallback pkill nếu cần
  if [ -n "${TG_PID:-}" ] && ps -p "${TG_PID}" >/dev/null 2>&1; then
    echo "==> Stop tegrastats (trap)"
    if sudo -n true >/dev/null 2>&1; then
      sudo -n kill "$TG_PID" >/dev/null 2>&1 || true
    else
      kill "$TG_PID" >/dev/null 2>&1 || true
    fi
  fi
  if pgrep -f tegrastats >/dev/null 2>&1; then
    if sudo -n true >/dev/null 2>&1; then
      sudo -n pkill -f tegrastats >/dev/null 2>&1 || true
    else
      pkill -f tegrastats >/dev/null 2>&1 || true
    fi
  fi
}
trap stop_tegrastats EXIT INT TERM

echo "==> [1/4] Baseline GPU (trtexec)"
("${GPU_BASELINE_CMD[@]}") | tee "$GPU_BASELINE_LOG"

echo "==> [2/4] Test GPU (trtexec)"
("${GPU_TEST_CMD[@]}") | tee "$GPU_TEST_LOG"

echo "==> [3/4] End-to-end C++ (camera) - test engine"
echo "==> Start tegrastats"
if command -v tegrastats >/dev/null 2>&1; then
  if sudo -n true >/dev/null 2>&1; then
    sudo -n tegrastats --interval 1000 > "$TG_LOG" &
    TG_PID=$!
  else
    tegrastats --interval 1000 > "$TG_LOG" &
    TG_PID=$!
  fi
else
  echo "tegrastats not found; skip logging."
fi
(
  if cd "$CPP_APP_DIR"; then
    echo "Running C++ app in $(pwd)..."
    PIPELINE_ENGINE="$TEST_ENGINE" stdbuf -oL timeout "${CPP_DURATION_SEC}s" "${CPP_CMD[@]}" 2>&1 || true
  else
    echo "ERROR: Không thể truy cập thư mục $CPP_APP_DIR" 2>&1
  fi
) | tee "$CPP_LOG"

echo "==> Stop tegrastats"
stop_tegrastats

echo "==> Summary"
SUMMARY_FILE="$RUN_DIR/${TS}_summary.txt"

parse_trtexec() {
  local log="$1"
  local prefix="$2"

  local tput mean p99 mem

  # Không cần match [I], chỉ cần từ khoá để tránh lỗi escape
  tput="$(awk '/Throughput:/ {print $4; exit}' "$log")"

  mean="$(
    awk '/Latency: min =/{
      for(i=1;i<=NF;i++) if($i=="mean") {print $(i+2); exit}
    }' "$log"
  )"
  mean="${mean%ms}"

  p99="$(
    awk '/Latency: min =/{
      for(i=1;i<=NF;i++){
        if($i ~ /^percentile\(99%\)/){
          print $(i+2);
          exit
        }
      }
    }' "$log"
  )"
  p99="${p99%ms}"

  mem="$(awk '/Device Global Memory:/ {print $(NF-1); exit}' "$log")"

  eval "${prefix}_throughput=\"${tput}\""
  eval "${prefix}_lat_mean=\"${mean}\""
  eval "${prefix}_lat_p99=\"${p99}\""
  eval "${prefix}_gpu_mem_total_mib=\"${mem}\""
}

parse_trtexec "$GPU_BASELINE_LOG" baseline
parse_trtexec "$GPU_TEST_LOG" test

improve_stats="$(
  BASE_TPUT="${baseline_throughput:-}" CURR_TPUT="${test_throughput:-}" \
  BASE_LAT="${baseline_lat_mean:-}" CURR_LAT="${test_lat_mean:-}" \
  BASE_P99="${baseline_lat_p99:-}" CURR_P99="${test_lat_p99:-}" \
  python3 - <<'PY'
import os

def f(x):
    try:
        return float(x)
    except Exception:
        return None

bt, ct = f(os.getenv("BASE_TPUT","")), f(os.getenv("CURR_TPUT",""))
bl, cl = f(os.getenv("BASE_LAT","")), f(os.getenv("CURR_LAT",""))
bp, cp = f(os.getenv("BASE_P99","")), f(os.getenv("CURR_P99",""))

def delta_pct(curr, base):
    if curr is None or base is None or base == 0:
        return ("", "")
    d = curr - base
    p = (curr / base - 1.0) * 100.0
    return (f"{d:.3f}", f"{p:.1f}")

def improve_latency(curr, base):
    # dương = giảm (tốt)
    if curr is None or base is None or curr == 0:
        return ("", "")
    d = base - curr
    p = (base / curr - 1.0) * 100.0
    return (f"{d:.3f}", f"{p:.1f}")

tput_d, tput_p = delta_pct(ct, bt)
lat_d, lat_p = improve_latency(cl, bl)
p99_d, p99_p = improve_latency(cp, bp)

print(f"tput_gain_abs={tput_d}")
print(f"tput_gain_pct={tput_p}")
print(f"lat_gain_abs={lat_d}")
print(f"lat_gain_pct={lat_p}")
print(f"p99_gain_abs={p99_d}")
print(f"p99_gain_pct={p99_p}")
PY
)"
eval "$improve_stats"

cpp_line="$(awk '/Camera FPS:/{line=$0} END{print line}' "$CPP_LOG")"
cpp_cam="$(echo "$cpp_line" | awk -F'[:|]' '{gsub(/ /,"",$2); print $2}')"
cpp_model="$(echo "$cpp_line" | awk -F'[:|]' '{gsub(/ /,"",$4); print $4}')"
cpp_infer="$(echo "$cpp_line" | awk -F'[:|]' '{gsub(/ /,"",$6); print $6}')"

stats="$(
  python3 - "$TG_LOG" <<'PY'
import re
import sys

path = sys.argv[1]
data = open(path, "r", errors="ignore").read().splitlines()

ram_peak = swap_peak = None
gr3d_sum = emc_sum = cpu_sum = 0.0
gr3d_n = emc_n = cpu_n = 0

def update_peak(val, cur):
    return val if cur is None or val > cur else cur

temp_cpu = []
temp_gpu = []
temp_ao = []
temp_th = []
pw_in = []
pw_gpu = []
pw_cpu = []

for line in data:
    m = re.search(r"RAM (\d+)/\d+MB", line)
    if m:
        ram_peak = update_peak(int(m.group(1)), ram_peak)

    m = re.search(r"SWAP (\d+)/\d+MB", line)
    if m:
        swap_peak = update_peak(int(m.group(1)), swap_peak)

    m = re.search(r"GR3D_FREQ (\d+)%", line)
    if m:
        gr3d_sum += float(m.group(1))
        gr3d_n += 1

    m = re.search(r"EMC_FREQ (\d+)%", line)
    if m:
        emc_sum += float(m.group(1))
        emc_n += 1

    m = re.search(r"CPU \[([^\]]+)\]", line)
    if m:
        parts = m.group(1).split(',')
        for p in parts:
            p = p.strip()
            p = p.split('%')[0]
            if p.isdigit():
                cpu_sum += float(p)
                cpu_n += 1

    m = re.search(r"CPU@([0-9.]+)C", line)
    if m:
        temp_cpu.append(float(m.group(1)))

    m = re.search(r"GPU@([0-9.]+)C", line)
    if m:
        temp_gpu.append(float(m.group(1)))

    m = re.search(r"AO@([0-9.]+)C", line)
    if m:
        temp_ao.append(float(m.group(1)))

    m = re.search(r"thermal@([0-9.]+)C", line)
    if m:
        temp_th.append(float(m.group(1)))

    m = re.search(r"POM_5V_IN (\d+)", line)
    if m:
        pw_in.append(float(m.group(1)))

    m = re.search(r"POM_5V_GPU (\d+)", line)
    if m:
        pw_gpu.append(float(m.group(1)))

    m = re.search(r"POM_5V_CPU (\d+)", line)
    if m:
        pw_cpu.append(float(m.group(1)))

def avg(lst):
    return sum(lst) / len(lst) if lst else None

def fmt(v):
    return "" if v is None else ("%.1f" % v if isinstance(v, float) else str(v))

print(f"ram_peak={'' if ram_peak is None else ram_peak}")
print(f"swap_peak={'' if swap_peak is None else swap_peak}")
print(f"gr3d_avg={fmt(gr3d_sum/gr3d_n) if gr3d_n else ''}")
print(f"emc_avg={fmt(emc_sum/emc_n) if emc_n else ''}")
print(f"cpu_avg={fmt(cpu_sum/cpu_n) if cpu_n else ''}")
print(f"temp_cpu_avg={fmt(avg(temp_cpu))}")
print(f"temp_cpu_peak={fmt(max(temp_cpu) if temp_cpu else None)}")
print(f"temp_gpu_avg={fmt(avg(temp_gpu))}")
print(f"temp_gpu_peak={fmt(max(temp_gpu) if temp_gpu else None)}")
print(f"temp_ao_avg={fmt(avg(temp_ao))}")
print(f"temp_ao_peak={fmt(max(temp_ao) if temp_ao else None)}")
print(f"temp_thermal_avg={fmt(avg(temp_th))}")
print(f"temp_thermal_peak={fmt(max(temp_th) if temp_th else None)}")
print(f"pwr_in_avg={fmt(avg(pw_in))}")
print(f"pwr_in_peak={fmt(max(pw_in) if pw_in else None)}")
print(f"pwr_gpu_avg={fmt(avg(pw_gpu))}")
print(f"pwr_gpu_peak={fmt(max(pw_gpu) if pw_gpu else None)}")
print(f"pwr_cpu_avg={fmt(avg(pw_cpu))}")
print(f"pwr_cpu_peak={fmt(max(pw_cpu) if pw_cpu else None)}")
PY
)"

eval "$stats"

cat > "$SUMMARY_FILE" <<EOF
DATE: $TS
MODE: gpu + e2e
BASELINE_ENGINE: $(basename "$BASELINE_ENGINE")
TEST_ENGINE: $(basename "$TEST_ENGINE")
TRT_STREAMS: $TRT_STREAMS
TRT_WARMUP: $TRT_WARMUP
TRT_DURATION_SEC: $TRT_DURATION_SEC
SHAPE: N/A (engine-defined)

GPU_BASELINE:
- Throughput: ${baseline_throughput:-N/A} qps
- Latency mean: ${baseline_lat_mean:-N/A} ms
- Latency p99: ${baseline_lat_p99:-N/A} ms
- GPU memory total: ${baseline_gpu_mem_total_mib:-N/A} MiB
- Log: $GPU_BASELINE_LOG

GPU_TEST:
- Throughput: ${test_throughput:-N/A} qps
- Latency mean: ${test_lat_mean:-N/A} ms
- Latency p99: ${test_lat_p99:-N/A} ms
- GPU memory total: ${test_gpu_mem_total_mib:-N/A} MiB
- Log: $GPU_TEST_LOG

IMPROVEMENT (test vs baseline):
- Δ Throughput: ${tput_gain_abs:-N/A} (${tput_gain_pct:-N/A} %)
- Δ Mean latency (baseline - test): ${lat_gain_abs:-N/A} (${lat_gain_pct:-N/A} %)
- Δ P99 latency (baseline - test): ${p99_gain_abs:-N/A} (${p99_gain_pct:-N/A} %)

CPP_E2E:
- Camera FPS: ${cpp_cam:-N/A}
- Model FPS: ${cpp_model:-N/A}
- Infer avg: ${cpp_infer:-N/A}
- Log: $CPP_LOG

TEGRASTATS:
- Log: $TG_LOG
- RAM peak: ${ram_peak:-N/A} MB
- SWAP peak: ${swap_peak:-N/A} MB
- GR3D avg: ${gr3d_avg:-N/A} %
- EMC avg: ${emc_avg:-N/A} %
- CPU avg: ${cpu_avg:-N/A} %
- CPU temp avg/peak: ${temp_cpu_avg:-N/A} / ${temp_cpu_peak:-N/A} C
- GPU temp avg/peak: ${temp_gpu_avg:-N/A} / ${temp_gpu_peak:-N/A} C
- AO temp avg/peak: ${temp_ao_avg:-N/A} / ${temp_ao_peak:-N/A} C
- thermal avg/peak: ${temp_thermal_avg:-N/A} / ${temp_thermal_peak:-N/A} C
- POM_5V_IN avg/peak: ${pwr_in_avg:-N/A} / ${pwr_in_peak:-N/A} mW
- POM_5V_GPU avg/peak: ${pwr_gpu_avg:-N/A} / ${pwr_gpu_peak:-N/A} mW
- POM_5V_CPU avg/peak: ${pwr_cpu_avg:-N/A} / ${pwr_cpu_peak:-N/A} mW
EOF

# Append 1 dòng vào scoreboard.csv để so sánh nhiều lần chạy
SCOREBOARD_FILE="${SCOREBOARD_FILE:-$RUN_DIR/scoreboard.csv}"
cpp_infer_ms="${cpp_infer%ms}"
if [ ! -f "$SCOREBOARD_FILE" ]; then
  cat > "$SCOREBOARD_FILE" <<'CSV'
date,baseline_engine,test_engine,trt_streams,warmup,duration_s,baseline_qps,baseline_lat_mean_ms,baseline_lat_p99_ms,test_qps,test_lat_mean_ms,test_lat_p99_ms,throughput_gain_pct,mean_latency_improve_pct,p99_latency_improve_pct,cpp_camera_fps,cpp_model_fps,cpp_infer_avg_ms,ram_peak_mb,swap_peak_mb,gr3d_avg_pct,emc_avg_pct,cpu_avg_pct,temp_cpu_peak_c,temp_gpu_peak_c,pwr_in_avg_mw,pwr_in_peak_mw,pwr_gpu_avg_mw,pwr_cpu_avg_mw
CSV
fi
printf '%s,"%s","%s",%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
  "$TS" \
  "$(basename "$BASELINE_ENGINE")" \
  "$(basename "$TEST_ENGINE")" \
  "${TRT_STREAMS:-}" \
  "${TRT_WARMUP:-}" \
  "${TRT_DURATION_SEC:-}" \
  "${baseline_throughput:-}" \
  "${baseline_lat_mean:-}" \
  "${baseline_lat_p99:-}" \
  "${test_throughput:-}" \
  "${test_lat_mean:-}" \
  "${test_lat_p99:-}" \
  "${tput_gain_pct:-}" \
  "${lat_gain_pct:-}" \
  "${p99_gain_pct:-}" \
  "${cpp_cam:-}" \
  "${cpp_model:-}" \
  "${cpp_infer_ms:-}" \
  "${ram_peak:-}" \
  "${swap_peak:-}" \
  "${gr3d_avg:-}" \
  "${emc_avg:-}" \
  "${cpu_avg:-}" \
  "${temp_cpu_peak:-}" \
  "${temp_gpu_peak:-}" \
  "${pwr_in_avg:-}" \
  "${pwr_in_peak:-}" \
  "${pwr_gpu_avg:-}" \
  "${pwr_cpu_avg:-}" \
  >> "$SCOREBOARD_FILE"

echo "Summary saved: $SUMMARY_FILE"
echo "Scoreboard updated: $SCOREBOARD_FILE"

echo "==> Done."
echo "Logs:"
echo "  GPU baseline : $GPU_BASELINE_LOG"
echo "  GPU test     : $GPU_TEST_LOG"
echo "  C++ : $CPP_LOG"