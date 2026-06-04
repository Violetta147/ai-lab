#pragma once

#include "types.hpp"
#include <string>
#include <utility>
#include <vector>
#include <deque>
#include <unordered_set>
#include <unordered_map>

namespace edge {
namespace filters {

class RuleBasedOodFilter {
public:
    RuleBasedOodFilter();

    std::pair<bool, std::string> should_flag_ood(const std::vector<Detection>& detections, int frame_w, int frame_h);

private:
    int touching_edges_count(float left, float top, float right, float bottom, float width, float height) const;

    std::unordered_set<std::string> vehicle_classes_;
    std::unordered_set<std::string> forbidden_classes_;
    std::unordered_map<std::string, std::pair<float, float>> class_aspect_ratio_limits_map_;
    std::deque<bool> persistence_history_;
};

} // namespace filters
} // namespace edge
