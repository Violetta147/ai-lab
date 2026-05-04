root@nano:/opt/nvidia/deepstream/deepstream-6.0# /usr/src/tensorrt/bin/trtexec \
>   --loadEngine=/root/deepstream_yolo/best_deepstream.onnx_b1_gpu0_fp16.engine \
>   --batch=1 \
>   --iterations=100 \
>   --warmUp=50 \
>   --fp16
&&&& RUNNING TensorRT.trtexec [TensorRT v8001] # /usr/src/tensorrt/bin/trtexec --loadEngine=/root/deepstream_yolo/best_deepstream.onnx_b1_gpu0_fp16.engine --batch=1 --iterations=100 --warmUp=50 --fp16
[04/14/2026-01:36:48] [I] === Model Options ===
[04/14/2026-01:36:48] [I] Format: *
[04/14/2026-01:36:48] [I] Model:
[04/14/2026-01:36:48] [I] Output:
[04/14/2026-01:36:48] [I] === Build Options ===
[04/14/2026-01:36:48] [I] Max batch: 1
[04/14/2026-01:36:48] [I] Workspace: 16 MiB
[04/14/2026-01:36:48] [I] minTiming: 1
[04/14/2026-01:36:48] [I] avgTiming: 8
[04/14/2026-01:36:48] [I] Precision: FP32+FP16
[04/14/2026-01:36:48] [I] Calibration:
[04/14/2026-01:36:48] [I] Refit: Disabled
[04/14/2026-01:36:48] [I] Sparsity: Disabled
[04/14/2026-01:36:48] [I] Safe mode: Disabled
[04/14/2026-01:36:48] [I] Restricted mode: Disabled
[04/14/2026-01:36:48] [I] Save engine:
[04/14/2026-01:36:48] [I] Load engine: /root/deepstream_yolo/best_deepstream.onnx_b1_gpu0_fp16.engine
[04/14/2026-01:36:48] [I] NVTX verbosity: 0
[04/14/2026-01:36:48] [I] Tactic sources: Using default tactic sources
[04/14/2026-01:36:48] [I] timingCacheMode: local
[04/14/2026-01:36:48] [I] timingCacheFile:
[04/14/2026-01:36:48] [I] Input(s)s format: fp32:CHW
[04/14/2026-01:36:48] [I] Output(s)s format: fp32:CHW
[04/14/2026-01:36:48] [I] Input build shapes: model
[04/14/2026-01:36:48] [I] Input calibration shapes: model
[04/14/2026-01:36:48] [I] === System Options ===
[04/14/2026-01:36:48] [I] Device: 0
[04/14/2026-01:36:48] [I] DLACore:
[04/14/2026-01:36:48] [I] Plugins:
[04/14/2026-01:36:48] [I] === Inference Options ===
[04/14/2026-01:36:48] [I] Batch: 1
[04/14/2026-01:36:48] [I] Input inference shapes: model
[04/14/2026-01:36:48] [I] Iterations: 100
[04/14/2026-01:36:48] [I] Duration: 3s (+ 50ms warm up)
[04/14/2026-01:36:48] [I] Sleep time: 0ms
[04/14/2026-01:36:48] [I] Streams: 1
[04/14/2026-01:36:48] [I] ExposeDMA: Disabled
[04/14/2026-01:36:48] [I] Data transfers: Enabled
[04/14/2026-01:36:48] [I] Spin-wait: Disabled
[04/14/2026-01:36:48] [I] Multithreading: Disabled
[04/14/2026-01:36:48] [I] CUDA Graph: Disabled
[04/14/2026-01:36:48] [I] Separate profiling: Disabled
[04/14/2026-01:36:48] [I] Time Deserialize: Disabled
[04/14/2026-01:36:48] [I] Time Refit: Disabled
[04/14/2026-01:36:48] [I] Skip inference: Disabled
[04/14/2026-01:36:48] [I] Inputs:
[04/14/2026-01:36:48] [I] === Reporting Options ===
[04/14/2026-01:36:48] [I] Verbose: Disabled
[04/14/2026-01:36:48] [I] Averages: 10 inferences
[04/14/2026-01:36:48] [I] Percentile: 99
[04/14/2026-01:36:48] [I] Dump refittable layers:Disabled
[04/14/2026-01:36:48] [I] Dump output: Disabled
[04/14/2026-01:36:48] [I] Profile: Disabled
[04/14/2026-01:36:48] [I] Export timing to JSON file:
[04/14/2026-01:36:48] [I] Export output to JSON file:
[04/14/2026-01:36:48] [I] Export profile to JSON file:
[04/14/2026-01:36:48] [I]
[04/14/2026-01:36:48] [I] === Device Information ===
[04/14/2026-01:36:48] [I] Selected Device: NVIDIA Tegra X1
[04/14/2026-01:36:48] [I] Compute Capability: 5.3
[04/14/2026-01:36:48] [I] SMs: 1
[04/14/2026-01:36:48] [I] Compute Clock Rate: 0.9216 GHz
[04/14/2026-01:36:48] [I] Device Global Memory: 3964 MiB
[04/14/2026-01:36:48] [I] Shared Memory per SM: 64 KiB
[04/14/2026-01:36:48] [I] Memory Bus Width: 64 bits (ECC disabled)
[04/14/2026-01:36:48] [I] Memory Clock Rate: 0.01275 GHz
[04/14/2026-01:36:48] [I]
[04/14/2026-01:36:48] [I] TensorRT version: 8001
[04/14/2026-01:36:50] [I] [TRT] [MemUsageChange] Init CUDA: CPU +203, GPU +0, now: CPU 232, GPU 2797 (MiB)
[04/14/2026-01:36:50] [I] [TRT] Loaded engine size: 10 MB
[04/14/2026-01:36:50] [I] [TRT] [MemUsageSnapshot] deserializeCudaEngine begin: CPU 232 MiB, GPU 2797 MiB
[04/14/2026-01:36:51] [I] [TRT] [MemUsageChange] Init cuBLAS/cuBLASLt: CPU +158, GPU +161, now: CPU 396, GPU 2961 (MiB)
[04/14/2026-01:36:52] [I] [TRT] [MemUsageChange] Init cuDNN: CPU +241, GPU +240, now: CPU 637, GPU 3201 (MiB)
[04/14/2026-01:36:52] [I] [TRT] [MemUsageChange] Init cuBLAS/cuBLASLt: CPU +0, GPU +0, now: CPU 636, GPU 3201 (MiB)
[04/14/2026-01:36:52] [I] [TRT] [MemUsageSnapshot] deserializeCudaEngine end: CPU 636 MiB, GPU 3201 MiB
[04/14/2026-01:36:52] [I] Engine loaded in 3.78183 sec.
[04/14/2026-01:36:52] [I] [TRT] [MemUsageSnapshot] ExecutionContext creation begin: CPU 626 MiB, GPU 3191 MiB
[04/14/2026-01:36:52] [I] [TRT] [MemUsageChange] Init cuBLAS/cuBLASLt: CPU +0, GPU +0, now: CPU 626, GPU 3191 (MiB)
[04/14/2026-01:36:52] [I] [TRT] [MemUsageChange] Init cuDNN: CPU +0, GPU +0, now: CPU 626, GPU 3191 (MiB)
[04/14/2026-01:36:52] [I] [TRT] [MemUsageSnapshot] ExecutionContext creation end: CPU 628 MiB, GPU 3196 MiB
[04/14/2026-01:36:52] [I] Created input binding for input with dimensions 1x3x640x640
[04/14/2026-01:36:52] [I] Created output binding for output with dimensions 1x8400x6
[04/14/2026-01:36:52] [I] Starting inference
[04/14/2026-01:36:58] [I] Warmup completed 1 queries over 50 ms
[04/14/2026-01:36:58] [I] Timing trace has 100 queries over 4.04082 s
[04/14/2026-01:36:58] [I]
[04/14/2026-01:36:58] [I] === Trace details ===
[04/14/2026-01:36:58] [I] Trace averages of 10 runs:
[04/14/2026-01:36:58] [I] Average on 10 runs - GPU latency: 39.8724 ms - Host latency: 40.3851 ms (end to end 40.3977 ms, enqueue 7.484 ms)
[04/14/2026-01:36:58] [I] Average on 10 runs - GPU latency: 39.8713 ms - Host latency: 40.3773 ms (end to end 40.3897 ms, enqueue 7.30795 ms)
[04/14/2026-01:36:58] [I] Average on 10 runs - GPU latency: 39.9067 ms - Host latency: 40.412 ms (end to end 40.4245 ms, enqueue 7.29104 ms)
[04/14/2026-01:36:58] [I] Average on 10 runs - GPU latency: 39.8893 ms - Host latency: 40.3991 ms (end to end 40.4114 ms, enqueue 7.121 ms)
[04/14/2026-01:36:58] [I] Average on 10 runs - GPU latency: 39.8917 ms - Host latency: 40.3979 ms (end to end 40.4102 ms, enqueue 7.13713 ms)
[04/14/2026-01:36:58] [I] Average on 10 runs - GPU latency: 39.874 ms - Host latency: 40.3799 ms (end to end 40.3922 ms, enqueue 7.18557 ms)
[04/14/2026-01:36:58] [I] Average on 10 runs - GPU latency: 39.8877 ms - Host latency: 40.3937 ms (end to end 40.4062 ms, enqueue 7.0707 ms)
[04/14/2026-01:36:58] [I] Average on 10 runs - GPU latency: 39.8963 ms - Host latency: 40.4062 ms (end to end 40.4185 ms, enqueue 7.3148 ms)
[04/14/2026-01:36:58] [I] Average on 10 runs - GPU latency: 39.875 ms - Host latency: 40.3824 ms (end to end 40.3948 ms, enqueue 7.39165 ms)
[04/14/2026-01:36:58] [I] Average on 10 runs - GPU latency: 39.9121 ms - Host latency: 40.4189 ms (end to end 40.4311 ms, enqueue 7.18472 ms)
[04/14/2026-01:36:58] [I]
[04/14/2026-01:36:58] [I] === Performance summary ===
[04/14/2026-01:36:58] [I] Throughput: 24.7474 qps
[04/14/2026-01:36:58] [I] Latency: min = 40.2976 ms, max = 40.6343 ms, mean = 40.3953 ms, median = 40.3808 ms, percentile(99%) = 40.6343 ms
[04/14/2026-01:36:58] [I] End-to-End Host Latency: min = 40.3104 ms, max = 40.647 ms, mean = 40.4076 ms, median = 40.3934 ms, percentile(99%) = 40.647 ms
[04/14/2026-01:36:58] [I] Enqueue Time: min = 6.76562 ms, max = 8.41187 ms, mean = 7.24886 ms, median = 7.18372 ms, percentile(99%) = 8.41187 ms
[04/14/2026-01:36:58] [I] H2D Latency: min = 0.471436 ms, max = 0.553223 ms, mean = 0.476471 ms, median = 0.474121 ms, percentile(99%) = 0.553223 ms
[04/14/2026-01:36:58] [I] GPU Compute Time: min = 39.795 ms, max = 40.1282 ms, mean = 39.8877 ms, median = 39.875 ms, percentile(99%) = 40.1282 ms
[04/14/2026-01:36:58] [I] D2H Latency: min = 0.0292969 ms, max = 0.0351562 ms, mean = 0.0311401 ms, median = 0.03125 ms, percentile(99%) = 0.0351562 ms
[04/14/2026-01:36:58] [I] Total Host Walltime: 4.04082 s
[04/14/2026-01:36:58] [I] Total GPU Compute Time: 3.98877 s
[04/14/2026-01:36:58] [I] Explanations of the performance metrics are printed in the verbose logs.
[04/14/2026-01:36:58] [I]
&&&& PASSED TensorRT.trtexec [TensorRT v8001] # /usr/src/tensorrt/bin/trtexec --loadEngine=/root/deepstream_yolo/best_deepstream.onnx_b1_gpu0_fp16.engine --batch=1 --iterations=100 --warmUp=50 --fp16
[04/14/2026-01:36:58] [I] [TRT] [MemUsageChange] Init cuBLAS/cuBLASLt: CPU +0, GPU +0, now: CPU 866, GPU 3440 (MiB)