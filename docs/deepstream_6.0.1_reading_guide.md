# DeepStream SDK 6.0.1 — Document Reading Guide

> 📖 Full documentation: [archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/index.html)
>
> This guide maps **common tasks and problems** to the specific documentation sections you should read. You don't need to read the whole doc — use this as a lookup table.

---

## 🗺️ Quick Navigation: "I want to..."

### 🚀 Getting Started / Setup

| I want to... | Read this section | Link |
|---|---|---|
| Understand what DeepStream is | DS Overview → Graph Architecture | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_Overview.html) |
| Install DS on Jetson Nano | Quickstart → Jetson Setup | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_Quickstart.html#jetson-setup) |
| Install SDK components | Quickstart → Install Jetson SDK components | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_Quickstart.html#install-jetson-sdk-components) |
| Install dependencies | Quickstart → Install Dependencies | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_Quickstart.html#install-dependencies) |
| Run DeepStream for the first time | Quickstart → Run deepstream-app | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_Quickstart.html#run-deepstream-app-the-reference-application) |
| Boost Jetson clock speed for better FPS | Quickstart → Boost the clocks | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_Quickstart.html#boost-the-clocks) |
| Run in headless mode (no monitor) | Quickstart → Running without an X server | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_Quickstart.html#running-without-an-x-server) |
| Use Docker on Jetson | Docker Containers → Jetson | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_docker_containers.html#a-docker-container-for-jetson) |

---

### ⚙️ deepstream-app Configuration (INI Files)

> **This is the MOST IMPORTANT section for your project.** Your `setup_deepstream_jetson.sh` generates these INI config files.

| I want to configure... | Read this section | Link |
|---|---|---|
| **All config groups overview** | Configuration Groups | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#configuration-groups) |
| `[application]` — perf measurement | Application Group | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#application-group) |
| `[source0]` — RTSP input, type, URI | Source Group ⭐ | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#source-group) |
| `[streammux]` — batch size, resolution | Streammux Group ⭐ | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#streammux-group) |
| `[primary-gie]` — inference config, GIE ID | Primary GIE and Secondary GIE Group ⭐ | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#primary-gie-and-secondary-gie-group) |
| `[tracker]` — NvDCF, IOU, tracker size | Tracker Group ⭐ | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#tracker-group) |
| `[osd]` — bbox colors, text, font | OSD Group | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#osd-group) |
| `[sink0]` — RTSP output, codec, bitrate | Sink Group ⭐ | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#sink-group) |
| `[tiled-display]` — multi-stream grid | Tiled-display Group | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#tiled-display-group) |
| `[nvds-analytics]` — line crossing, ROI | NvDs-analytics Group ⭐ | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#nvds-analytics-group) |
| `[message-converter]` — IoT messaging | Message Converter Group | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#message-converter-group) |

---

### 🔧 Inference Config (`config_infer_primary_*.txt`)

| I want to... | Read this section | Link |
|---|---|---|
| Understand `[property]` section keys | Primary GIE Group → nvinfer config | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#primary-gie-and-secondary-gie-group) |
| Set `custom-lib-path` for YOLO | Primary GIE → custom-lib-path | Same as above |
| Configure `cluster-mode`, NMS | Primary GIE → clustering | Same as above |
| Use FP16/INT8 (`network-mode`) | Primary GIE → network-mode | Same as above |
| Set per-class thresholds (`[class-attrs-*]`) | Primary GIE → class attributes | Same as above |

> **Also read**: [Gst-nvinfer plugin](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_plugin_gst-nvinfer.html) for the full property reference of the nvinfer plugin.

---

### 🎯 Tracking (NvDCF / IOU)

| I want to... | Read this section | Link |
|---|---|---|
| Understand tracker options | Tracker Group | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#tracker-group) |
| Tune NvDCF accuracy vs performance | Tracker Tuning → Accuracy-Performance Tradeoffs | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_plugin_NvMultiObjectTracker_parameter_tuning_guide.html#accuracy-performance-tradeoffs) |
| Set tracker frame resolution | Tuning → Video Frame Size for Tracker | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_plugin_NvMultiObjectTracker_parameter_tuning_guide.html#video-frame-size-for-tracker) |
| Understand detection interval effect | Tuning → Detection Interval | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_plugin_NvMultiObjectTracker_parameter_tuning_guide.html#detection-interval) |
| Handle ID switches / flickering | Tuning → Target Creation/Termination Policy | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_plugin_NvMultiObjectTracker_parameter_tuning_guide.html#target-creation-policy) |
| Tune Kalman Filter for smoothness | Tuning → State Estimation → Kalman Filter | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_plugin_NvMultiObjectTracker_parameter_tuning_guide.html#kalman-filter) |
| Tune Data Association (IOU matching) | Tuning → Data Association | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_plugin_NvMultiObjectTracker_parameter_tuning_guide.html#data-association) |
| Tune DCF filter learning rate | Tuning → DCF Core Tuning | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_plugin_NvMultiObjectTracker_parameter_tuning_guide.html#dcf-core-tuning) |

---

### 🏎️ Performance & Optimization

