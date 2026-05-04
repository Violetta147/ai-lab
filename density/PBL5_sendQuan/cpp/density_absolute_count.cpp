// =============================================================================
// density_absolute_count.cpp
// Method 1: Absolute Count Density  (k = N / L)
//
// Python equivalent: density_absolute_count.py
// Algorithm:
//   For each detection, compute centroid → check if inside ROI polygon
//   via PointPolygonTest (Ray-Casting). Count = N vehicles inside ROI.
//   Density k = N / road_length_km.
// =============================================================================
#include "density_common.h"
#include <iostream>

// ==========================================
// CONFIGURATION
// ==========================================
static const std::string MODEL_PATH  = "best.onnx";
static const std::string VIDEO_PATH  = "test_video.mp4";
static const std::string OUTPUT_PATH = "output_density_absolute.mp4";

// Class names must match data.yaml order
static const std::vector<std::string> CLASS_NAMES = {"bus", "car", "motor", "truck"};

// ROI polygon (camera-space coordinates)
static const std::vector<cv::Point> ROI_VERTICES = {
    {750,  400},   // Top-left
    {980,  400},   // Top-right
    {1250, 1050},  // Bottom-right
    {200,  1000}   // Bottom-left
};

// Road length inside ROI (km). Calibrate once per camera installation.
static const double ROAD_LENGTH_KM = 0.1;

// ==========================================
// FUNCTION 1: Absolute density calculation
// Replaces: calculate_absolute_density() in Python
// ==========================================
static int calculate_absolute_density(const std::vector<Detection>& dets,
                                      const PolygonZone& zone)
{
    int count = 0;
    for (const auto& d : dets) {
        // Centroid = center of bounding box (same as Python version)
        cv::Point2f centroid = d.center();

        // Ray-Casting via pointPolygonTest:
        //   >= 0  ->  inside or on edge  ->  count it
        //    < 0  ->  outside
        if (zone.contains(centroid))
            count++;
    }
    return count;
}

int main() {
    std::cout << "[INFO] Method 1: Absolute Count Density (k = N / L)\n";

    YoloDetector detector(MODEL_PATH, CLASS_NAMES);
    SimpleTracker tracker;
    PolygonZone   zone(ROI_VERTICES);

    cv::VideoCapture cap(VIDEO_PATH);
    if (!cap.isOpened()) { std::cerr << "[ERROR] Cannot open video\n"; return 1; }

    int    fw = (int)cap.get(cv::CAP_PROP_FRAME_WIDTH);
    int    fh = (int)cap.get(cv::CAP_PROP_FRAME_HEIGHT);
    double fps = cap.get(cv::CAP_PROP_FPS);

    cv::VideoWriter writer(OUTPUT_PATH,
                           cv::VideoWriter::fourcc('m','p','4','v'),
                           fps, {fw, fh});

    cv::namedWindow("Density: Absolute Count", cv::WINDOW_NORMAL);
    cv::resizeWindow("Density: Absolute Count", 1280, 720);

    cv::Mat frame;
    while (cap.read(frame)) {
        // ── Inference + Tracking ──────────────────────────────────────────
        auto dets = detector.detect(frame);
        tracker.update(dets);

        // ── Filter detections inside ROI ──────────────────────────────────
        std::vector<bool>      mask = zone.trigger(dets);
        std::vector<Detection> dets_in_roi;
        for (size_t i = 0; i < dets.size(); i++)
            if (mask[i]) dets_in_roi.push_back(dets[i]);

        // ── CORE ALGORITHM: Count vehicles inside ROI ─────────────────────
        int total_count = calculate_absolute_density(dets, zone);

        // ── MATH: Density k = N / L ───────────────────────────────────────
        double density_k = (ROAD_LENGTH_KM > 0) ? total_count / ROAD_LENGTH_KM : 0.0;

        // ── Draw ──────────────────────────────────────────────────────────
        zone.draw(frame, {0, 0, 255}, 2);
        draw_detections(frame, dets_in_roi, CLASS_NAMES, {0, 255, 0});

        // Draw centroid dots for each vehicle in ROI (demo for presentation)
        for (const auto& d : dets_in_roi) {
            cv::Point2f c = d.center();
            cv::circle(frame, c, 4, {0, 255, 255}, -1);
        }

        // ── HUD ───────────────────────────────────────────────────────────
        draw_info_box(frame, {
            {"Vehicles (N): " + std::to_string(total_count),              {255,255,255}},
            {"Density  (k): " + std::to_string((int)density_k) + " veh/km", {0,255,0}}
        });

        writer.write(frame);
        cv::imshow("Density: Absolute Count", frame);
        if ((cv::waitKey(1) & 0xFF) == 'q') break;
    }

    cap.release();
    writer.release();
    cv::destroyAllWindows();
    std::cout << "[SUCCESS] Method 1 complete.\n";
    return 0;
}
