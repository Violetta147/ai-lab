---
applyTo: "**/{deepstream,rstp,nvinfer,gstreamer}/**,**/setup_deepstream_*.sh,**/*deepstream*,**/*nvinfer*"
---

# NVIDIA DeepStream SDK 9.0 Development Guide

When working on DeepStream-related code, **ALWAYS consult the reference documents** in `deepstream_coding_agent_tmp/skills/deepstream-dev/references/` before generating code. Do NOT rely on memory.

## Reference Documents Location
All reference documents are located at: `deepstream_coding_agent_tmp/skills/deepstream-dev/references/`

| Document | Use When |
|----------|----------|
| `gstreamer_plugins.md` | Looking up plugin properties |
| `service_maker_api.md` | Using Pipeline/Flow API, metadata access, probes |
| `use_cases_pipelines.md` | Building pipelines: playback, multi-inference, cascaded GIE |
| `kafka_messaging.md` | Kafka/message broker setup and configuration |
| `best_practices.md` | Design patterns, common pitfalls, anti-patterns |
| `buffer_apis.md` | BufferProvider/Feeder and BufferRetriever/Receiver |
| `media_extractor_advanced.md` | MediaExtractor, MediaChunk, FrameSampler |
| `utilities_config.md` | PerfMonitor, EngineFileMonitor, SourceConfig |
| `nvinfer_config.md` | nvinfer config file format and ALL parameters |
| `tracker_config.md` | nvtracker config (NvDCF, IOU, DeepSORT, NvSORT) |
| `troubleshooting.md` | Error messages and solutions |
| `rest_api_dynamic.md` | REST API, dynamic source management |
| `docker_containers.md` | Docker images, Dockerfile examples, pyservicemaker install |

## SDK Requirements
- **GStreamer**: 1.24.2
- **NVIDIA Driver**: 590+
- **CUDA**: 13.1
- **TensorRT**: 10.14.1.48
- **Platforms**: Ubuntu 24.04 (x86_64 and ARM64/Jetson)

## Typical Pipeline Flow
```
Source → Stream Muxer → Inference → [Tracker] → OSD → Renderer
```
Components in `[brackets]` are optional — only add when explicitly requested.

| Stage | Key Element(s) | Required? |
|-------|----------------|-----------|
| Source | `nvurisrcbin` (preferred), `nvmultiurisrcbin`, `filesrc` | Yes |
| Stream Muxer | `nvstreammux` | Yes |
| Inference | `nvinfer`, `nvinferserver` | Yes |
| Tracker | `nvtracker` | Only if requested |
| OSD | `nvosdbin` | Yes (for visualization) |
| Renderer | `nveglglessink`, `nv3dsink`, `filesink` | Yes |

## Critical Rules

1. **Only Add Requested Components** — Do NOT add tracker, secondary GIEs, analytics, or message broker unless explicitly requested.

2. **Default to `nvurisrcbin`** — Handles RTSP, HTTP, and local files transparently. Convert local paths: `"file://" + os.path.abspath(path)`.

3. **Metadata Iteration** — Use `.frame_items` and `.object_items` (iterators, NOT lists). NEVER use `len()`.

4. **Request Pad Syntax** — Use `"sink_%u"` template, NEVER literal pad names like `"sink_0"`.

5. **Platform Detection for Sinks**:
```python
import platform
sink_type = "nv3dsink" if platform.processor() == "aarch64" else "nveglglessink"
```

6. **Buffer Cloning** — Always clone buffers for async processing: `tensor = buffer.extract(0).clone()`

7. **nvinfer Config Format** — YAML: `property:` section. INI: `[property]` section. Section MUST be named `property`.

8. **ALL Sinks Need async=0 for Tee Splits or Dynamic Sources** — Without it, pipeline stays PAUSED.

9. **Dynamic ONNX → add `infer-dims=C;H;W`** — e.g., `infer-dims=3;640;640` for YOLO models.

10. **YOLO Output Format**:
    - v8/v11: `[batch, 84, 8400]` → `cluster-mode: 2` (NMS)
    - v10/v26+: `[batch, 300, 6]` → `cluster-mode: 4` (none, already post-NMS)

## Common Error Solutions

| Error | Solution |
|-------|----------|
| `iterator has no len()` | Iterate to count, don't use `len()` |
| `pad template not found` | Use `"sink_%u"` not `"sink_0"` |
| Config parse failed | Use `property:` not `model:` in YAML |
| Tee/dynamic source stuck PAUSED | Set `async: 0` on ALL sinks |
| `setDimensions` error | Add `infer-dims=C;H;W` for dynamic ONNX |
| `No module named 'pyservicemaker'` | Install whl inside venv |

## Key Paths (DeepStream 9.0)
- Models: `/opt/nvidia/deepstream/deepstream/samples/models/`
- Tracker lib: `/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so`
- Sample configs: `/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/`
