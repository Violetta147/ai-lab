# Plan: Livestream Realtime Tracking

## Summary
Triển khai bộ theo dõi thời gian thực (Realtime Tracker - `ByteTrack`) tập trung tại `PipelineManager` để toàn bộ các thuật toán Livestream (như `area_occupancy`, `heatmap`) đều có ID ổn định. Đồng thời xử lý lỗi đa luồng trong `MqttVideoAdapter` để loại bỏ hoàn toàn độ trễ 1.5 giây giữa video và tọa độ hộp bọc.

## User Story
As a C2 Center Operator, I want objects in the livestream to have stable tracking IDs and perfectly synced bounding boxes, so that I don't see boxes jumping around or lagging behind fast-moving vehicles.

## Problem → Solution
**Current state**: 
- `metadata_to_detections` luôn trả về `tracker_id = [-1, -1, ...]`.
- Các thuật toán kiểm tra `getattr(detections, 'tracker_id', None) is None` sẽ bị sai (vì nó trả về mảng numpy chứ không phải None), dẫn đến `ByteTrack` bị vô hiệu hóa hoàn toàn, ngay cả trên `line_crossing`.
- MQTT Client decode Video Base64 trên luồng mạng chính, gây nghẽn cổ chai và làm trễ video 1.5 giây.

**Desired state**: 
- `PipelineManager` quản lý một từ điển `_trackers: dict[str, sv.ByteTrack]`.
- Nếu `detections.tracker_id` chứa toàn `-1`, `PipelineManager` sẽ xóa `tracker_id` (đặt thành None) và gọi `ByteTrack.update_with_detections()`.
- Lắp `ThreadPoolExecutor` vào `MqttVideoAdapter` để giải phóng luồng Paho MQTT.

## Metadata
- **Complexity**: Medium
- **Source PRD**: N/A
- **PRD Phase**: N/A
- **Estimated Files**: 3

---

## Mandatory Reading

| Priority | File | Lines | Why |
|---|---|---|---|
| P0 (critical) | `c2_center/backend/app/runtime/pipeline_manager.py` | 103-214 | Vòng lặp `_loop` xử lý frame, nơi ta sẽ chèn ByteTrack. |
| P1 (important) | `c2_center/backend/app/infrastructure/mqtt/mqtt_video_adapter.py` | 62-80 | Lỗi nghẽn cổ chai khi parse JSON 65KB trên main thread. |
| P2 (reference) | `c2_center/backend/app/domain/detection/converters.py` | 47-59 | Nơi gán `tracker_id = -1` khiến logic kiểm tra bị sai. |

---

## Patterns to Mirror

### BYTE_TRACKER_INIT
```python
# SOURCE: c2_center/backend/app/analytics/plugins/line_crossing.py:28
import supervision as sv
self._tracker = sv.ByteTrack(minimum_consecutive_frames=1)
```

### BYTE_TRACKER_UPDATE
```python
# SOURCE: c2_center/backend/app/analytics/plugins/line_crossing.py:65
# Phải gỡ bỏ tracker_id = -1 trước khi đưa vào ByteTrack
detections.tracker_id = None
detections = self._tracker.update_with_detections(detections=detections)
```

---

## Files to Change

| File | Action | Justification |
|---|---|---|
| `c2_center/backend/app/runtime/pipeline_manager.py` | UPDATE | Thêm `_trackers` dict, khởi tạo `ByteTrack` cho mỗi luồng, và cập nhật `detections` trong `_loop`. |
| `c2_center/backend/app/analytics/plugins/line_crossing.py` | UPDATE | Xóa logic `ByteTrack` cục bộ vì đã được xử lý tập trung. |
| `c2_center/backend/app/infrastructure/mqtt/mqtt_video_adapter.py` | UPDATE | Thêm `ThreadPoolExecutor` để xử lý `_decode_and_store` bất đồng bộ. |

---

## Step-by-Step Tasks

### Task 1: Fix MqttVideoAdapter Threading Bottleneck
- **ACTION**: Move JSON and Base64 decoding to a ThreadPoolExecutor.
- **IMPLEMENT**: 
  - Khởi tạo `self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)` trong `__init__`.
  - Trong `_on_message`, đổi thành `self._executor.submit(self._decode_msg, msg.payload)`.
- **IMPORTS**: `import concurrent.futures`
- **GOTCHA**: Ensure OpenCV decode is thread-safe (it is).
- **VALIDATE**: `SYNC-DIAG` log will show "Alignment error" dropping from ~1500ms to < 50ms.

### Task 2: Implement Centralized Tracking in PipelineManager
- **ACTION**: Add `ByteTrack` directly into the `_loop`.
- **IMPLEMENT**:
  - `self._trackers = {}` in `__init__`.
  - In `start_stream()`, `self._trackers[stream_id] = sv.ByteTrack(...)`
  - In `_loop()`, after scaling bbox:
    ```python
    # Check if tracker_id contains -1
    if len(detections) > 0 and detections.tracker_id is not None and len(detections.tracker_id) > 0 and detections.tracker_id[0] == -1:
        detections.tracker_id = None
        if stream_id in self._trackers:
            detections = self._trackers[stream_id].update_with_detections(detections=detections)
    ```
- **IMPORTS**: `import supervision as sv`
- **VALIDATE**: `detections.tracker_id` will contain real IDs (>0) when passed to `dispatcher.run()`.

### Task 3: Clean up LineCrossingAnalyzer
- **ACTION**: Remove redundant tracker from line crossing.
- **IMPLEMENT**: Remove `self._tracker` from `__init__` and remove the `update_with_detections` block in `process`.
- **VALIDATE**: Line crossing still counts correctly using the IDs provided by `PipelineManager`.

---

## Acceptance Criteria
- [ ] Task 1, 2, 3 hoàn thành.
- [ ] Các bounding box không bị nhảy và được gán ID qua các frame.
- [ ] Log hệ thống không còn cảnh báo "Alignment error" lên tới hàng nghìn mili-giây.
- [ ] Self-contained — plan này đã có đủ các path cần thiết.
