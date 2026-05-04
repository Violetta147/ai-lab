// =============================================================================
// density_fundamental_equation.cpp
// Method 3: Fundamental Traffic Equation  k = q / v
//
// Python equivalent: density_fundamental_equation.py
// Algorithm (Sliding Window, 30s):
//   - Entry line: record frame timestamp when vehicle crosses
//   - Exit  line: (a) push to exit_timestamps for flow  (q)
//                 (b) if vehicle was seen at Entry → compute speed v = D/t
//   - Every frame:
//       q  = vehicles that crossed Exit in last 30s × 3600 → veh/h
//       v  = mean speed of vehicles recorded in last 30s   → km/h
//       k  = q / v   → veh/km
// =============================================================================
#include "density_common.h"
#include <iostream>
#include <deque>
#include <unordered_map>

// ==========================================
// CONFIGURATION
// ==========================================
static const std::string MODEL_PATH  = "best.onnx";
static const std::string VIDEO_PATH  = "test_video.mp4";
static const std::string OUTPUT_PATH = "output_density_fundamental.mp4";

static const std::vector<std::string> CLASS_NAMES = {"bus", "car", "motor", "truck"};

// Entry line  (far from camera, small y)
static const cv::Point2f ENTRY_START = {582, 507};
static const cv::Point2f ENTRY_END   = {1048, 507};

// Exit line   (near camera, large y)
static const cv::Point2f EXIT_START  = {308, 830};
static const cv::Point2f EXIT_END    = {1130, 830};

// Real-world distance between the two lines (km)
static const double ZONE_DISTANCE_KM = 0.03;

// Sliding window duration (seconds)
static const double SLIDING_WINDOW_SEC = 30.0;

// Speed plausibility filter (km/h)
static const double SPEED_MIN = 1.0, SPEED_MAX = 250.0;

// Fallback speed when q > 0 but v = 0 (km/h) — e.g. road speed limit
static const double FALLBACK_SPEED_KMH = 40.0;

