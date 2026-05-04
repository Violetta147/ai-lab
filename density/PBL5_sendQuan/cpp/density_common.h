#pragma once
// =============================================================================
// density_common.h
// Shared infrastructure replacing: ultralytics YOLO, supervision (sv)
// Dependencies: OpenCV 4.x (with dnn module)
// =============================================================================
#include <opencv2/opencv.hpp>
#include <opencv2/dnn.hpp>
#include <vector>
#include <string>
#include <map>
#include <unordered_map>
#include <algorithm>
#include <cmath>
#include <numeric>

// -----------------------------------------------------------------------------
// Detection struct (replaces sv.Detections)
// -----------------------------------------------------------------------------
struct Detection {
    cv::Rect2f bbox;       // x, y, w, h in frame pixels
    float      confidence;
    int        class_id;
    int        tracker_id = -1;

    cv::Point2f center()      const { return {bbox.x + bbox.width/2.f, bbox.y + bbox.height/2.f}; }
    cv::Point2f bottom_center() const { return {bbox.x + bbox.width/2.f, bbox.y + bbox.height}; }
};

// -----------------------------------------------------------------------------
// YOLO inference via OpenCV DNN (loads .onnx exported from ultralytics)
// YOLOv8 ONNX output shape: [1, 4+num_classes, 8400]
// -----------------------------------------------------------------------------
class YoloDetector {
public:
    std::vector<std::string> class_names;

    YoloDetector(const std::string& model_path,
                 const std::vector<std::string>& names,
                 float conf = 0.3f, float nms = 0.45f)
        : class_names(names), conf_thresh_(conf), nms_thresh_(nms)
    {
        net_ = cv::dnn::readNetFromONNX(model_path);
        // Use CUDA if available, fall back to CPU
        net_.setPreferableBackend(cv::dnn::DNN_BACKEND_CUDA);
        net_.setPreferableTarget(cv::dnn::DNN_TARGET_CUDA_FP16);
    }

    std::vector<Detection> detect(const cv::Mat& frame) {
        cv::Mat blob;
        cv::dnn::blobFromImage(frame, blob, 1.0/255.0,
                               cv::Size(INPUT_W, INPUT_H),
                               cv::Scalar(), true, false);
        net_.setInput(blob);

        std::vector<cv::Mat> outs;
        net_.forward(outs, net_.getUnconnectedOutLayersNames());
        return postprocess(frame.size(), outs[0]);
    }

private:
    static constexpr int INPUT_W = 640, INPUT_H = 640;
    cv::dnn::Net net_;
    float conf_thresh_, nms_thresh_;

    std::vector<Detection> postprocess(const cv::Size& fs, const cv::Mat& out) {
        // out: [1, 4+C, 8400] -> reshape to [4+C, 8400] -> transpose to [8400, 4+C]
        int rows = out.size[1]; // 4+C
        int cols = out.size[2]; // 8400
        cv::Mat data(rows, cols, CV_32F, const_cast<float*>(out.ptr<float>()));
        cv::Mat t = data.t(); // [8400, 4+C]

        float sx = (float)fs.width  / INPUT_W;
        float sy = (float)fs.height / INPUT_H;
        int   nc = rows - 4;

        std::vector<cv::Rect2f> boxes;
        std::vector<float>      scores;
        std::vector<int>        class_ids;

        for (int i = 0; i < t.rows; i++) {
            const float* r = t.ptr<float>(i);
            // Find best class probability
            int   best_c = 0;
            float best_s = 0.f;
            for (int c = 0; c < nc; c++) {
                if (r[4+c] > best_s) { best_s = r[4+c]; best_c = c; }
            }
            if (best_s < conf_thresh_) continue;

            float cx = r[0]*sx, cy = r[1]*sy;
            float  w = r[2]*sx,  h = r[3]*sy;
            boxes.push_back({cx - w/2, cy - h/2, w, h});
            scores.push_back(best_s);
            class_ids.push_back(best_c);
        }

        std::vector<int> idx;
        cv::dnn::NMSBoxes(boxes, scores, conf_thresh_, nms_thresh_, idx);

        std::vector<Detection> dets;
        for (int i : idx) {
            dets.push_back({boxes[i], scores[i], class_ids[i]});
        }
        return dets;
    }
};

// -----------------------------------------------------------------------------
// Simple IoU Tracker (replaces ByteTrack for basic functionality)
// -----------------------------------------------------------------------------
class SimpleTracker {
public:
    explicit SimpleTracker(float iou_thresh = 0.3f)
        : iou_thresh_(iou_thresh), next_id_(1) {}

    void update(std::vector<Detection>& dets) {
        if (tracks_.empty()) {
            for (auto& d : dets) { d.tracker_id = next_id_++; tracks_[d.tracker_id] = d.bbox; }
            return;
        }

        std::vector<int>   assigned(dets.size(), -1);
        std::map<int,bool> used;

        for (size_t i = 0; i < dets.size(); i++) {
            float best = iou_thresh_; int best_id = -1;
            for (auto& [tid, tb] : tracks_) {
                float iou = iou(dets[i].bbox, tb);
                if (iou > best && !used[tid]) { best = iou; best_id = tid; }
            }
            if (best_id >= 0) { assigned[i] = best_id; used[best_id] = true; }
        }

        std::map<int, cv::Rect2f> new_tracks;
        for (size_t i = 0; i < dets.size(); i++) {
            int tid = (assigned[i] >= 0) ? assigned[i] : next_id_++;
            dets[i].tracker_id = tid;
            new_tracks[tid] = dets[i].bbox;
        }
        tracks_ = new_tracks;
    }

private:
    float iou_thresh_; int next_id_;
    std::map<int, cv::Rect2f> tracks_;

