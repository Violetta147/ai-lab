# Technical Forensic Log: Custom Payload Failure (Type 257)
**Date**: 2026-05-11
**Target**: DeepStream 6.0 on Jetson Nano (Headless)
**Status**: DEPRECATED / FAILED

## 1. The Objective
The goal was to implement a custom C++ library (`libnvds_msgconv_c2.so`) that would intercept DeepStream metadata and convert it into a proprietary "C2" JSON format before sending it to Kafka.

## 2. Chronological Failure Analysis

### Phase A: The "Unknown Symbol" Era
*   **Attempt**: Initial build of the `.so` plugin.
*   **Result**: Pipeline failed to load the library due to missing DeepStream 6.0 ABI symbols.
*   **Fix**: Discovered that DS 6.0 requires `nvds_msg2p_ctx_create` and `nvds_msg2p_release` to be explicitly exported.
*   **Outcome**: Handshake achieved, but moved to the next failure.

### Phase B: The "GLib Crash" Era (g_strchug)
*   **Attempt**: Enabling `payload-type=257` in the `[sink]` block.
*   **Error**: `GLib-CRITICAL: g_strchug: assertion 'string != NULL' failed`.
*   **Discovery**: The `deepstream-app` binary contains a hardcoded orchestration bug. When `type=6` (Kafka) is used with a custom library, the internal parser attempts to "trim" (chug) a string property that hasn't been initialized, resulting in a NULL pointer dereference and immediate crash.

### Phase C: The "New API" Discovery
*   **Attempt**: Setting `msg-conv-msg2p-new-api=1`.
*   **Discovery**: Discovered through header inspection (`nvmsgconv.h`) that the "New API" bypasses the standard `generate` function and calls `nvds_msg2p_generate_new`.
*   **Implementation**: Refactored C++ code to support the new `NvDsMsg2pMetaInfo` struct.
*   **Result**: Pipeline finally reached `PLAYING` state (at 35 FPS), but produced **0-byte files**.

### Phase D: The "Config Parser" Hell
*   **Attempt**: Moving configuration keys between the Main App Config and a sub-config file.
*   **Failure**: Tried `[property]`, `[custom]`, and `[message-converter]` headers.
*   **Result**: `deepstream-app` threw `Unknown group` warnings for every header. The binary in DS 6.0 on Nano appears to have a non-standard or crippled parser for sub-config files.

## 3. The Isolation Breakthrough
We switched the sink from `type=6` (Kafka) to `type=1` (Fakesink).
*   **Finding**: The `g_strchug` crash **disappeared**!
*   **Conclusion**: The crash is **not** in the Message Converter itself, but in the **Kafka Sink's internal bridge** to the message converter. Specifically, the Kafka sink in DS 6.0 on Jetson Nano cannot safely "hand off" metadata to a custom `.so` without triggering a NULL assertion.

## 4. Final Verdict
*   **Standard Payload (Type 0)**: 100% Stable, 35 FPS, Full Telemetry.
*   **Custom Payload (Type 257)**: Binary-level orchestration failure in `deepstream-app`.

**Recommendation**: Do not attempt to use `type=257` on this specific JetPack/DeepStream revision. Use Type 0 and perform JSON transformation on the backend server (Laptop A).

---
*End of Report*
