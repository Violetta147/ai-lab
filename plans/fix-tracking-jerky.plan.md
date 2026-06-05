# Plan: Fix Tracking (Sparse Boxes and Jerky ID Switching)

## Summary
The current tracking system occasionally loses bounding boxes ("lác đác") and suffers from jerky ID switching ("giật cục"). This is primarily caused by strict tracking thresholds (IoU/confidence) operating over lower frame rates (e.g., WS_TARGET_FPS pacing), where objects displace significantly between frames, causing the ByteTrack tracker to break tracks and create new ones.

## User Story
As an edge AI user, I want the tracking system to smoothly follow vehicles across frames even at lower processing frame rates, so that vehicle counts and speed estimations remain accurate without jerky ID changes.

## Problem → Solution
**Current state**: 
- Python `pipeline_manager.py` uses `sv.ByteTrack(minimum_consecutive_frames=1)` with default `supervision` thresholds (`minimum_matching_threshold` typically 0.8, requiring 80% overlap). At low FPS (e.g. `WS_TARGET_FPS`), objects move too far, IoU drops below 0.8, and the track is broken.
- C++ `bt_byte_tracker.cpp` hardcodes `track_thresh_ = 0.5f`, dropping lower-confidence detections prematurely, resulting in sparse boxes.

**Desired state**: 
- Configure `sv.ByteTrack` in Python with more lenient matching thresholds (`minimum_matching_threshold` ~0.4) and lower activation thresholds.
- Lower `track_thresh_` in the C++ tracker to accept more YOLO detections.

## Metadata
- **Complexity**: Small
- **Source PRD**: N/A
- **PRD Phase**: N/A
- **Estimated Files**: 2

---

## Mandatory Reading

| Priority | File | Lines | Why |
|---|---|---|---|
| P0 | `c2_center/backend/app/runtime/pipeline_manager.py` | 94 | Python ByteTrack instantiation |
| P1 | `edge_server_cplusplus/src/infer/bt_byte_tracker.cpp` | 39-48 | C++ ByteTracker hardcoded thresholds |

---

## Files to Change

| File | Action | Justification |
|---|---|---|
| `c2_center/backend/app/runtime/pipeline_manager.py` | UPDATE | Tune `sv.ByteTrack` parameters to handle low FPS displacement |
| `edge_server_cplusplus/src/infer/bt_byte_tracker.cpp` | UPDATE | Lower `track_thresh_` to prevent dropping valid lower-confidence detections |

## NOT Building
- Rewriting the tracker algorithm (using default ByteTrack/Kalman filter logic).
- Changing DeepStream's native tracking configuration (only fixing the Python and C++ fallback trackers).

---

## Step-by-Step Tasks

### Task 1: Tune Python ByteTrack Parameters
- **ACTION**: Update `sv.ByteTrack` initialization to handle lower frame rates.
- **IMPLEMENT**: In `c2_center/backend/app/runtime/pipeline_manager.py` (around line 94):
  Change:
  `self._trackers[stream_id] = sv.ByteTrack(minimum_consecutive_frames=1)`
  To:
  ```python
  self._trackers[stream_id] = sv.ByteTrack(
      track_activation_threshold=0.25,
      lost_track_buffer=30,
      minimum_matching_threshold=0.4, # Lower IoU threshold to tolerate large displacements between frames
      minimum_consecutive_frames=1
  )
  ```
- **MIRROR**: Python keyword argument initialization.
- **IMPORTS**: None new required.
- **GOTCHA**: Supervision `0.25.0` requires keyword arguments for some of these parameters.
- **VALIDATE**: Run the backend and verify that trackers no longer flicker rapidly when vehicles move fast.

### Task 2: Tune C++ ByteTracker Thresholds
- **ACTION**: Lower the minimum tracking confidence threshold in the C++ edge server.
- **IMPLEMENT**: In `edge_server_cplusplus/src/infer/bt_byte_tracker.cpp` (around line 40):
  Change:
  `track_thresh_(0.5f)`
  To:
  `track_thresh_(0.25f)`
- **MIRROR**: Standard float initialization in initializer list.
- **IMPORTS**: None.
- **GOTCHA**: `high_thresh_` remains `0.6f`, so detections between 0.25 and 0.6 will be treated as low-confidence tracks (second phase matching), which is standard ByteTrack behavior.
- **VALIDATE**: Recompile `edge_server_cplusplus` and verify that vehicles with lower YOLO confidence (e.g. partially occluded) are still tracked.

---

## Testing Strategy

### Manual Validation
- [ ] Connect a live or recorded video stream (e.g., `test.webm`).
- [ ] Observe the WebSocket annotated frames via the frontend dashboard.
- [ ] Verify that bounding boxes persist smoothly across frames (no "giật cục").
- [ ] Verify that partially occluded or distant vehicles are still detected (no "lác đác vài box").

## Acceptance Criteria
- [ ] Python `sv.ByteTrack` instantiated with lenient `minimum_matching_threshold` (0.4).
- [ ] C++ `ByteTracker` `track_thresh_` lowered to 0.25f.
- [ ] Tracking ID switches significantly reduced during high-speed movement or low FPS.

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Lowering thresholds causes ghost tracks | Low | Medium | Keep `minimum_consecutive_frames` or `high_thresh` high enough to filter out pure noise. |