| I want to... | Read this section | Link |
|---|---|---|
| Improve FPS on Jetson | App Tuning → Jetson optimization ⭐ | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#jetson-optimization) |
| General DS best practices | App Tuning → DeepStream best practices | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#deepstream-best-practices) |
| Maximize inference throughput | App Tuning → Inference Throughput | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#inference-throughput) |
| Reduce false positives | App Tuning → Reducing Spurious Detections | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#reducing-spurious-detections) |
| See Jetson Nano benchmark numbers | Performance → Jetson → Jetson Nano | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_Performance.html#jetson-nano) |
| Understand perf config settings | Performance → Configuration File Settings | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_Performance.html#configuration-file-settings-for-performance-measurement) |

---

### 🧩 Custom YOLO Integration

| I want to... | Read this section | Link |
|---|---|---|
| Use a custom YOLO model with DS | Custom YOLO Model in DeepStream YOLO App | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_custom_YOLO.html) |
| Set up the YOLO sample | Custom YOLO → Set up the sample | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_custom_YOLO.html#set-up-the-sample) |
| Build a custom GStreamer plugin | Custom GStreamer Plugin with OpenCV | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_sample_custom_gstream.html) |
| Access NvBufSurface in OpenCV | Custom Plugin → Accessing NvBufSurface memory | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_sample_custom_gstream.html#accessing-nvbufsurface-memory-in-opencv) |

---

### 🐍 Python Development

| I want to... | Read this section | Link |
|---|---|---|
| Understand DS Python bindings | Python Sample Apps → Python Bindings | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_Python_Sample_Apps.html#python-bindings-and-application-development) |
| Build a pipeline in Python | Python → Pipeline Construction | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_Python_Sample_Apps.html#pipeline-construction) |
| Access metadata in Python | Python → MetaData Access | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_Python_Sample_Apps.html#metadata-access) |
| Access image/frame data | Python → Image Data Access | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_Python_Sample_Apps.html#image-data-access) |
| Register callback functions | Python → Callback Function Registration | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_Python_Sample_Apps.html#callback-function-registration) |

---

### ☁️ IoT / Cloud / Advanced

| I want to... | Read this section | Link |
|---|---|---|
| Send data to Kafka/cloud | test5 → IoT Protocols | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_test5.html#iot-protocols-supported-and-cloud-configuration) |
| Event-based smart recording | test5 → Smart Record | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_test5.html#smart-record-event-based-recording) |
| OTA model update at runtime | test5 → OTA model update | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_test5.html#ota-model-update) |
| Use TAO pre-trained models | TAO Toolkit Integration | [Link](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_TAO_integration.html) |

---

## 🔥 Priority Reading Order for Your Project

Based on your `setup_deepstream_jetson.sh` (YOLOv8 + NvDCF + nvdsanalytics + RTSP on Jetson Nano), read in this order:

| Priority | Section | Why |
|---|---|---|
| 1️⃣ | [Configuration Groups](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#configuration-groups) | Understand every `[section]` in your INI configs |
| 2️⃣ | [Source Group](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#source-group) + [Sink Group](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#sink-group) | Your RTSP input/output config |
| 3️⃣ | [Primary GIE Group](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#primary-gie-and-secondary-gie-group) | Your YOLOv8 inference config |
| 4️⃣ | [NvDCF Tracker Tuning Guide](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_plugin_NvMultiObjectTracker_parameter_tuning_guide.html) | Your tracker — accuracy vs FPS tradeoff |
| 5️⃣ | [NvDs-analytics Group](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#nvds-analytics-group) | Your line-crossing counter |
| 6️⃣ | [Jetson Optimization](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_ref_app_deepstream.html#jetson-optimization) | Squeeze more FPS from Nano |
| 7️⃣ | [Custom YOLO](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_custom_YOLO.html) | How DS handles custom YOLO models |
| 8️⃣ | [Performance → Jetson Nano](https://archive.docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_Performance.html#jetson-nano) | Benchmark numbers for your hardware |

---

## 📌 Mapping to Your Config Files

```
setup_deepstream_jetson.sh generates:
│
├── config_infer_primary_yolov8.txt     → Read: Primary GIE Group + Custom YOLO
│   ├── [property]                      → network-mode, custom-lib-path, cluster-mode
│   └── [class-attrs-*]                 → per-class thresholds, border-color
│
├── config_nvdsanalytics.txt            → Read: NvDs-analytics Group
│   ├── [property]                      → enable, config-width/height
│   └── [line-crossing-stream-0]        → coordinates, direction, mode
│
└── deepstream_app_yolov8_rtsp.txt      → Read: Configuration Groups (ALL)
    ├── [application]                   → perf measurement
    ├── [source0]                       → RTSP URI, type=4
    ├── [streammux]                     → batch-size, width/height
    ├── [primary-gie]                   → config-file, bbox colors
    ├── [tracker]                       → NvDCF, tracker resolution
    ├── [osd]                           → border-width, text-size
    ├── [nvds-analytics]                → analytics config file
    └── [sink0]                         → RTSP output, codec, bitrate
```
