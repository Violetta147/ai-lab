#pragma once

#include <opencv2/opencv.hpp>
#include <string>
#include <utility>

namespace edge {
namespace filters {

class PublishGate {
public:
    PublishGate();

    std::pair<bool, std::string> should_publish(const cv::Mat& frame);

private:
    cv::Mat frame_hash(const cv::Mat& frame) const;
    int hamming_distance(const cv::Mat& left, const cv::Mat& right) const;

    double last_publish_ts_{0.0};
    double window_start_ts_{0.0};
    int window_upload_count_{0};
    cv::Mat last_frame_hash_;
};

} // namespace filters
} // namespace edge