int main() {
    std::cout << "[INFO] Method 3: Fundamental Traffic Equation (k = q/v)\n";

    YoloDetector detector(MODEL_PATH, CLASS_NAMES);
    SimpleTracker tracker;

    LineZone entry_line(ENTRY_START, ENTRY_END);
    LineZone exit_line (EXIT_START,  EXIT_END);

    // Per-tracker: frame index when the vehicle crossed Entry
    std::unordered_map<int, int> entry_timestamps;

    // Per-tracker: previous centroid (required by LineZone::trigger)
    std::unordered_map<int, cv::Point2f> prev_entry_cents, prev_exit_cents;

    // Sliding-window data
    // exit_frames:   frame index of each Exit crossing
    // speed_records: {speed_kmh, frame_index} for vehicles with full Entry→Exit data
    std::deque<int>                  exit_frames;
    std::deque<std::pair<double,int>> speed_records;

    cv::VideoCapture cap(VIDEO_PATH);
    if (!cap.isOpened()) { std::cerr << "[ERROR] Cannot open video\n"; return 1; }

    int    fw  = (int)cap.get(cv::CAP_PROP_FRAME_WIDTH);
    int    fh  = (int)cap.get(cv::CAP_PROP_FRAME_HEIGHT);
    double fps = cap.get(cv::CAP_PROP_FPS);

    cv::VideoWriter writer(OUTPUT_PATH,
                           cv::VideoWriter::fourcc('m','p','4','v'),
                           fps, {fw, fh});

    cv::namedWindow("Fundamental Traffic Equation", cv::WINDOW_NORMAL);
    cv::resizeWindow("Fundamental Traffic Equation", 1280, 720);

    cv::Mat frame;
    int frame_idx = 0;

    while (cap.read(frame)) {
        frame_idx++;
        double current_sec = frame_idx / fps;

        auto dets = detector.detect(frame);
        tracker.update(dets);

        if (!dets.empty()) {
            // ── Trigger ENTRY line ────────────────────────────────────────
            auto [ein, eout] = entry_line.trigger(dets, prev_entry_cents);
            std::vector<bool> entry_crossed(dets.size());
            for (size_t i = 0; i < dets.size(); i++)
                entry_crossed[i] = ein[i] | eout[i];

            // ── Trigger EXIT line ─────────────────────────────────────────
            auto [xin, xout] = exit_line.trigger(dets, prev_exit_cents);
            std::vector<bool> exit_crossed(dets.size());
            for (size_t i = 0; i < dets.size(); i++)
                exit_crossed[i] = xin[i] | xout[i];

            // ── Per-vehicle logic ─────────────────────────────────────────
            for (size_t i = 0; i < dets.size(); i++) {
                int tid = dets[i].tracker_id;

                // Vehicle crossed Entry → save entry timestamp
                if (entry_crossed[i])
                    entry_timestamps[tid] = frame_idx;

                // Vehicle crossed Exit
                if (exit_crossed[i]) {
                    // (a) always counts toward flow q
                    exit_frames.push_back(frame_idx);

                    // (b) if we saw it at Entry → compute speed v = D / t
                    auto it = entry_timestamps.find(tid);
                    if (it != entry_timestamps.end()) {
                        int    frames_elapsed     = frame_idx - it->second;
                        double time_elapsed_hours = (frames_elapsed / fps) / 3600.0;
                        if (time_elapsed_hours > 0) {
                            double speed_kmh = ZONE_DISTANCE_KM / time_elapsed_hours;
                            if (speed_kmh >= SPEED_MIN && speed_kmh <= SPEED_MAX)
                                speed_records.push_back({speed_kmh, frame_idx});
                        }
                        entry_timestamps.erase(it); // free memory
                    }
                }
            }

            // Draw bboxes
            draw_detections(frame, dets, CLASS_NAMES, {0, 255, 0});
        }

        // ── Slide the windows: drop records older than SLIDING_WINDOW_SEC ──
        while (!exit_frames.empty() &&
               (current_sec - exit_frames.front()/fps) > SLIDING_WINDOW_SEC)
            exit_frames.pop_front();

        while (!speed_records.empty() &&
               (current_sec - speed_records.front().second/fps) > SLIDING_WINDOW_SEC)
            speed_records.pop_front();

        // ── Calculate q, v, k ─────────────────────────────────────────────
        double obs_time = std::min(current_sec, SLIDING_WINDOW_SEC);

        // q = flow rate (veh/h)
        double q = (obs_time > 0)
                 ? ((double)exit_frames.size() / obs_time) * 3600.0
                 : 0.0;

        // v = spatial mean speed (km/h)
        double v = 0.0;
        if (!speed_records.empty()) {
            double sum = 0.0;
            for (auto& [spd, _] : speed_records) sum += spd;
            v = sum / speed_records.size();
        }

        // k = q / v  (fundamental equation)
        double k = 0.0;
        if (v > 0.0)               k = q / v;
        else if (q > 0.0 && v == 0) k = q / FALLBACK_SPEED_KMH; // safe fallback

        // ── Draw lines ────────────────────────────────────────────────────
        entry_line.draw(frame, {0, 0, 255}, 2);   // red  = entry
        cv::putText(frame, "ENTRY", ENTRY_START,
                    cv::FONT_HERSHEY_SIMPLEX, 0.7, {0,0,255}, 2);
        exit_line.draw(frame, {255, 0, 0}, 2);    // blue = exit
        cv::putText(frame, "EXIT", EXIT_START,
                    cv::FONT_HERSHEY_SIMPLEX, 0.7, {255,0,0}, 2);

        // ── HUD ───────────────────────────────────────────────────────────
        char buf_q[64], buf_v[64], buf_k[64];
        std::snprintf(buf_q, sizeof(buf_q), "Flow    (q): %.1f veh/h",  q);
        std::snprintf(buf_v, sizeof(buf_v), "Avg Speed(v): %.1f km/h",  v);
        std::snprintf(buf_k, sizeof(buf_k), "Density (k=q/v): %.1f veh/km", k);

        draw_info_box(frame, {
            {"FUNDAMENTAL TRAFFIC EQUATION",  {255, 255, 255}},
            {buf_q,                           {0,   255, 255}},
            {buf_v,                           {255, 165, 0  }},
            {buf_k,                           {0,   255, 0  }}
        });

        writer.write(frame);
        cv::imshow("Fundamental Traffic Equation", frame);
        if ((cv::waitKey(1) & 0xFF) == 'q') break;
    }

    cap.release();
    writer.release();
    cv::destroyAllWindows();
    std::cout << "[SUCCESS] Method 3 complete.\n";
    return 0;
}
