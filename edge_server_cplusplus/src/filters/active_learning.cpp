#include "active_learning.hpp"
#include "../../include/config.hpp"
#include <iostream>

namespace edge {
namespace filters {

ActiveLearningFilter::ActiveLearningFilter() {}

std::pair<bool, std::string> ActiveLearningFilter::analyze_image_quality(const cv::Mat& frame) const {
    cv::Mat gray;
    cv::cvtColor(frame, gray, cv::COLOR_BGR2GRAY);

    cv::Scalar mean_scalar = cv::mean(gray);
    double brightness = mean_scalar[0];

    if (brightness < config::ACTIVE_LEARNING_MIN_BRIGHTNESS) {
        return {true, "OOD: Too Dark (brightness=" + std::to_string(brightness) + ")"};
    }
    if (brightness > config::ACTIVE_LEARNING_MAX_BRIGHTNESS) {
        return {true, "OOD: Too Bright/Glare (brightness=" + std::to_string(brightness) + ")"};
    }

    cv::Mat laplacian;
    cv::Laplacian(gray, laplacian, CV_64F);
    cv::Scalar mean, stddev;
    cv::meanStdDev(laplacian, mean, stddev);
    double blur_val = stddev.val[0] * stddev.val[0];

    if (blur_val < config::ACTIVE_LEARNING_MIN_BLUR) {
        return {true, "OOD: Blurry (Val: " + std::to_string(blur_val) + ")"};
    }

    return {false, ""};
}

std::pair<bool, std::string> ActiveLearningFilter::should_save_frame(const cv::Mat& frame, const std::vector<Detection>& detections) const {
    for (const auto& det : detections) {
        if (det.conf >= config::ACTIVE_LEARNING_CONF_MIN && det.conf <= config::ACTIVE_LEARNING_CONF_MAX) {
            return {true, "Uncertainty: Class " + det.class_name + " at " + std::to_string(det.conf)};
        }
    }

    if (!detections.empty()) {
        auto [is_ood, reason] = analyze_image_quality(frame);
        if (is_ood) {
            return {true, reason};
        }
    }

    return {false, "Clear"};
}

} // namespace filters
} // namespace edge