    static float iou(const cv::Rect2f& a, const cv::Rect2f& b) {
        cv::Rect2f inter = a & b;
        if (inter.empty()) return 0.f;
        float ia = inter.area();
        float ua = a.area() + b.area() - ia;
        return ua > 0 ? ia/ua : 0.f;
    }
};

// -----------------------------------------------------------------------------
// Polygon Zone  (replaces sv.PolygonZone)
// -----------------------------------------------------------------------------
struct PolygonZone {
    std::vector<cv::Point> polygon;

    explicit PolygonZone(const std::vector<cv::Point>& pts) : polygon(pts) {}

    bool contains(const cv::Point2f& p) const {
        return cv::pointPolygonTest(polygon, p, false) >= 0;
    }

    // Returns mask: which detections have bottom-center inside polygon
    std::vector<bool> trigger(const std::vector<Detection>& dets) const {
        std::vector<bool> mask(dets.size());
        for (size_t i = 0; i < dets.size(); i++)
            mask[i] = contains(dets[i].bottom_center());
        return mask;
    }

    void draw(cv::Mat& frame, const cv::Scalar& color = {0,0,255}, int thick = 2) const {
        std::vector<std::vector<cv::Point>> pts = {polygon};
        cv::polylines(frame, pts, true, color, thick);
    }
};

// -----------------------------------------------------------------------------
// Line Zone  (replaces sv.LineZone)
// Uses per-tracker previous centroid to detect crossing + direction
// -----------------------------------------------------------------------------
struct LineZone {
    cv::Point2f start, end;
    int in_count = 0, out_count = 0;

    LineZone(cv::Point2f s, cv::Point2f e) : start(s), end(e) {}

    // Returns {crossed_in[], crossed_out[]}
    std::pair<std::vector<bool>, std::vector<bool>>
    trigger(const std::vector<Detection>& dets,
            std::unordered_map<int, cv::Point2f>& prev_centroids)
    {
        std::vector<bool> cross_in(dets.size()), cross_out(dets.size());
        for (size_t i = 0; i < dets.size(); i++) {
            int tid = dets[i].tracker_id;
            cv::Point2f cur = dets[i].bottom_center();
            auto it = prev_centroids.find(tid);
            if (it != prev_centroids.end()) {
                if (intersects(it->second, cur)) {
                    // direction via cross product
                    float ldx = end.x - start.x, ldy = end.y - start.y;
                    float mdx = cur.x - it->second.x, mdy = cur.y - it->second.y;
                    if (ldx*mdy - ldy*mdx > 0) { cross_in[i]  = true; in_count++;  }
                    else                         { cross_out[i] = true; out_count++; }
                }
            }
            prev_centroids[tid] = cur;
        }
        return {cross_in, cross_out};
    }

    void draw(cv::Mat& frame, const cv::Scalar& color = {0,255,0}, int thick = 2) const {
        cv::line(frame, start, end, color, thick);
    }

private:
    bool intersects(cv::Point2f A, cv::Point2f B) const {
        // Segment AB vs segment start-end
        auto cross3 = [](cv::Point2f O, cv::Point2f P, cv::Point2f Q) {
            return (P.x-O.x)*(Q.y-O.y) - (P.y-O.y)*(Q.x-O.x);
        };
        float d1 = cross3(start, end, A), d2 = cross3(start, end, B);
        float d3 = cross3(A, B, start),   d4 = cross3(A, B, end);
        if (((d1>0&&d2<0)||(d1<0&&d2>0)) && ((d3>0&&d4<0)||(d3<0&&d4>0))) return true;
        return false;
    }
};

// -----------------------------------------------------------------------------
// Drawing helpers
// -----------------------------------------------------------------------------
inline void draw_detections(cv::Mat& frame,
                            const std::vector<Detection>& dets,
                            const std::vector<std::string>& names,
                            const cv::Scalar& color = {0,255,0})
{
    for (const auto& d : dets) {
        cv::Rect r(d.bbox);
        cv::rectangle(frame, r, color, 2);
        std::string label = "#" + std::to_string(d.tracker_id) + " " + names[d.class_id];
        cv::putText(frame, label, {r.x, r.y-5},
                    cv::FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv::LINE_AA);
    }
}

inline void draw_info_box(cv::Mat& frame,
                          const std::vector<std::pair<std::string,cv::Scalar>>& lines,
                          cv::Point tl = {10,10}, int line_h = 45)
{
    int w = 600, h = (int)lines.size() * line_h + 20;
    cv::rectangle(frame, tl, {tl.x+w, tl.y+h}, {0,0,0}, -1);
    for (size_t i = 0; i < lines.size(); i++) {
        cv::Point pt = {tl.x+15, tl.y + (int)(i+1)*line_h};
        cv::putText(frame, lines[i].first, pt,
                    cv::FONT_HERSHEY_SIMPLEX, 0.85, lines[i].second, 2, cv::LINE_AA);
    }
}
