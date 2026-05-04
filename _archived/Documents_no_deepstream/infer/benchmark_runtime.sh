#!/usr/bin/env bash
set -euo pipefail

# Simple runtime benchmark for Jetson:
# - runs ./main camera for N seconds
# - captures tegrastats in parallel
# - prints compact averages

ENGINE_PATH="${1:-/home/jetson/Documents/models/best_v8n_pruned.engine}"
DURATION_SEC="${2:-60}"
INTERVAL_MS="${3:-1000}"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${PWD}/benchmark_${STAMP}"
mkdir -p "${OUT_DIR}"

APP_LOG="${OUT_DIR}/app.log"
TEGRA_LOG="${OUT_DIR}/tegrastats.log"
SUMMARY_TXT="${OUT_DIR}/summary.txt"

echo "[bench] output dir: ${OUT_DIR}"
echo "[bench] engine: ${ENGINE_PATH}"
echo "[bench] duration: ${DURATION_SEC}s, tegrastats interval: ${INTERVAL_MS}ms"

# Start tegrastats in background (auto-stop by timeout)
timeout "${DURATION_SEC}s" tegrastats --interval "${INTERVAL_MS}" > "${TEGRA_LOG}" 2>&1 &
TEGRA_PID=$!

# Run app with profiling logs enabled
set +e
PIPELINE_ENGINE="${ENGINE_PATH}" \
PIPELINE_PROFILE=1 \
YOLO_PROFILE=1 \
YOLO_PROFILE_EVERY=30 \
timeout "${DURATION_SEC}s" ./main camera > "${APP_LOG}" 2>&1
APP_RC=$?
set -e

# Ensure tegrastats exits
wait "${TEGRA_PID}" 2>/dev/null || true

# timeout exits with 124 on normal timeout; treat it as success
if [[ "${APP_RC}" -ne 0 && "${APP_RC}" -ne 124 ]]; then
  echo "[bench] app exited with code ${APP_RC}"
fi

# Summarize app + tegrastats with python (portable on Jetson)
python3 - "${APP_LOG}" "${TEGRA_LOG}" "${SUMMARY_TXT}" <<'PY'
import re
import sys

app_log, tegra_log, summary = sys.argv[1], sys.argv[2], sys.argv[3]

def avg(values):
    return sum(values) / len(values) if values else 0.0

infer_fps_vals = []
infer_ms_vals = []
read_vals = []
draw_vals = []

with open(app_log, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        if "Infer(E2E) FPS" in line or "Infer FPS" in line:
            m = re.search(r"Infer(?:\(E2E\))? FPS:\s*([0-9.]+)", line)
            if m:
                infer_fps_vals.append(float(m.group(1)))
            m = re.search(r"infer=([0-9.]+)", line)
            if m:
                infer_ms_vals.append(float(m.group(1)))
            m = re.search(r"(?:capture_wait|read)=([0-9.]+)", line)
            if m:
                read_vals.append(float(m.group(1)))
            m = re.search(r"draw=([0-9.]+)", line)
            if m:
                draw_vals.append(float(m.group(1)))

ram_used_vals = []
ram_total = 0
gr3d_vals = []
cpu_util_vals = []

with open(tegra_log, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        if "GR3D_FREQ" not in line:
            continue
        m = re.search(r"RAM\s+([0-9]+)/([0-9]+)MB", line)
        if m:
            ram_used_vals.append(float(m.group(1)))
            ram_total = int(m.group(2))
        m = re.search(r"GR3D_FREQ\s+([0-9]+)%", line)
        if m:
            gr3d_vals.append(float(m.group(1)))
        m = re.search(r"CPU\s+\[([^\]]+)\]", line)
        if m:
            parts = m.group(1).split(",")
            core_vals = []
            for p in parts:
                mm = re.search(r"([0-9]+)%@", p)
                if mm:
                    core_vals.append(float(mm.group(1)))
            if core_vals:
                cpu_util_vals.append(sum(core_vals) / len(core_vals))

with open(summary, "w", encoding="utf-8") as out:
    out.write(f"APP_SAMPLES={len(infer_fps_vals)}\n")
    if infer_fps_vals:
        out.write(f"APP_INFER_FPS_AVG={avg(infer_fps_vals):.3f}\n")
        out.write(f"APP_INFER_MS_AVG={avg(infer_ms_vals):.3f}\n")
        out.write(f"APP_READ_OR_WAIT_MS_AVG={avg(read_vals):.3f}\n")
        out.write(f"APP_DRAW_MS_AVG={avg(draw_vals):.3f}\n")

    out.write(f"TEGRA_SAMPLES={len(gr3d_vals)}\n")
    if gr3d_vals:
        out.write(f"TEGRA_RAM_USED_MB_AVG={avg(ram_used_vals):.1f}\n")
        out.write(f"TEGRA_RAM_TOTAL_MB={ram_total}\n")
        out.write(f"TEGRA_GR3D_FREQ_AVG={avg(gr3d_vals):.1f}\n")
        out.write(f"TEGRA_CPU_UTIL_AVG={avg(cpu_util_vals):.1f}\n")
PY

echo "[bench] done"
echo "[bench] logs:"
echo "  - ${APP_LOG}"
echo "  - ${TEGRA_LOG}"
echo "  - ${SUMMARY_TXT}"
echo
cat "${SUMMARY_TXT}"
