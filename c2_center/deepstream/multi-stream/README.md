C2 DeepStream Multi-Stream
=========================

This folder contains templates for running DeepStream in multi-source mode and
publishing detection metadata to Kafka for the C2 backend.

Files:
- `setup_c2_multistream.sh` — generates DeepStream config and launches deepstream-app.
- `nvmsgconv_c2/` — template for a custom payload builder (C++) that constructs the
  JSON messages sent to Kafka. Build this inside the DeepStream container/WSL2.

Build instructions (WSL2 inside DeepStream image):

```bash
cd /workspace/c2_center/deepstream/multi-stream/nvmsgconv_c2
make
# copy libnvds_msgconv_c2.so to your work dir referenced by deepstream config
```

Adapt the C++ implementation to use the actual DeepStream `nvds_msg2p` API and
extract `tracking_id`, `class_id`, `bbox`, `confidence`, `frame_num`, and
timestamps. The C2 backend expects JSON of the form:

```json
{
  "stream_id": "cam_8554",
  "frame_id": 1024,
  "timestamp": "1679123456.789",
  "objects": [ { "tracking_id": 45, "class_id": 0, "class_name": "car", "bbox": {"x":100,"y":200,"w":150,"h":80}, "confidence":0.89 } ]
}
```

Note: this is intentionally a template — building and testing requires the
DeepStream SDK headers and libs available in the build environment.
