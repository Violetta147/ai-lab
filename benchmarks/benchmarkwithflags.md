root@nano:/opt/nvidia/deepstream/deepstream-6.0# /usr/src/tensorrt/bin/trtexec --loadEngine=/root/deepstream_yolo/best_deepstream.onnx_b1_gpu0_fp16.engine --batch=1 --iterations=100 --warmUp=50 --fp16 --exportTimes=times.json --exportProfile=profile.json
&&&& RUNNING TensorRT.trtexec [TensorRT v8001] # /usr/src/tensorrt/bin/trtexec --loadEngine=/root/deepstream_yolo/best_deepstream.onnx_b1_gpu0_fp16.engine --batch=1 --iterations=100 --warmUp=50 --fp16 --exportTimes=times.json --exportProfile=profile.json
[04/14/2026-01:43:06] [I] === Model Options ===
[04/14/2026-01:43:06] [I] Format: *
[04/14/2026-01:43:06] [I] Model:
[04/14/2026-01:43:06] [I] Output:
[04/14/2026-01:43:06] [I] === Build Options ===
[04/14/2026-01:43:06] [I] Max batch: 1
[04/14/2026-01:43:06] [I] Workspace: 16 MiB
[04/14/2026-01:43:06] [I] minTiming: 1
[04/14/2026-01:43:06] [I] avgTiming: 8
[04/14/2026-01:43:06] [I] Precision: FP32+FP16
[04/14/2026-01:43:06] [I] Calibration:
[04/14/2026-01:43:06] [I] Refit: Disabled
[04/14/2026-01:43:06] [I] Sparsity: Disabled
[04/14/2026-01:43:06] [I] Safe mode: Disabled
[04/14/2026-01:43:06] [I] Restricted mode: Disabled
[04/14/2026-01:43:06] [I] Save engine:
[04/14/2026-01:43:06] [I] Load engine: /root/deepstream_yolo/best_deepstream.onnx_b1_gpu0_fp16.engine
[04/14/2026-01:43:06] [I] NVTX verbosity: 0
[04/14/2026-01:43:06] [I] Tactic sources: Using default tactic sources
[04/14/2026-01:43:06] [I] timingCacheMode: local
[04/14/2026-01:43:06] [I] timingCacheFile:
[04/14/2026-01:43:06] [I] Input(s)s format: fp32:CHW
[04/14/2026-01:43:06] [I] Output(s)s format: fp32:CHW
[04/14/2026-01:43:06] [I] Input build shapes: model
[04/14/2026-01:43:06] [I] Input calibration shapes: model
[04/14/2026-01:43:06] [I] === System Options ===
[04/14/2026-01:43:06] [I] Device: 0
[04/14/2026-01:43:06] [I] DLACore:
[04/14/2026-01:43:06] [I] Plugins:
[04/14/2026-01:43:06] [I] === Inference Options ===
[04/14/2026-01:43:06] [I] Batch: 1
[04/14/2026-01:43:06] [I] Input inference shapes: model
[04/14/2026-01:43:06] [I] Iterations: 100
[04/14/2026-01:43:06] [I] Duration: 3s (+ 50ms warm up)
[04/14/2026-01:43:06] [I] Sleep time: 0ms
[04/14/2026-01:43:06] [I] Streams: 1
[04/14/2026-01:43:06] [I] ExposeDMA: Disabled
[04/14/2026-01:43:06] [I] Data transfers: Enabled
[04/14/2026-01:43:06] [I] Spin-wait: Disabled
[04/14/2026-01:43:06] [I] Multithreading: Disabled
[04/14/2026-01:43:06] [I] CUDA Graph: Disabled
[04/14/2026-01:43:06] [I] Separate profiling: Disabled
[04/14/2026-01:43:06] [I] Time Deserialize: Disabled
[04/14/2026-01:43:06] [I] Time Refit: Disabled
[04/14/2026-01:43:06] [I] Skip inference: Disabled
[04/14/2026-01:43:06] [I] Inputs:
[04/14/2026-01:43:06] [I] === Reporting Options ===
[04/14/2026-01:43:06] [I] Verbose: Disabled
[04/14/2026-01:43:06] [I] Averages: 10 inferences
[04/14/2026-01:43:06] [I] Percentile: 99
[04/14/2026-01:43:06] [I] Dump refittable layers:Disabled
[04/14/2026-01:43:06] [I] Dump output: Disabled
[04/14/2026-01:43:06] [I] Profile: Disabled
[04/14/2026-01:43:06] [I] Export timing to JSON file: times.json
[04/14/2026-01:43:06] [I] Export output to JSON file:
[04/14/2026-01:43:06] [I] Export profile to JSON file: profile.json
[04/14/2026-01:43:06] [I]
[04/14/2026-01:43:06] [I] === Device Information ===
[04/14/2026-01:43:06] [I] Selected Device: NVIDIA Tegra X1
[04/14/2026-01:43:06] [I] Compute Capability: 5.3
[04/14/2026-01:43:06] [I] SMs: 1
[04/14/2026-01:43:06] [I] Compute Clock Rate: 0.9216 GHz
[04/14/2026-01:43:06] [I] Device Global Memory: 3964 MiB
[04/14/2026-01:43:06] [I] Shared Memory per SM: 64 KiB
[04/14/2026-01:43:06] [I] Memory Bus Width: 64 bits (ECC disabled)
[04/14/2026-01:43:06] [I] Memory Clock Rate: 0.01275 GHz
[04/14/2026-01:43:06] [I]
[04/14/2026-01:43:06] [I] TensorRT version: 8001
[04/14/2026-01:43:07] [I] [TRT] [MemUsageChange] Init CUDA: CPU +203, GPU +0, now: CPU 232, GPU 2795 (MiB)
[04/14/2026-01:43:07] [I] [TRT] Loaded engine size: 10 MB
[04/14/2026-01:43:07] [I] [TRT] [MemUsageSnapshot] deserializeCudaEngine begin: CPU 232 MiB, GPU 2795 MiB
[04/14/2026-01:43:09] [I] [TRT] [MemUsageChange] Init cuBLAS/cuBLASLt: CPU +158, GPU +160, now: CPU 396, GPU 2961 (MiB)
[04/14/2026-01:43:10] [I] [TRT] [MemUsageChange] Init cuDNN: CPU +240, GPU +241, now: CPU 636, GPU 3202 (MiB)
[04/14/2026-01:43:10] [I] [TRT] [MemUsageChange] Init cuBLAS/cuBLASLt: CPU +0, GPU +0, now: CPU 636, GPU 3202 (MiB)
[04/14/2026-01:43:10] [I] [TRT] [MemUsageSnapshot] deserializeCudaEngine end: CPU 636 MiB, GPU 3202 MiB
[04/14/2026-01:43:10] [I] Engine loaded in 3.86437 sec.
[04/14/2026-01:43:10] [I] [TRT] [MemUsageSnapshot] ExecutionContext creation begin: CPU 626 MiB, GPU 3191 MiB
[04/14/2026-01:43:10] [I] [TRT] [MemUsageChange] Init cuBLAS/cuBLASLt: CPU +0, GPU +0, now: CPU 626, GPU 3192 (MiB)
[04/14/2026-01:43:10] [I] [TRT] [MemUsageChange] Init cuDNN: CPU +0, GPU +0, now: CPU 626, GPU 3192 (MiB)
[04/14/2026-01:43:10] [I] [TRT] [MemUsageSnapshot] ExecutionContext creation end: CPU 628 MiB, GPU 3195 MiB
[04/14/2026-01:43:10] [I] Created input binding for input with dimensions 1x3x640x640
[04/14/2026-01:43:10] [I] Created output binding for output with dimensions 1x8400x6
[04/14/2026-01:43:10] [I] Starting inference
[04/14/2026-01:43:16] [I] Warmup completed 1 queries over 50 ms
[04/14/2026-01:43:16] [I] Timing trace has 100 queries over 4.07195 s
[04/14/2026-01:43:16] [I]
[04/14/2026-01:43:16] [I] === Trace details ===
[04/14/2026-01:43:16] [I] Trace averages of 10 runs:
[04/14/2026-01:43:16] [I] Average on 10 runs - GPU latency: 39.9924 ms - Host latency: 40.6451 ms (end to end 40.7041 ms, enqueue 40.4169 ms)
[04/14/2026-01:43:16] [I] Average on 10 runs - GPU latency: 39.9946 ms - Host latency: 40.6483 ms (end to end 40.7067 ms, enqueue 40.4197 ms)
[04/14/2026-01:43:16] [I] Average on 10 runs - GPU latency: 39.9997 ms - Host latency: 40.641 ms (end to end 40.6904 ms, enqueue 40.4258 ms)
[04/14/2026-01:43:16] [I] Average on 10 runs - GPU latency: 40.0082 ms - Host latency: 40.6253 ms (end to end 40.6647 ms, enqueue 40.4338 ms)
[04/14/2026-01:43:16] [I] Average on 10 runs - GPU latency: 40.0125 ms - Host latency: 40.6267 ms (end to end 40.6629 ms, enqueue 40.4323 ms)
[04/14/2026-01:43:16] [I] Average on 10 runs - GPU latency: 40.0071 ms - Host latency: 40.634 ms (end to end 40.6737 ms, enqueue 40.432 ms)
[04/14/2026-01:43:16] [I] Average on 10 runs - GPU latency: 40.0058 ms - Host latency: 40.6466 ms (end to end 40.6978 ms, enqueue 40.4298 ms)
[04/14/2026-01:43:16] [I] Average on 10 runs - GPU latency: 40.0311 ms - Host latency: 40.6389 ms (end to end 40.6729 ms, enqueue 40.4555 ms)
[04/14/2026-01:43:16] [I] Average on 10 runs - GPU latency: 39.9994 ms - Host latency: 40.6202 ms (end to end 40.6588 ms, enqueue 40.425 ms)
[04/14/2026-01:43:16] [I] Average on 10 runs - GPU latency: 39.9765 ms - Host latency: 40.6 ms (end to end 40.6391 ms, enqueue 40.4031 ms)
[04/14/2026-01:43:16] [I]
[04/14/2026-01:43:16] [I] === Performance summary ===
[04/14/2026-01:43:16] [I] Throughput: 24.5583 qps
[04/14/2026-01:43:16] [I] Latency: min = 40.5005 ms, max = 40.8591 ms, mean = 40.6326 ms, median = 40.6337 ms, percentile(99%) = 40.8591 ms
[04/14/2026-01:43:16] [I] End-to-End Host Latency: min = 40.5388 ms, max = 40.9277 ms, mean = 40.6771 ms, median = 40.6718 ms, percentile(99%) = 40.9277 ms
[04/14/2026-01:43:16] [I] Enqueue Time: min = 40.2849 ms, max = 40.6204 ms, mean = 40.4274 ms, median = 40.4176 ms, percentile(99%) = 40.6204 ms
[04/14/2026-01:43:16] [I] H2D Latency: min = 0.487671 ms, max = 0.590698 ms, mean = 0.544677 ms, median = 0.543213 ms, percentile(99%) = 0.590698 ms
[04/14/2026-01:43:16] [I] GPU Compute Time: min = 39.8569 ms, max = 40.1931 ms, mean = 40.0027 ms, median = 39.9982 ms, percentile(99%) = 40.1931 ms
[04/14/2026-01:43:16] [I] D2H Latency: min = 0.0678711 ms, max = 0.150146 ms, mean = 0.0852185 ms, median = 0.079834 ms, percentile(99%) = 0.150146 ms
[04/14/2026-01:43:16] [I] Total Host Walltime: 4.07195 s
[04/14/2026-01:43:16] [I] Total GPU Compute Time: 4.00027 s
[04/14/2026-01:43:16] [W] * Throughput may be bound by Enqueue Time rather than GPU Compute and the GPU may be under-utilized.
[04/14/2026-01:43:16] [W]   If not already in use, --useCudaGraph (utilize CUDA graphs where possible) may increase the throughput.
[04/14/2026-01:43:16] [I] Explanations of the performance metrics are printed in the verbose logs.
[04/14/2026-01:43:16] [I]
&&&& PASSED TensorRT.trtexec [TensorRT v8001] # /usr/src/tensorrt/bin/trtexec --loadEngine=/root/deepstream_yolo/best_deepstream.onnx_b1_gpu0_fp16.engine --batch=1 --iterations=100 --warmUp=50 --fp16 --exportTimes=times.json --exportProfile=profile.json
[04/14/2026-01:43:16] [I] [TRT] [MemUsageChange] Init cuBLAS/cuBLASLt: CPU +0, GPU +0, now: CPU 866, GPU 3438 (MiB)