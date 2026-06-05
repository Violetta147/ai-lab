#include <iostream>
#include <vector>
#include <string>
#include <opencv2/opencv.hpp>
#include <chrono>
#include <nlohmann/json.hpp>
#include <thread>
#include <mutex>
#include <atomic>

#include "../include/config.hpp"
#include "../include/types.hpp"
#include "../include/safe_queue.hpp"
#include "../include/utils/dotenv.hpp"
#include "filters/active_learning.hpp"
#include "filters/rule_ood.hpp"
#include "filters/publish_gate.hpp"
#include "clients/mqtt_client.hpp"
#include "clients/minio_client.hpp"
#include "core/disk_writer_thread.hpp"
#include "core/sync_thread.hpp"
#include "infer/yolo.hpp"
#include "infer/bt_byte_tracker.hpp"

// Background reader to prevent RTSP buffer overflow and H264 corruption
class CameraStream {
public:
    CameraStream(const std::string& path, bool use_video_source) : path_(path), use_video_source_(use_video_source), running_(false) {}

    bool start() {
        if (use_video_source_) {
            // UDP transport is usually better for RTSP to prevent TCP backpressure
            // but we'll stick to default for now, just reduce buffersize
            cap_.open(path_, cv::CAP_FFMPEG);
        } else {
            cap_.open(0);
        }

        if (!cap_.isOpened()) return false;
        
        cap_.set(cv::CAP_PROP_BUFFERSIZE, 1);

        running_ = true;
        thread_ = std::thread([this]() {
            cv::Mat temp;
            while (running_) {
                if (!cap_.read(temp)) {
                    std::this_thread::sleep_for(std::chrono::milliseconds(10));
                    continue;
                }
                std::lock_guard<std::mutex> lock(mtx_);
                latest_frame_ = temp.clone();
                has_new_frame_ = true;
            }
        });
        return true;
    }

    bool get_latest_frame(cv::Mat& out_frame) {
        std::lock_guard<std::mutex> lock(mtx_);
        if (!has_new_frame_) return false;
        out_frame = latest_frame_.clone();
        has_new_frame_ = false;
        return true;
    }

    void stop() {
        running_ = false;
        if (thread_.joinable()) thread_.join();
        if (cap_.isOpened()) cap_.release();
    }

private:
    std::string path_;
    bool use_video_source_;
    cv::VideoCapture cap_;
    std::thread thread_;
    std::atomic<bool> running_;
    std::mutex mtx_;
    cv::Mat latest_frame_;
    bool has_new_frame_ = false;
};

