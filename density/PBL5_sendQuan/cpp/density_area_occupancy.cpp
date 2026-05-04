// =============================================================================
// density_area_occupancy.cpp
// Method 2: Area Occupancy via Bird's Eye View (BEV)
//
// Python equivalent: density_area_occupancy.py
// Algorithm:
//   1. Compute Homography matrix from camera ROI (SRC) to top-down BEV (DST).
//   2. For each detection bbox, transform its 4 corners via perspectiveTransform.
//   3. Fill the transformed polygon on a black BEV canvas (uint8).
//   4. Count white pixels → occupancy % = white_px / total_px * 100.
//   Filling (not addition) automatically handles overlapping vehicles.
// =============================================================================
#include "density_common.h"
#include <iostream>

// ==========================================
// CONFIGURATION
// ==========================================
static const std::string MODEL_PATH  = "best.onnx";
static const std::string VIDEO_PATH  = "test_video.mp4";
static const std::string OUTPUT_PATH = "output_density_occupancy.mp4";

static const std::vector<std::string> CLASS_NAMES = {"bus", "car", "motor", "truck"};

// Source ROI corners (camera perspective, float32 for getPerspectiveTransform)
static const std::vector<cv::Point2f> SRC_ROI = {
    {750,  400},
    {980,  400},
    {1250, 1050},
    {200,  1000}
};

// Destination BEV canvas size and corners
static constexpr int BEV_W = 500, BEV_H = 500;
static const std::vector<cv::Point2f> DST_BEV = {
    {0,           0},
    {BEV_W,       0},
    {BEV_W, BEV_H},
    {0,     BEV_H}
};

// ==========================================
// Helper: transform bbox corners to BEV space
// Replaces: cv2.perspectiveTransform + cv2.fillPoly loop
// ==========================================
static void draw_bbox_on_bev(cv::Mat& bev_canvas,
                             const cv::Rect2f& bbox,
                             const cv::Mat& H)
{
    // 4 corners of the bbox in camera space
    std::vector<cv::Point2f> corners = {
        {bbox.x,            bbox.y},
        {bbox.x+bbox.width, bbox.y},
        {bbox.x+bbox.width, bbox.y+bbox.height},
        {bbox.x,            bbox.y+bbox.height}
    };

    // perspectiveTransform needs a 1xN or Nx1 array of Point2f
    std::vector<cv::Point2f> transformed;
    cv::perspectiveTransform(corners, transformed, H);

    // Convert to integer points and fill on canvas (white = 255)
    std::vector<cv::Point> poly;
    for (auto& p : transformed) poly.push_back({(int)p.x, (int)p.y});
    cv::fillPoly(bev_canvas, std::vector<std::vector<cv::Point>>{poly}, 255);
}

int main() {
    std::cout << "[INFO] Method 2: BEV Area Occupancy\n";

    // Pre-compute Homography matrix  (SRC camera ROI -> DST top-down BEV)
    cv::Mat H = cv::getPerspectiveTransform(SRC_ROI, DST_BEV);
    const int TOTAL_BEV_PIXELS = BEV_W * BEV_H;

    YoloDetector detector(MODEL_PATH, CLASS_NAMES);
    SimpleTracker tracker;

    // PolygonZone for filtering (int32 version of SRC_ROI)
    std::vector<cv::Point> roi_int;
    for (auto& p : SRC_ROI) roi_int.push_back({(int)p.x, (int)p.y});
    PolygonZone zone(roi_int);

    cv::VideoCapture cap(VIDEO_PATH);
    if (!cap.isOpened()) { std::cerr << "[ERROR] Cannot open video\n"; return 1; }

    int    fw = (int)cap.get(cv::CAP_PROP_FRAME_WIDTH);
    int    fh = (int)cap.get(cv::CAP_PROP_FRAME_HEIGHT);
    double fps = cap.get(cv::CAP_PROP_FPS);

    cv::VideoWriter writer(OUTPUT_PATH,
                           cv::VideoWriter::fourcc('m','p','4','v'),
                           fps, {fw, fh});

    cv::namedWindow("Area Occupancy - BEV", cv::WINDOW_NORMAL);
    cv::resizeWindow("Area Occupancy - BEV", 1280, 720);

    cv::Mat frame;
    while (cap.read(frame)) {
        auto dets = detector.detect(frame);
        tracker.update(dets);

        auto mask = zone.trigger(dets);

        // ── BEV canvas (black = road, white = vehicle footprint) ──────────
        cv::Mat bev_canvas = cv::Mat::zeros(BEV_H, BEV_W, CV_8UC1);

        for (size_t i = 0; i < dets.size(); i++) {
            if (!mask[i]) continue;

            // ── CORE: Homography-based flattening ─────────────────────────
            // Camera bbox → BEV polygon → fill on canvas
            // Filling (not additive) eliminates double-counting of overlaps
            draw_bbox_on_bev(bev_canvas, dets[i].bbox, H);
        }

        // ── CALCULATION: Area Occupancy % ─────────────────────────────────
        int    occupied_px    = cv::countNonZero(bev_canvas);
        double occupancy_pct  = (double)occupied_px / TOTAL_BEV_PIXELS * 100.0;

        // ── Draw detections -  only vehicles in ROI ────────────────────────
        std::vector<Detection> dets_in;
        for (size_t i = 0; i < dets.size(); i++)
            if (mask[i]) dets_in.push_back(dets[i]);

        zone.draw(frame, {0, 0, 255}, 2);
        draw_detections(frame, dets_in, CLASS_NAMES, {0, 255, 0});

        // ── BEV minimap overlay (top-right corner) ─────────────────────────
        cv::Mat colored_bev;
        cv::cvtColor(bev_canvas, colored_bev, cv::COLOR_GRAY2BGR);
        // Color vehicle footprints red
        colored_bev.setTo(cv::Scalar(0, 0, 255),
                          bev_canvas == 255);

        cv::Mat minimap;
        cv::resize(colored_bev, minimap, {300, 300});
        int mx = fw - 340, my = 40;
        minimap.copyTo(frame(cv::Rect(mx, my, 300, 300)));
        cv::putText(frame, "BEV Radar", {mx+5, my+20},
                    cv::FONT_HERSHEY_SIMPLEX, 0.6, {255,255,255}, 1);

        // ── HUD: color-coded occupancy ─────────────────────────────────────
        cv::Scalar txt_color = {0, 255, 0};
        if (occupancy_pct > 20) txt_color = {0, 165, 255};
        if (occupancy_pct > 40) txt_color = {0, 0,   255};

        char buf[64];
        std::snprintf(buf, sizeof(buf), "Area Occupancy: %.1f%%", occupancy_pct);
        draw_info_box(frame, {{std::string(buf), txt_color}}, {20, 20}, 70);

        writer.write(frame);
        cv::imshow("Area Occupancy - BEV", frame);
        if ((cv::waitKey(1) & 0xFF) == 'q') break;
    }

    cap.release();
    writer.release();
    cv::destroyAllWindows();
    std::cout << "[SUCCESS] Method 2 complete.\n";
    return 0;
}
