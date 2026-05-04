#include "traffic_analyzer.hpp"
#include <numeric>

TrafficAnalyzer::TrafficAnalyzer(int frame_w, int frame_h) : w(frame_w), h(frame_h) {
    // 1. Khởi tạo ROI (Mặc định nửa dưới màn hình)
    roi_polygon = {{w/4, h/2}, {3*w/4, h/2}, {w, h}, {0, h}};
    
    // 2. Khởi tạo PCE weights (bus, car, motor, truck)
    pce_weights = {2.5, 1.0, 0.5, 2.5};

    // 3. Khởi tạo Homography cho BEV (Bird's Eye View)
    std::vector<cv::Point2f> src = {{ (float)w/4, (float)h/2 }, { (float)3*w/4, (float)h/2 }, { (float)w, (float)h }, { 0, (float)h }};
    std::vector<cv::Point2f> dst = {{0, 0}, {(float)bev_size, 0}, {(float)bev_size, (float)bev_size}, {0, (float)bev_size}};
    homography = cv::getPerspectiveTransform(src, dst);

    // 4. Vạch đếm cho Fundamental Equation
    entry_s = { (float)w/4, (float)h/2 + 20 }; entry_e = { (float)3*w/4, (float)h/2 + 20 };
    exit_s = { 20, (float)h - 20 };            exit_e = { (float)w - 20, (float)h - 20 };
}

void TrafficAnalyzer::update(const std::vector<STrack>& tracks, double fps) {
    frame_counter++;
    count_n = 0;
    double pce_sum = 0.0;
    bev_canvas = cv::Mat::zeros(bev_size, bev_size, CV_8UC1);

    for (const auto& t : tracks) {
        if (t.tlbr.size() < 4) continue;
        
        // Lấy tọa độ chân thực của xe (bottom center)
        cv::Point2f bc = { (t.tlbr[0] + t.tlbr[2])/2.0f, t.tlbr[3] };
        
        // --- METHOD 1 & 4: ROI filtering & PCE ---
        if (is_inside_roi(bc)) {
            count_n++;
            if (t.label >= 0 && t.label < (int)pce_weights.size()) {
                pce_sum += pce_weights[t.label];
            }

            // --- METHOD 2: BEV Occupancy ---
            std::vector<cv::Point2f> corners = {
                {t.tlbr[0], t.tlbr[1]}, {t.tlbr[2], t.tlbr[1]}, 
                {t.tlbr[2], t.tlbr[3]}, {t.tlbr[0], t.tlbr[3]}
            };
            std::vector<cv::Point2f> trans;
            cv::perspectiveTransform(corners, trans, homography);
            std::vector<cv::Point> poly;
            for(auto& p : trans) poly.push_back(p);
            if (!poly.empty()) {
                cv::fillPoly(bev_canvas, std::vector<std::vector<cv::Point>>{poly}, 255);
            }
        }

        // --- METHOD 3: Fundamental (k=q/v) ---
        // Đơn giản hóa: xe chạm vạch entry lưu time, chạm vạch exit tính speed
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

    // Tính toán con số cuối cùng
    density_pce_k = pce_sum / road_length_km;
    occupancy_pct = (double)cv::countNonZero(bev_canvas) / (bev_size * bev_size) * 100.0;
    
    // Cập nhật Sliding Window (xóa dữ liệu cũ hơn 30 giây)
    while (!exit_frames.empty() && (frame_counter - exit_frames.front()) > 30 * fps) {
        exit_frames.pop_front();
    }
    while (speed_records.size() > 50) {
        speed_records.pop_front();
    }

    q_flow = (exit_frames.size() / 30.0) * 3600.0;
    v_speed = speed_records.empty() ? 0 : std::accumulate(speed_records.begin(), speed_records.end(), 0.0) / speed_records.size();
    k_fund = v_speed > 5.0 ? q_flow / v_speed : 0;
}

bool TrafficAnalyzer::is_inside_roi(cv::Point2f p) {
    if (roi_polygon.empty()) return false;
    return cv::pointPolygonTest(roi_polygon, p, false) >= 0;
}

void TrafficAnalyzer::draw(cv::Mat& frame) {
    // 1. Vẽ ROI và Vạch
    std::vector<std::vector<cv::Point>> pts = {roi_polygon};
    cv::polylines(frame, pts, true, {0, 255, 255}, 2);
    cv::line(frame, entry_s, entry_e, {0, 0, 255}, 2);
    cv::line(frame, exit_s, exit_e, {255, 0, 0}, 2);

    // 2. Dashboard nền đen
    cv::rectangle(frame, {10, 350}, {350, 470}, {0, 0, 0}, -1);
    cv::putText(frame, cv::format("Vehicles (N): %d", count_n), {20, 370}, 0, 0.5, {255, 255, 255}, 1);
    cv::putText(frame, cv::format("PCE Density: %.1f PCE/km", density_pce_k), {20, 390}, 0, 0.5, {0, 255, 0}, 1);
    cv::putText(frame, cv::format("BEV Occupancy: %.1f%%", occupancy_pct), {20, 410}, 0, 0.5, {0, 255, 255}, 1);
    cv::putText(frame, cv::format("Flow (q): %.0f v/h", q_flow), {20, 430}, 0, 0.5, {255, 150, 0}, 1);
    cv::putText(frame, cv::format("Speed (v): %.1f km/h", v_speed), {20, 450}, 0, 0.5, {255, 100, 255}, 1);
}