int main() {
    std::cout << "Starting edge_server_cplusplus...\n";

    // Load environment variables from .env file or ../.env
    if (!edge::utils::load_dotenv(".env")) {
        edge::utils::load_dotenv("../.env");
    }

    edge::clients::MinioClient minio(edge::config::MINIO_ENDPOINT(), "minioadmin", "minioadminpassword");
    edge::clients::MqttClient mqtt(edge::config::MQTT_BROKER(), edge::config::MQTT_PORT(), std::string("edge_") + edge::config::CAMERA_ID());
    
    edge::filters::ActiveLearningFilter al_filter;
    edge::filters::RuleBasedOodFilter ood_filter;
    edge::filters::PublishGate pub_gate;

    edge::core::SafeQueue<edge::BufferItem> ram_queue(10); // Reduced from 100 to 10 for Edge devices
    
    edge::core::DiskWriterThread disk_writer(ram_queue);
    edge::core::SyncThread sync_thread(minio, mqtt);

    // Load YOLO TensorRT model FIRST to avoid OOM crash during memory spike
    std::cout << "[Main] Loading YOLO TensorRT engine from: " << edge::config::MODEL_PATH << "... (This may take 10-30 seconds)\n";
    std::shared_ptr<yolo::Infer> yolo_infer = yolo::load(edge::config::MODEL_PATH, yolo::Type::V8, edge::config::CONFIDENCE_THRESHOLD);
    if (!yolo_infer) {
        std::cerr << "Failed to load YOLO model: " << edge::config::MODEL_PATH << "\n";
        return -1;
    }
    std::cout << "[Main] YOLO engine loaded successfully.\n";

    // Start video capture in a background thread
    std::cout << "[Main] Opening video source... (If it hangs here, check your RTSP stream)\n";
    CameraStream camera(edge::config::VIDEO_PATH(), edge::config::USE_VIDEO_SOURCE);
    if (!camera.start()) {
        std::cerr << "Failed to open video source: " << (edge::config::USE_VIDEO_SOURCE ? edge::config::VIDEO_PATH() : "Camera 0") << "\n";
        return -1;
    }

    // Start background threads ONLY AFTER TensorRT and Camera have safely allocated their memory
    disk_writer.start();
    sync_thread.start();

    // Initialize ByteTracker and VideoWriter
    ByteTracker tracker(30, 30);
    cv::VideoWriter writer;
    bool writer_initialized = false;

    std::cout << "Start processing loop (Luồng 1).\n";
    cv::Mat frame;
    int frame_count = 0;
    auto last_inference_time = std::chrono::steady_clock::now();
    
    while (true) {
        if (!camera.get_latest_frame(frame)) {
            // No new frame yet, yield to reduce CPU usage
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
            continue;
        }
        
        auto now = std::chrono::steady_clock::now();
        auto elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_inference_time).count();
        if (elapsed_ms < edge::config::INFERENCE_INTERVAL_MS) {
            continue;
        }
        last_inference_time = now;
        
        frame_count++;
        if (frame_count % 30 == 0) {
            std::cout << "[Video Reader] Successfully processed frame " << frame_count << ".\n";
        }
        
        // TensorRT Inference
        auto boxes = yolo_infer->forward(yolo::Image(frame.data, frame.cols, frame.rows));
        
        std::vector<ByteObject> byte_objects;
        byte_objects.reserve(boxes.size());
        for (const auto& b : boxes) {
            ByteObject obj;
            obj.rect = cv::Rect_<float>(b.left, b.top, b.right - b.left, b.bottom - b.top);
            obj.label = b.class_label;
            obj.prob = b.confidence;
            byte_objects.push_back(obj);
        }
        
        std::vector<STrack> tracked_stracks = tracker.update(byte_objects);

        std::vector<edge::Detection> detections;
        detections.reserve(tracked_stracks.size());
        for (const auto& t : tracked_stracks) {
            edge::Detection d;
            d.class_name = std::to_string(t.label); 
            d.conf = t.score;
            d.bbox = { static_cast<int>(t.tlbr[0]), static_cast<int>(t.tlbr[1]), static_cast<int>(t.tlbr[2]), static_cast<int>(t.tlbr[3]) };
            d.tracker_id = t.track_id;
            
            // Draw box and ID on frame
            cv::rectangle(frame, cv::Point(d.bbox[0], d.bbox[1]), cv::Point(d.bbox[2], d.bbox[3]), cv::Scalar(0, 255, 0), 2);
            cv::putText(frame, "ID: " + std::to_string(t.track_id), cv::Point(d.bbox[0], d.bbox[1] - 5), cv::FONT_HERSHEY_SIMPLEX, 0.5, cv::Scalar(0, 255, 0), 2);

            detections.push_back(d);
        }
        
        // Prepare Live Telemetry & Video (Send unconditionally)
        edge::FrameMetadata live_meta;
        live_meta.camera_id = edge::config::CAMERA_ID();
        live_meta.image_url = "raw_" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()) + ".jpg";
        live_meta.timestamp = std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
        live_meta.trigger_reason = "live_stream";
        live_meta.detections = detections;
        
        // MQTT Publishing Telemetry
        nlohmann::json j_meta;
        j_meta["camera_id"] = live_meta.camera_id;
        j_meta["image_url"] = live_meta.image_url;
        j_meta["timestamp"] = live_meta.timestamp;
        j_meta["trigger_reason"] = live_meta.trigger_reason;
        
        nlohmann::json j_dets = nlohmann::json::array();
        for (const auto& d : detections) {
            j_dets.push_back({
                {"class", d.class_name},
                {"conf", d.conf},
                {"bbox", d.bbox},
                {"tracker_id", d.tracker_id}
            });
        }
        j_meta["detections"] = j_dets;
        mqtt.publish(edge::config::LIVE_TRACKING_TOPIC, j_meta.dump(), 0);

        // Initialize VideoWriter on first frame
        if (!writer_initialized) {
            std::string backend_ip = "127.0.0.1";
            if (const char* env_ip = std::getenv("BACKEND_STREAM_IP")) {
                backend_ip = env_ip;
            }
            std::string stream_id = edge::config::CAMERA_ID();
            std::string rtsp_url = "rtsp://" + backend_ip + ":8554/" + stream_id;
            
            // GStreamer pipeline for Jetson (nvv4l2h264enc) to RTSP Push
            std::string pipeline = "appsrc ! videoconvert ! nvv4l2h264enc insert-sps-pps=true bitrate=4000000 ! h264parse ! rtspclientsink location=" + rtsp_url;
            
            std::cout << "[VideoWriter] Opening RTSP push to: " << rtsp_url << "\n";
            writer.open(pipeline, cv::CAP_GSTREAMER, 0, 15, cv::Size(frame.cols, frame.rows), true);
            if (!writer.isOpened()) {
                std::cerr << "[VideoWriter] ERROR: Failed to open GStreamer VideoWriter!\n";
            }
            writer_initialized = true;
        }

        // Write the drawn frame to RTSP stream
        if (writer.isOpened()) {
            writer.write(frame);
        }

        // Run filters for Buffer Storage
        auto [rule_hit, rule_reason] = ood_filter.should_flag_ood(detections, frame.cols, frame.rows);
        auto [al_hit, al_reason] = al_filter.should_save_frame(frame, detections);

        if (!al_hit && !rule_hit) {
            continue;
        }

        auto [should_pub, gate_reason] = pub_gate.should_publish(frame);
        if (!should_pub) {
            std::cout << "⚠️ Bị Publish Gate chặn: " << gate_reason << "\n";
            continue;
        }

        // Prepare metadata for buffer
        std::string save_reason = al_reason + " | " + rule_reason + " | " + gate_reason;
        live_meta.trigger_reason = save_reason;

        std::cout << "🚀 Active learning accepted frame: " << save_reason << "\n";

        // Push to queue (Keep full resolution frame for MinIO)
        if (!ram_queue.push({frame.clone(), live_meta})) {
            std::cout << "⚠️ RAM Queue FULL! Dropped frame.\n";
        }
    }

    camera.stop();
    disk_writer.stop();
    sync_thread.stop();

    std::cout << "Shutdown complete.\n";
    return 0;
}

