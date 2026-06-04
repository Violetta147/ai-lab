#include "publish_gate.hpp"
#include "../../include/config.hpp"
#include <chrono>

namespace edge {
namespace filters {

static double get_current_time_sec() {
    auto now = std::chrono::steady_clock::now();
    return std::chrono::duration<double>(now.time_since_epoch()).count();
}

PublishGate::PublishGate() {
    window_start_ts_ = get_current_time_sec();
}

cv::Mat PublishGate::frame_hash(const cv::Mat& frame) const {
    cv::Mat gray, resized;
    cv::cvtColor(frame, gray, cv::COLOR_BGR2GRAY);
    cv::resize(gray, resized, cv::Size(8, 8), 0, 0, cv::INTER_AREA);
    
    cv::Scalar mean = cv::mean(resized);
    cv::Mat hash;
    cv::compare(resized, mean[0], hash, cv::CMP_GT);
    return hash;
}

int PublishGate::hamming_distance(const cv::Mat& left, const cv::Mat& right) const {
    cv::Mat diff;
    cv::bitwise_xor(left, right, diff);
    return cv::countNonZero(diff);
}

std::pair<bool, std::string> PublishGate::should_publish(const cv::Mat& frame) {
    double now = get_current_time_sec();
    
    if (now - last_publish_ts_ < config::PUBLISH_COOLDOWN_SECONDS) {
        double wait_left = config::PUBLISH_COOLDOWN_SECONDS - (now - last_publish_ts_);
        return {false, "Cooldown active (" + std::to_string(wait_left) + "s left)"};
    }

    if (now - window_start_ts_ >= config::PUBLISH_WINDOW_SECONDS) {
        window_start_ts_ = now;
        window_upload_count_ = 0;
    }

    if (window_upload_count_ >= config::MAX_UPLOADS_PER_WINDOW) {
        return {false, "Window quota reached"};
    }

    cv::Mat current_hash = frame_hash(frame);
    if (!last_frame_hash_.empty()) {
        int distance = hamming_distance(current_hash, last_frame_hash_);
        if (distance <= config::FRAME_DEDUP_PHASH_DISTANCE_MAX) {
            return {false, "Frame deduplicated (distance=" + std::to_string(distance) + ")"};
        }
    }

    last_publish_ts_ = now;
    window_upload_count_++;
    last_frame_hash_ = current_hash;
    return {true, "Publish gate accepted"};
}

} // namespace filters
} // namespace edge
