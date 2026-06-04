#pragma once

#include <queue>
#include <mutex>
#include <condition_variable>
#include <optional>

namespace edge {
namespace core {

template<typename T>
class SafeQueue {
public:
    explicit SafeQueue(size_t max_size = 0) : max_size_(max_size) {}

    bool push(T item) {
        std::unique_lock<std::mutex> lock(mutex_);
        if (max_size_ > 0 && queue_.size() >= max_size_) {
            return false; // Queue full
        }
        queue_.push(std::move(item));
        lock.unlock();
        cond_.notify_one();
        return true;
    }

    std::optional<T> pop(std::chrono::milliseconds timeout) {
        std::unique_lock<std::mutex> lock(mutex_);
        if (!cond_.wait_for(lock, timeout, [this] { return !queue_.empty(); })) {
            return std::nullopt; // Timeout
        }
        T item = std::move(queue_.front());
        queue_.pop();
        return item;
    }

    size_t size() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return queue_.size();
    }

private:
    std::queue<T> queue_;
    mutable std::mutex mutex_;
    std::condition_variable cond_;
    size_t max_size_;
};

} // namespace core
} // namespace edge
