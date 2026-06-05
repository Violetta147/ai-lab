# Edge Server Memory Optimization Notes

## The "Silent Killer": Heap Fragmentation
When running the Edge Server on resource-constrained devices like the Jetson Nano (which often lacks SSD swap files), you may encounter `std::bad_alloc` exceptions even when there is plenty of free RAM.

**Symptom**: 
- `jtop` shows RAM is NOT full (e.g., only 50-60% used).
- GPU usage is > 90% (TensorRT inference is running perfectly and continuously).
- Background threads (like `SyncThread` reading an empty directory or allocating small buffers) suddenly throw `std::bad_alloc` and crash.

**Root Cause**:
This is caused by **Heap Fragmentation**, not a memory leak. In the `base64_encode` function, `std::string` was being appended byte-by-byte (`ret += char`) in a loop of over 70,000 iterations per image.
Without calling `reserve()`, `std::string` continuously requests larger blocks of memory from the OS, copies its old data to the new block, and frees the old block. 
Doing this 70,000 times per image, 10 images per second, shreds the RAM into tiny, disconnected fragments. Eventually, when a thread requests a single, contiguous 8KB block for something as simple as reading a directory, the OS cannot find a contiguous block (even if 500MB is free in total), resulting in `std::bad_alloc`.

## The Fix: Pre-allocation with `reserve()`
```cpp
ret.reserve(((bufLen + 2) / 3) * 4);
```
**Why this exact mathematical formula?**
- Base64 encoding takes exactly 3 bytes of raw binary (24 bits) and converts it into 4 characters (6 bits each).
- The final string length is always `ceil(bufLen / 3) * 4`.
- In C++ integer math, `ceil(A / B)` is safely implemented as `(A + B - 1) / B`.
- So `ceil(bufLen / 3)` becomes `(bufLen + 3 - 1) / 3` = `(bufLen + 2) / 3`.
- By multiplying by 4, we get the **exact, absolute** number of characters the Base64 string will contain (including padding `=` at the end).

By calling `reserve()`, C++ asks the OS for the exact required memory block **once**. The loop then fills this block without a single reallocation or memory copy, entirely preventing heap fragmentation.

## GPU vs RAM in `jtop`
- **GPU > 90%**: TensorRT is utilizing the CUDA cores effectively for YOLOv8 inference. This is expected and highly optimal.
- **RAM not full**: Because the issue was fragmentation, not a memory leak. The total memory consumed remained low, but the continuous "churn" destroyed the availability of contiguous memory blocks.

## Update: Diagnosing std::bad_alloc in SyncThread (June 2026)

**Observed Log**:
```text
[SyncThread] Exception: std::bad_alloc
[SyncThread] Memory at crash - Free RAM: 864 MB / 3964 MB, Free Swap: 4030 MB
```

**Key Insight**:
The system has **864 MB of free RAM** and **4030 MB of free Swap (ZRAM)**. This confirms that the crash is **not a global out-of-memory (OOM)** error. 
Since the main thread continues running and printing `Frame deduplicated` logs, the heap allocator is not globally exhausted. 

**Potential Causes**:
1. **Virtual Memory Mapping Limits**: Since the application uses CUDA/TensorRT and OpenCV camera stream decoding, it creates a large number of memory mappings. If it hits the Linux limit (`/proc/sys/vm/max_map_count`), any further memory mapping attempts (even small ones like creating a `std::filesystem::directory_iterator`) will fail and throw `std::bad_alloc`.
2. **Deterministic Large Allocation in SyncThread**: A logic bug or data corruption might cause `SyncThread` to request a massive size allocation (e.g. if parsing a malformed or corrupted JSON file that has a huge field value or if a string length calculation underflows).
3. **Double Free / Memory Corruption in SyncThread**: A thread-safety race condition on the shared `MqttClient` or files being modified concurrently could corrupt the allocator's internal structure in that specific thread's context.

**Diagnostic Checkpoints**:
- We have added conditional `<sys/sysinfo.h>` system logging inside [sync_thread.cpp](file:///d:/datas/Final.yolov8/edge_server_cplusplus/src/core/sync_thread.cpp) to verify memory states immediately upon crash.
- Detailed print checkpoints should be added inside the `SyncThread::run` directory traversal to isolate the exact line throwing the exception.
- Check the contents of the `buffer/` directory. If a JSON file is empty or corrupted, it must be handled defensively.
