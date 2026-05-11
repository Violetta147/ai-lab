# 01 — Edge Pipeline (Jetson Nano)

DeepStream 6.0 GStreamer pipeline running on Jetson Nano (192.168.1.14).
Configured by `deepstream/multi-stream/setup_c2_roi.sh`.

```mermaid
flowchart TD
    subgraph EDGE ["Jetson Nano — DeepStream 6.0"]
        direction TB

        subgraph INPUT ["Video Input"]
            SRC0["source0\ntype=4 (RTSP)\nuri=rtsp://172.16.1.162:8554/cam"]
        end

        subgraph MUX ["Stream Multiplexer"]
            SM["streammux\ngpu-id=0\nlive-source=1\nbatch-size=1\nwidth=640, height=640\nnvbuf-memory-type=0"]
        end

        subgraph INFERENCE ["Primary Inference"]
            PGIE["primary-gie\ngie-unique-id=1\nmodel: yolo_all_exports_p2n_fine-tuning2_best\nnetwork-mode=2 (FP16)\ninterval=1\ncluster-mode=4\ncustom-lib: libnvdsinfer_custom_impl_Yolo26.so"]
        end

        subgraph TRACKING ["Object Tracker"]
            TRACKER["NvDCF Tracker\ntracker-width=640\ntracker-height=384\nenable-past-frame=1\ndisplay-tracking-id=1\nconfig: config_tracker_NvDCF_perf.yml"]
        end

        subgraph ZONE_FILTER ["ROI Analytics"]
            NVDA["nvds-analytics\nconfig-width=1920\nconfig-height=1080\nROI polygon: 759;306;1077;325;1477;957;292;917\n(loaded from stream_profiles.json)"]
        end

        subgraph OSD_LAYER ["On-Screen Display"]
            OSD["osd\nborder-width=2\ntext-size=12\nshow-clock=1"]
        end

        subgraph SINKS ["Output Sinks"]
            SINK0["sink0 — Kafka Message\ntype=6\nmsg-conv-payload-type=257\nlib: libnvds_msgconv_c2.so (custom)\nbroker: libnvds_kafka_proto.so\nconn: 172.16.1.162;9092;c2_metadata"]
            SINK1["sink1 — RTSP Server\ntype=4\nrtsp-port=8555\nudp-port=5400\ncodec=1 (H.264)\nbitrate=4000000"]
        end

        SRC0 --> SM --> PGIE --> TRACKER --> NVDA --> OSD
        OSD --> SINK0
        OSD --> SINK1
    end
```

## Key Configuration Files

| File | Purpose |
|------|---------|
| `setup_c2_roi.sh` | Main launcher — generates all DeepStream configs at runtime |
| `config_infer_c2.txt` | YOLO inference config (generated) |
| `config_nvdsanalytics_roi.txt` | ROI polygon filter config (generated) |
| `cfg_kafka.txt` | Kafka broker connection string |
| `nvmsgconv_c2_config.txt` | Custom message converter config |
| `libnvds_msgconv_c2.so` | Custom Type 257 message converter (C++) |
| `libnvdsinfer_custom_impl_Yolo26.so` | Custom YOLO parser |

## Kafka Payload Schema (Type 257)

```json
{
  "timestamp": 1715400000.123,
  "source_id": 0,
  "objects": [
    {
      "class_id": 2,
      "label": "car",
      "confidence": 0.87,
      "tracker_id": 42,
      "bbox": { "left": 100, "top": 200, "width": 80, "height": 60 },
      "roi_status": "inside"
    }
  ]
}
```
