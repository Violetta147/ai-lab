#pragma once

#include "../../include/safe_queue.hpp"
#include "../../include/types.hpp"
#include <thread>
#include <atomic>

namespace edge {
namespace core {

class DiskWriterThread {
public:
    DiskWriterThread(SafeQueue<BufferItem>& queue);
    ~DiskWriterThread();

    // Prevent copies (C.21)
    DiskWriterThread(const DiskWriterThread&) = delete;
    DiskWriterThread& operator=(const DiskWriterThread&) = delete;
    DiskWriterThread(DiskWriterThread&&) = delete;
    DiskWriterThread& operator=(DiskWriterThread&&) = delete;

    void start();
    void stop();

private:
    void run();

    SafeQueue<BufferItem>& queue_;
    std::thread thread_;
    std::atomic<bool> running_{false};
};

} // namespace core
} // namespace edge
