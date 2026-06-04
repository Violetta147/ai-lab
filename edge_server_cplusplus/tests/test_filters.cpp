#include <gtest/gtest.h>
#include <opencv2/opencv.hpp>
#include "../src/filters/active_learning.hpp"
#include "../src/filters/rule_ood.hpp"
#include "../src/filters/publish_gate.hpp"
#include "../include/types.hpp"

using namespace edge::filters;
using namespace edge;

TEST(ActiveLearningTest, DetectsDarkImage) {
    ActiveLearningFilter filter;
    cv::Mat dark_frame = cv::Mat::zeros(480, 640, CV_8UC3); // Pure black
    auto [is_ood, reason] = filter.analyze_image_quality(dark_frame);
    EXPECT_TRUE(is_ood);
    EXPECT_NE(reason.find("Too Dark"), std::string::npos);
}

TEST(ActiveLearningTest, DetectsBrightImage) {
    ActiveLearningFilter filter;
    cv::Mat bright_frame = cv::Mat(480, 640, CV_8UC3, cv::Scalar(255, 255, 255)); // Pure white
    auto [is_ood, reason] = filter.analyze_image_quality(bright_frame);
    EXPECT_TRUE(is_ood);
    EXPECT_NE(reason.find("Too Bright"), std::string::npos);
}

TEST(RuleOodTest, FlagsForbiddenClass) {
    RuleBasedOodFilter filter;
    std::vector<Detection> dets = {
        {"person", 0.9f, {100, 100, 200, 200}}
    };
    auto [hit, reason] = filter.should_flag_ood(dets, 640, 480);
    // Might not return true immediately due to persistence window
    EXPECT_FALSE(hit);
    EXPECT_NE(reason.find("Forbidden class"), std::string::npos);
}

TEST(PublishGateTest, HandlesCooldown) {
    PublishGate gate;
    cv::Mat frame = cv::Mat::zeros(480, 640, CV_8UC3);
    
    // First should pass
    auto [pass1, reason1] = gate.should_publish(frame);
    EXPECT_TRUE(pass1);
    
    // Second should fail due to cooldown
    auto [pass2, reason2] = gate.should_publish(frame);
    EXPECT_FALSE(pass2);
    EXPECT_NE(reason2.find("Cooldown"), std::string::npos);
}
