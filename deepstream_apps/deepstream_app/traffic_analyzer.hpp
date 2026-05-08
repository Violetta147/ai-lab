#ifndef TRAFFIC_ANALYZER_HPP
#define TRAFFIC_ANALYZER_HPP

#include <opencv2/opencv.hpp>
#include <vector>
#include <deque>
#include <map>

// Cấu trúc dữ liệu đơn giản thay thế cho STrack của ByteTrack
struct TrackedObj {
    int track_id;
    int label;
    float confidence;
    float left, top, right, bottom;
};

class TrafficAnalyzer {
public:
    TrafficAnalyzer(int frame_w = 640, int frame_h = 480);
    
    // Cập nhật: dùng vector TrackedObj thay vì STrack
    void update(const std::vector<TrackedObj>& tracks, double fps);
    
    void draw(cv::Mat& frame);

private:
    int w, h;
    std::vector<cv::Point> roi_polygon;
    double road_length_km = 0.1;
    int count_n = 0;
    std::vector<double> pce_weights; 
    double density_pce_k = 0.0;
    cv::Mat homography;
    int bev_size = 300;
    double occupancy_pct = 0.0;
    cv::Mat bev_canvas;
    cv::Point2f entry_s, entry_e, exit_s, exit_e;
    double zone_dist_km = 0.03;
    std::map<int, int> entry_timestamps; 
    std::deque<int> exit_frames;         
    std::deque<double> speed_records;    
    double q_flow = 0.0, v_speed = 0.0, k_fund = 0.0;
    int frame_counter = 0;

    bool is_inside_roi(cv::Point2f p);
};

#endif
