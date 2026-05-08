// =============================================================================
// density_pce_aware.cpp
// Method 4: PCE-Weighted Density  k_pce = sum(PCE_i) / L
//
// Python equivalent: density_pce_aware.py
// Algorithm:
//   - For each vehicle inside ROI, look up its class name in PCE_WEIGHTS.
//   - Sum all PCE values → total_pce.
//   - k_pce = total_pce / road_length_km  (PCE/km)
//   - Color-code ROI polygon and dashboard by congestion level.
//
// PCE (Passenger Car Equivalent) converts each vehicle type to an equivalent
// number of passenger cars, enabling fair multi-class density comparison.
// =============================================================================
#include "density_common.h"
#include <iostream>
#include <unordered_map>

// ==========================================
// CONFIGURATION
// ==========================================
static const std::string MODEL_PATH  = "best.onnx";
static const std::string VIDEO_PATH  = "test_video.mp4";
static const std::string OUTPUT_PATH = "output_density_pce.mp4";

// Class names must match data.yaml order
static const std::vector<std::string> CLASS_NAMES = {"bus", "car", "motor", "truck"};

// ROI polygon
static const std::vector<cv::Point> ROI_VERTICES = {
    {750,  400},
    {980,  400},
    {1250, 1050},
    {200,  1000}
};

// Road length inside ROI (km) — calibrate once per camera installation
static const double ROAD_LENGTH_KM = 0.1;

// ==========================================
// PCE WEIGHT TABLE
// Keys must match CLASS_NAMES exactly.
// ==========================================
static const std::unordered_map<std::string, double> PCE_WEIGHTS = {
    {"motor", 0.5},
    {"car",   1.0},
    {"bus",   2.5},
    {"truck", 2.5}
};

// ==========================================
// CONGESTION THRESHOLDS (PCE/km — international standard)
// ==========================================
static const double THRESHOLD_HEAVY = 800.0;   // > 800  PCE/km → ùn ứ       (heavy)
static const double THRESHOLD_JAM   = 1500.0;  // > 1500 PCE/km → kẹt xe     (jam)

// ==========================================
// FUNCTION 4: PCE density
// Replaces: calculate_pce_density() in Python
// Returns: {total_pce, labels}
// ==========================================
static std::pair<double, std::vector<std::string>>
calculate_pce_density(const std::vector<Detection>& dets_in_roi)
{
    double total_pce = 0.0;
    std::vector<std::string> labels;

    for (const auto& d : dets_in_roi) {
        const std::string& name = CLASS_NAMES[d.class_id];

        // Look up PCE weight; default = 1.0 for unknown classes
        double pce_val = 1.0;
        auto it = PCE_WEIGHTS.find(name);
        if (it != PCE_WEIGHTS.end()) pce_val = it->second;

        total_pce += pce_val;

        char buf[64];
        std::snprintf(buf, sizeof(buf), "#%d %s (PCE:%.1f) %.2f",
                      d.tracker_id, name.c_str(), pce_val, d.confidence);
        labels.push_back(buf);
    }

    return {total_pce, labels};
}

// ==========================================
// Helper: congestion status from k_pce
// ==========================================
struct Status {
    std::string text;
    cv::Scalar  color_bgr;
    cv::Scalar  roi_color;
};

static Status get_status(double k_pce) {
    if (k_pce >= THRESHOLD_JAM)
        return {"TRAFFIC JAM (Ket xe)",       {0,0,255},   {0,0,255}};
    if (k_pce >= THRESHOLD_HEAVY)
        return {"HEAVY (Un u)",               {0,165,255}, {0,165,255}};
    return    {"NORMAL (Thong thoang)",       {0,255,0},   {0,255,0}};
}

int main() {
    std::cout << "[INFO] Method 4: PCE-Aware Density (k_pce = sum(PCE) / L)\n";

    YoloDetector detector(MODEL_PATH, CLASS_NAMES);
    SimpleTracker tracker;
    PolygonZone   zone(ROI_VERTICES);

    cv::VideoCapture cap(VIDEO_PATH);
    if (!cap.isOpened()) { std::cerr << "[ERROR] Cannot open video\n"; return 1; }

    int    fw  = (int)cap.get(cv::CAP_PROP_FRAME_WIDTH);
    int    fh  = (int)cap.get(cv::CAP_PROP_FRAME_HEIGHT);
    double fps = cap.get(cv::CAP_PROP_FPS);

    cv::VideoWriter writer(OUTPUT_PATH,
                           cv::VideoWriter::fourcc('m','p','4','v'),
                           fps, {fw, fh});

    cv::namedWindow("PCE Density Estimation", cv::WINDOW_NORMAL);
    cv::resizeWindow("PCE Density Estimation", 1280, 720);

    cv::Mat frame;
    while (cap.read(frame)) {
        auto dets = detector.detect(frame);
        tracker.update(dets);

        // ── Filter: only vehicles inside ROI ─────────────────────────────
        auto mask = zone.trigger(dets);
        std::vector<Detection> dets_in_roi;
        for (size_t i = 0; i < dets.size(); i++)
            if (mask[i]) dets_in_roi.push_back(dets[i]);

        // ── CORE ALGORITHM: PCE density ───────────────────────────────────
        auto [total_pce, labels] = calculate_pce_density(dets_in_roi);

        // k_pce = total PCE points / road length (PCE/km)
        double k_pce = (ROAD_LENGTH_KM > 0) ? total_pce / ROAD_LENGTH_KM : 0.0;

        // ── Congestion status ─────────────────────────────────────────────
        Status status = get_status(k_pce);

        // ── Draw: ROI polygon (color changes with congestion level) ───────
        std::vector<std::vector<cv::Point>> poly_pts = {ROI_VERTICES};
        cv::polylines(frame, poly_pts, true, status.roi_color, 3);

        // ── Draw: detections with PCE labels ──────────────────────────────
        for (size_t i = 0; i < dets_in_roi.size(); i++) {
            cv::Rect r(dets_in_roi[i].bbox);
            cv::rectangle(frame, r, {0, 255, 0}, 2);
            cv::putText(frame, labels[i], {r.x, r.y - 5},
                        cv::FONT_HERSHEY_SIMPLEX, 0.45, {0, 255, 0}, 1, cv::LINE_AA);
        }

        // ── HUD ───────────────────────────────────────────────────────────
        char buf_count[64], buf_pce[64], buf_k[64];
        std::snprintf(buf_count, sizeof(buf_count),
                      "Absolute Count: %d vehicles", (int)dets_in_roi.size());
        std::snprintf(buf_pce,   sizeof(buf_pce),
                      "Total PCE Points: %.1f PCE",  total_pce);
        std::snprintf(buf_k,     sizeof(buf_k),
                      "Density (k): %.1f PCE/km",    k_pce);

        draw_info_box(frame, {
            {buf_count,                       {255, 255, 255}},
            {buf_pce,                         {0,   255, 255}},
            {buf_k,                           {255,   0, 255}},
            {"Status: " + status.text,        status.color_bgr}
        });

        writer.write(frame);
        cv::imshow("PCE Density Estimation", frame);
        if ((cv::waitKey(1) & 0xFF) == 'q') break;
    }

    cap.release();
    writer.release();
    cv::destroyAllWindows();
    std::cout << "[SUCCESS] Method 4 complete.\n";
    return 0;
}
