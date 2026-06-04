#pragma once

#include <string>
#include <vector>
#include <opencv2/opencv.hpp>
#include <chrono>

namespace edge {

struct Detection {
    std::string class_name;
    float conf;
    std::vector<int> bbox; // x1, y1, x2, y2
};

struct FrameMetadata {
    std::string camera_id;
    std::string image_url;
    double timestamp;
    std::string trigger_reason;
    std::vector<Detection> detections;
};

struct BufferItem {
    cv::Mat frame;
    FrameMetadata metadata;
};

} // namespace edge
