#pragma once

#include <opencv2/opencv.hpp>
#include <string>
#include <utility>
#include "types.hpp"

namespace edge {
namespace filters {

class ActiveLearningFilter {
public:
    ActiveLearningFilter();

    std::pair<bool, std::string> analyze_image_quality(const cv::Mat& frame) const;
    std::pair<bool, std::string> should_save_frame(const cv::Mat& frame, const std::vector<Detection>& detections) const;
};

} // namespace filters
} // namespace edge
