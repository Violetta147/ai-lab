#ifndef TRAFFIC_ANALYZER_HPP
#define TRAFFIC_ANALYZER_HPP

#include <opencv2/opencv.hpp>
#include <vector>
#include <deque>
#include <map>
#include "bt_byte_tracker.hpp"

class TrafficAnalyzer {
public:
    TrafficAnalyzer(int frame_w = 640, int frame_h = 480);
    
    // Hàm cập nhật chính: gọi sau khi có kết quả từ ByteTrack
    void update(const std::vector<STrack>& tracks, double fps);
    
    // Hàm vẽ HUD và kết quả lên frame
    void draw(cv::Mat& frame);

private:
    int w, h;
    
    // --- 1. Absolute Count & ROI ---
    std::vector<cv::Point> roi_polygon;
    double road_length_km = 0.1;
    int count_n = 0;

    // --- 2. PCE (Passenger Car Equivalent) ---
    // Thứ tự: bus (0), car (1), motor (2), truck (3)
    std::vector<double> pce_weights; 
    double density_pce_k = 0.0;

    // --- 3. Area Occupancy (BEV) ---
    cv::Mat homography;
    int bev_size = 300;
    double occupancy_pct = 0.0;
    cv::Mat bev_canvas;

    // --- 4. Fundamental Equation (k = q/v) ---
    cv::Point2f entry_s, entry_e, exit_s, exit_e;
    double zone_dist_km = 0.03;
    std::map<int, int> entry_timestamps; // track_id -> frame_idx
    std::deque<int> exit_frames;         // Lưu frame_idx của các xe vừa thoát
    std::deque<double> speed_records;    // Lưu tốc độ các xe gần đây
    double q_flow = 0.0, v_speed = 0.0, k_fund = 0.0;
    int frame_counter = 0;

    // Helper functions
    bool is_inside_roi(cv::Point2f p);
};

#endif
