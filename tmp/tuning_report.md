# C2 Analytics Pipeline: Optimization & Bottleneck Guide

This report details every "knob" you can turn to balance performance, latency, and thermal stability on the Jetson Nano and the Backend.

---

## 🏎 1. Jetson DeepStream Tuning (`setup_c2_roi.sh`)

These settings impact the **Edge Device** load and the quality of metadata sent to Kafka.

### Inference Config (`[property]` in `config_infer_c2.txt`)
| Parameter | Current | Recommended | Impact |
| :--- | :--- | :--- | :--- |
| `network-mode` | `0` (FP32) | `0` (FP32) | **Keep at 0** for Nano 4GB to avoid custom library crashes. |
| `interval` | `3` | `2` to `5` | **Inference Skip.** `3` means infer every 4th frame. Increase this (e.g., `5`) to cool the Nano further. |
| `cluster-mode` | `4` | `2` or `4` | `4` (DBSCAN) is accurate; `2` (GroupRects) is much faster but "jittery". |
| `maintain-aspect-ratio`| `1` | `1` | **Always keep at 1** to prevent cars from looking "squashed" in the AI's eyes. |

### Detection Filtering (`[class-attrs-all]`)
| Parameter | Current | Recommended | Impact |
| :--- | :--- | :--- | :--- |
| `pre-cluster-threshold`| `0.25` | `0.40` | **Confidence Filter.** Higher value = fewer false positives and less data for the Backend to process. |
| `topk` | `100` | `40` | **Max Objects.** If you don't expect 100 cars in a frame, lower this to reduce Kafka payload size. |

### Streammux & Tracker (`deepstream_c2_roi.txt`)
| Parameter | Current | Recommended | Impact |
| :--- | :--- | :--- | :--- |
| `batched-push-timeout` | `40000` | `20000` | **Latency.** Lower value = metadata is sent faster, but uses more CPU. |
| `tracker-width/height` | `640x384` | `480x272` | **Tracker Speed.** Lower resolution makes the tracker faster (less CPU) but less accurate for tiny cars. |

---

## 🧠 2. Backend Sync & Analytics (`backend/app/...`)

These settings impact how the **PC** matches video frames with Jetson data.

### Sync Logic (`core/config.py`)
| Parameter | Current | Recommended | Impact |
| :--- | :--- | :--- | :--- |
| `SYNC_TOLERANCE_MS` | `200.0` | `100` to `400` | **Match Window.** If boxes flicker, **increase** this. If boxes lag behind cars, **decrease** it. |
| `VIDEO_QUEUE_MAXSIZE` | `30` | `5` to `60` | **Buffer Lag.** Lowering this (e.g. `10`) reduces "Live" delay but makes the video "stutter" if the network is slow. |

### Anti-Flicker (`runtime/sync_engine.py`)
| Parameter | Current | Recommended | Impact |
| :--- | :--- | :--- | :--- |
| `_hold_ttl_sec` | `0.5` | `0.3` to `1.0` | **Ghost Duration.** How long to keep a box on screen if Jetson misses a frame. Increase to hide flickering. |
| `_alpha` | `0.05` | `0.01` to `0.2` | **Drift Speed.** How fast the backend adapts to clock drift. Higher = more aggressive alignment. |

---

## 📺 3. FFmpeg Source Optimization

| Flag | Recommended | Impact |
| :--- | :--- | :--- |
| `-c:v copy` | **Mandatory** | Zero latency. Use this unless you *must* resize on the PC. |
| `-rtsp_transport tcp` | **Mandatory** | Prevents "tearing" and green artifacts in the video. |
| `-g 30` | **Recommended** | Forces a keyframe every 1 second. Makes the Jetson recover faster if the network blips. |
| `-re` | **Mandatory** | Ensures the video doesn't play at "fast forward" speed. |

---

## 🔍 How to Debug a Bottleneck

1.  **Is the video slow?** 
    - Check the PC CPU usage. If high, check `RtspVideoReader` logs. 
    - Use `ffmpeg -c:v copy` to eliminate PC encoding as a cause.
2.  **Are the boxes flickering?** 
    - Check the Jetson Temperature (`tegrastats`). If it's > 80°C, the Jetson is throttling. 
    - Increase `interval` in `setup_c2_roi.sh`.
    - Increase `SYNC_TOLERANCE_MS` in the backend.
3.  **Are the boxes lagging (Ghosting)?**
    - Decrease `VIDEO_QUEUE_MAXSIZE` to `10`.
    - Ensure your PC and Jetson have their clocks synced to the same NTP server.
    - Check if `Drift Correction` in `sync_engine.py` is working (look for offset logs).
