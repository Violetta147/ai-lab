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
