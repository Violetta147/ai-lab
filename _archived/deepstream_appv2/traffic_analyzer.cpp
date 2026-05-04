#include "traffic_analyzer.hpp"
#include <numeric>

TrafficAnalyzer::TrafficAnalyzer(int frame_w, int frame_h) : w(frame_w), h(frame_h) {
    roi_polygon = {{w/4, h/2}, {3*w/4, h/2}, {w, h}, {0, h}};
    pce_weights = {2.5, 1.0, 0.5, 2.5};
    std::vector<cv::Point2f> src = {{ (float)w/4, (float)h/2 }, { (float)3*w/4, (float)h/2 }, { (float)w, (float)h }, { 0, (float)h }};
    std::vector<cv::Point2f> dst = {{0, 0}, {(float)bev_size, 0}, {(float)bev_size, (float)bev_size}, {0, (float)bev_size}};
    homography = cv::getPerspectiveTransform(src, dst);
    entry_s = { (float)w/4, (float)h/2 + 20 }; entry_e = { (float)3*w/4, (float)h/2 + 20 };
    exit_s = { 20, (float)h - 20 };            exit_e = { (float)w - 20, (float)h - 20 };
}

void TrafficAnalyzer::update(const std::vector<TrackedObj>& tracks, double fps) {
    frame_counter++;
    count_n = 0;
    double pce_sum = 0.0;
    bev_canvas = cv::Mat::zeros(bev_size, bev_size, CV_8UC1);

    for (const auto& t : tracks) {
        cv::Point2f bc = { (t.left + t.right)/2.0f, t.bottom };
        if (is_inside_roi(bc)) {
            count_n++;
            if (t.label >= 0 && t.label < (int)pce_weights.size()) {
                pce_sum += pce_weights[t.label];
            }
            std::vector<cv::Point2f> corners = {{t.left, t.top}, {t.right, t.top}, {t.right, t.bottom}, {t.left, t.bottom}};
            std::vector<cv::Point2f> trans;
            cv::perspectiveTransform(corners, trans, homography);
            std::vector<cv::Point> poly;
            for(auto& p : trans) poly.push_back(p);
            if (!poly.empty()) {
                cv::fillPoly(bev_canvas, std::vector<std::vector<cv::Point>>{poly}, 255);
            }
        }
        if (bc.y > entry_s.y && bc.y < entry_s.y + 10) {
            if (entry_timestamps.find(t.track_id) == entry_timestamps.end()) {
                entry_timestamps[t.track_id] = frame_counter;
            }
        }
        if (bc.y > exit_s.y && entry_timestamps.count(t.track_id)) {
            exit_frames.push_back(frame_counter);
            double travel_time = (frame_counter - entry_timestamps[t.track_id]) / fps;
            if (travel_time > 0) {
                double speed_kmh = (zone_dist_km / (travel_time / 3600.0));
                if (speed_kmh > 1.0 && speed_kmh < 200.0) speed_records.push_back(speed_kmh);
            }
            entry_timestamps.erase(t.track_id);
        }
    }
    density_pce_k = pce_sum / road_length_km;
    occupancy_pct = (double)cv::countNonZero(bev_canvas) / (bev_size * bev_size) * 100.0;
    while (!exit_frames.empty() && (frame_counter - exit_frames.front()) > 30 * fps) exit_frames.pop_front();
    while (speed_records.size() > 50) speed_records.pop_front();
    q_flow = (exit_frames.size() / 30.0) * 3600.0;
    v_speed = speed_records.empty() ? 0 : std::accumulate(speed_records.begin(), speed_records.end(), 0.0) / speed_records.size();
    k_fund = v_speed > 5.0 ? q_flow / v_speed : 0;
}

bool TrafficAnalyzer::is_inside_roi(cv::Point2f p) {
    if (roi_polygon.empty()) return false;
    return cv::pointPolygonTest(roi_polygon, p, false) >= 0;
}

void TrafficAnalyzer::draw(cv::Mat& frame) {
    std::vector<std::vector<cv::Point>> pts = {roi_polygon};
    cv::polylines(frame, pts, true, {0, 255, 255}, 2);
    cv::line(frame, entry_s, entry_e, {0, 0, 255}, 2);
    cv::line(frame, exit_s, exit_e, {255, 0, 0}, 2);
    cv::rectangle(frame, {10, 350}, {350, 470}, {0, 0, 0}, -1);
    cv::putText(frame, cv::format("N: %d | PCE: %.1f | BEV: %.1f%%", count_n, density_pce_k, occupancy_pct), {20, 375}, 0, 0.5, {255, 255, 255}, 1);
    cv::putText(frame, cv::format("q: %.0f v/h | v: %.1f km/h", q_flow, v_speed), {20, 410}, 0, 0.5, {0, 255, 255}, 1);
}
