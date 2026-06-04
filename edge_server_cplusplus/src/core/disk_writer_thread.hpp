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
