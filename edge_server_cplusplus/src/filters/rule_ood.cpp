#include "rule_ood.hpp"
#include "../../include/config.hpp"
#include <algorithm>
#include <iostream>

namespace edge {
namespace filters {

RuleBasedOodFilter::RuleBasedOodFilter() {
    vehicle_classes_ = {"bus", "truck", "car", "motorcycle"};
    // Just an example forbidden class list
    forbidden_classes_ = {"person", "bicycle"}; 
    
    // Example aspect ratio limits
    class_aspect_ratio_limits_map_["car"] = {0.5f, 2.5f};
    class_aspect_ratio_limits_map_["truck"] = {0.5f, 3.0f};
}

int RuleBasedOodFilter::touching_edges_count(float left, float top, float right, float bottom, float width, float height) const {
    const float tolerance_px = 2.0f;
    int edges = 0;
    if (left <= tolerance_px) edges++;
    if (top <= tolerance_px) edges++;
    if (right >= width - tolerance_px) edges++;
    if (bottom >= height - tolerance_px) edges++;
    return edges;
}

std::pair<bool, std::string> RuleBasedOodFilter::should_flag_ood(const std::vector<Detection>& detections, int frame_w, int frame_h) {
    if (!config::RULE_OOD_ENABLED) {
        return {false, "Rule OOD disabled"};
    }

    float frame_area = static_cast<float>(frame_w * frame_h);
    if (frame_area <= 0) {
        return {false, "Invalid frame area for rule-based OOD."};
    }

    float ood_score = 0.0f;
    std::vector<std::string> soft_reasons;

    for (const auto& det : detections) {
        float left = det.bbox[0];
        float top = det.bbox[1];
        float right = det.bbox[2];
        float bottom = det.bbox[3];
        
        float width = std::max(1.0f, right - left);
        float height = std::max(1.0f, bottom - top);
        float area_ratio = (width * height) / frame_area;
        float center_y_norm = ((top + bottom) * 0.5f) / static_cast<float>(frame_h);
        float aspect_h_over_w = height / width;
        const std::string& class_name = det.class_name;

        if (forbidden_classes_.count(class_name) > 0) {
            ood_score += config::RULE_OOD_SCORE_FORBIDDEN_CLASS;
            soft_reasons.push_back("Forbidden class: " + class_name);
        }

        if (area_ratio >= config::RULE_OOD_EXTREME_AREA_MAX_RATIO) {
            ood_score += config::RULE_OOD_SCORE_EXTREME_AREA;
            soft_reasons.push_back("Extreme scale: class=" + class_name);
        }

        if (class_name == "bus" && aspect_h_over_w >= config::RULE_OOD_BUS_VERTICAL_RATIO_MIN) {
            ood_score += config::RULE_OOD_SCORE_BUS_VERTICAL;
            soft_reasons.push_back("Bus vertical shape");
        }

        auto it = class_aspect_ratio_limits_map_.find(class_name);
        if (it != class_aspect_ratio_limits_map_.end()) {
            if (aspect_h_over_w < it->second.first || aspect_h_over_w > it->second.second) {
                ood_score += config::RULE_OOD_SCORE_ASPECT_RATIO;
                soft_reasons.push_back("Aspect ratio out-of-range: class=" + class_name);
            }
        }

        if (vehicle_classes_.count(class_name) > 0 && center_y_norm <= config::RULE_OOD_VEHICLE_TOP_ZONE_MAX_Y) {
            ood_score += config::RULE_OOD_SCORE_TOP_ZONE_VEHICLE;
            soft_reasons.push_back("Vehicle in top zone: class=" + class_name);
        }

        int touched_edges = touching_edges_count(left, top, right, bottom, static_cast<float>(frame_w), static_cast<float>(frame_h));
        if (touched_edges >= config::RULE_OOD_EDGE_TOUCH_MIN_EDGES && area_ratio >= config::RULE_OOD_EDGE_TOUCH_MIN_AREA_RATIO) {
            ood_score += config::RULE_OOD_SCORE_EDGE_TOUCH;
            soft_reasons.push_back("Edge-touch large box");
        }
    }

    bool is_score_hit = ood_score >= config::RULE_OOD_SCORE_THRESHOLD;
    
    persistence_history_.push_back(is_score_hit);
    if (persistence_history_.size() > static_cast<size_t>(config::RULE_OOD_PERSISTENCE_WINDOW_FRAMES)) {
        persistence_history_.pop_front();
    }

    int soft_hits = std::count(persistence_history_.begin(), persistence_history_.end(), true);
    
    if (is_score_hit && soft_hits >= config::RULE_OOD_PERSISTENCE_MIN_HITS) {
        std::string reason = "Rule OOD score=" + std::to_string(ood_score) + " | hits=" + std::to_string(soft_hits);
        if (!soft_reasons.empty()) {
            reason += " | " + soft_reasons[0];
        }
        return {true, reason};
    }
    
    if (is_score_hit) {
        std::string reason = "Rule OOD score hit but waiting persistence";
        if (!soft_reasons.empty()) {
            reason += " | " + soft_reasons[0];
        }
        return {false, reason};
    }

    return {false, "Rule OOD clear"};
}

} // namespace filters
} // namespace edge
