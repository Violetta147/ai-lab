# 🛠️ Jetson Nano Deployment & Troubleshooting Guide

This guide documents the known issues, root causes, and configurations required to run the C++ Edge AI Server (`edge_server_cplusplus`) stably on the NVIDIA Jetson Nano.

---

## 1. Crash: `[SyncThread] Exception: std::bad_alloc`

### Symptom
The background syncing thread crashes repeatedly with `std::bad_alloc` even though `tegrastats` or system monitoring shows there is still ~800MB of free RAM:
```text
[SyncThread] Exception: std::bad_alloc
[SyncThread] Memory at crash - Free RAM: 850 MB / 3964 MB
```

### Root Cause
This is a concurrency bug in C++17's `std::filesystem::directory_iterator` under GCC on Linux (specifically on ARM64/Jetpack). 
While the background `SyncThread` is iterating over the `buffer/` directory, the `DiskWriterThread` is simultaneously creating, writing, and renaming files (`.tmp` to `.json`) in the same directory. This concurrent modification invalidates the iterator, causing it to hold a dangling reference. When the code attempts to call `entry.path()`, it dereferences garbage memory and throws a `std::bad_alloc`.

### Solution
The code was migrated in `sync_thread.cpp` to use the POSIX directory traversal API (`opendir` / `readdir` from `<dirent.h>`) on Linux, while keeping `std::filesystem` as a fallback for Windows development:
* POSIX `readdir` reads files directly from the OS page cache using low-level system calls, which is thread-safe at the kernel level and never throws C++ allocator exceptions when directories are modified concurrently.

---

## 2. Error: `[MinioClient] Upload failed with HTTP code: 400` (SigV4 Error)

### Symptom
The sync thread is unable to upload raw frames to MinIO, printing:
```xml
<Error>
  <Code>InvalidRequest</Code>
  <Message>The authorization mechanism you have provided is not supported. Please use AWS4-HMAC-SHA256.</Message>
</Error>
```

### Root Cause
1. **Outdated libcurl:** The default `libcurl` version installed on JetPack 4.x (Ubuntu 18.04) or JetPack 5.x (Ubuntu 20.04) is older than **7.75.0**. The `CURLOPT_AWS_SIGV4` option (AWS Signature V4) was only introduced in libcurl `7.75.0`. Older libcurl libraries ignore this option and fall back to Basic Auth, which MinIO rejects for S3 API uploads. 
2. **Dynamic Linker Cache:** If you compile a newer curl version (like `curl-8.7.1`) into `/usr/local/lib` but do not configure the dynamic linker search path, the binary will link to the old system `libcurl.so` at runtime and fail.
3. **Invalid SigV4 Parameter Typo:** The C++ code previously passed `"s3:us-east-1:auto"` to `CURLOPT_AWS_SIGV4`. This is an invalid format. The correct format for S3/MinIO is `aws:amz:[region]:[service]` (i.e., `"aws:amz:us-east-1:s3"`). Passing the wrong format causes libcurl to generate incorrect signatures, which MinIO rejects with `InvalidRequest` (AWS4-HMAC-SHA256 required).

### Solution
1. **Fix Code Parameter:** Update the `CURLOPT_AWS_SIGV4` parameter in [minio_client.cpp](file:///d:/datas/Final.yolov8/edge_server_cplusplus/src/clients/minio_client.cpp) to `"aws:amz:us-east-1:s3"`.
2. **Configure LD_LIBRARY_PATH:** Force the OS to prioritize loading the newly compiled `libcurl.so` from `/usr/local/lib` by setting the `LD_LIBRARY_PATH` environment variable.

#### Temporary Run:
```bash
LD_LIBRARY_PATH=/usr/local/lib ./edge_server
```

#### Permanent Setup (Recommended):
Run this on the Jetson Nano to add the path to your shell profile so you don't have to specify it every time:
```bash
echo 'export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

---

## 3. Jetson RAM & SWAP Optimization (SD Card Safety)

### Warning
Running YOLOv8 TensorRT models and RTSP video decoding on a 4GB Jetson Nano consumes nearly all available RAM.
* **DO NOT** create a traditional swap file on the SD card (e.g. `/swapfile`). The heavy and continuous writes from swap page faults will degrade and kill the SD card in a matter of weeks.

### Solution: Enable ZRAM (Compressed RAM Swap)
ZRAM creates a compressed block device in the physical RAM. When RAM usage spikes, the Linux kernel compresses cold pages and stores them in ZRAM. This increases the effective RAM capacity to ~6-8GB with **zero write cycles to the SD card**.

Run the following commands on your Jetson Nano to configure ZRAM:
```bash
# Install the ZRAM configuration utility
sudo apt-get install zram-config

# Enable and start the ZRAM service
sudo systemctl enable zram-config
sudo systemctl start zram-config
```
Verify it is active by running `free -m` or `swapon -s`. You should see a swap partition on `/dev/zram0` (typically half the size of your total RAM).

---

## 4. Curl Symbol Lookup Error / CMake Warnings (`no version information available`)

### Symptom
When installing a custom compiled `curl` into `/usr/local/lib` and using `sudo ldconfig`, system tools that depend on `libcurl` (like `cmake`, `git`, `apt`) may throw warnings or errors such as:
```text
curl: symbol lookup error: curl: undefined symbol: curl_easy_nextheader
```
or
```text
cmake: /usr/local/lib/libcurl.so.4: no version information available (required by /usr/bin/cmake)
```

### Root Cause
System tools on Ubuntu are compiled against Debian's specific version of `libcurl` which uses proprietary version tags (like `CURL_OPENSSL_4`). When you overwrite or prioritize `/usr/local/lib/libcurl.so.4` globally, these tools fail to find the expected tags. 

### Solution (Isolated Installation)
To safely compile `curl` with AWS SigV4 support (required for MinIO uploads) without breaking your OS, you should **isolate** the installation to a project-specific directory rather than installing it globally.

**Step 1: Clean up the global install**
Remove the custom curl from `/usr/local` and restore system defaults.
```bash
# Inside the curl source directory
cd ~/curl-8.7.1
sudo make uninstall
sudo ldconfig

# IMPORTANT: Also remove the LD_LIBRARY_PATH override from your ~/.bashrc if you added it!
# nano ~/.bashrc -> remove the export LD_LIBRARY_PATH=/usr/local/lib line -> source ~/.bashrc
```

**Step 2: Compile Curl to an Isolated Directory**
Compile the new `curl` version with OpenSSL into a custom folder (e.g., `~/target-curl`).
```bash
cd ~/curl-8.7.1
./configure --prefix=$HOME/target-curl --with-openssl --enable-versioned-symbols
make -j$(nproc)
make install
```
*(No `sudo` is required because it's in your home directory).*

**Step 3: Build and Run the Edge Server**
Configure your C++ project to exclusively use the isolated curl library using `CMAKE_PREFIX_PATH`.
```bash
cd ~/edge_server_cplusplus/build
rm -rf *  # Clear the cmake cache
cmake -DCMAKE_PREFIX_PATH=$HOME/target-curl ..
make -j$(nproc)

# Run the server by temporarily pointing the dynamic linker to the isolated library
LD_LIBRARY_PATH=$HOME/target-curl/lib ./edge_server
```

