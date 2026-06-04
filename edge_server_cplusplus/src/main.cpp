#include <iostream>
#include <vector>
#include <string>
#include <opencv2/opencv.hpp>
#include <chrono>

#include "../include/config.hpp"
#include "../include/types.hpp"
#include "../include/safe_queue.hpp"
#include "filters/active_learning.hpp"
#include "filters/rule_ood.hpp"
#include "filters/publish_gate.hpp"
#include "clients/mqtt_client.hpp"
#include "clients/minio_client.hpp"
#include "core/disk_writer_thread.hpp"
#include "core/sync_thread.hpp"

// Forward declare the YOLO TensorRT interface (simulated for compilation)
namespace yolo {
    void load(const std::string& model_path);
    std::vector<edge::Detection> infer(const cv::Mat& frame, float conf_thres);
}

int main() {
    std::cout << "Starting edge_server_cplusplus...\n";

    edge::clients::MinioClient minio("localhost", "minioadmin", "minioadmin");
    edge::clients::MqttClient mqtt(edge::config::MQTT_BROKER, edge::config::MQTT_PORT, std::string("edge_") + edge::config::CAMERA_ID);
    
    edge::filters::ActiveLearningFilter al_filter;
    edge::filters::RuleBasedOodFilter ood_filter;
    edge::filters::PublishGate pub_gate;

    edge::core::SafeQueue<edge::BufferItem> ram_queue(100);
    
    edge::core::DiskWriterThread disk_writer(ram_queue);
    edge::core::SyncThread sync_thread(minio, mqtt);

    disk_writer.start();
    sync_thread.start();

    // Start video capture
    cv::VideoCapture capture;
    if (edge::config::USE_VIDEO_SOURCE) {
        capture.open(edge::config::VIDEO_PATH);
    } else {
        capture.open(0);
    }

    if (!capture.isOpened()) {
        std::cerr << "Failed to open video source.\n";
        return -1;
    }

    std::cout << "Start processing loop (Luồng 1).\n";
    cv::Mat frame;
    
    // yolo::load(edge::config::MODEL_PATH);

    while (capture.read(frame)) {
        if (frame.empty()) break;
        
        // Mocking YOLO detections to allow this skeleton to compile without full TensorRT CUDA link
        std::vector<edge::Detection> detections; 
        // std::vector<edge::Detection> detections = yolo::infer(frame, edge::config::CONFIDENCE_THRESHOLD);
        
        // Run filters
        auto [rule_hit, rule_reason] = ood_filter.should_flag_ood(detections, frame.cols, frame.rows);
        auto [al_hit, al_reason] = al_filter.should_save_frame(frame, detections);

        if (!al_hit && !rule_hit) {
            continue;
        }

        auto [should_pub, gate_reason] = pub_gate.should_publish(frame);
        if (!should_pub) {
            continue;
        }

        // Prepare metadata
        std::string save_reason = al_reason + " | " + rule_reason + " | " + gate_reason;
        
        edge::FrameMetadata meta;
        meta.camera_id = edge::config::CAMERA_ID;
        meta.image_url = "raw_" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()) + ".jpg";
        meta.timestamp = std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
        meta.trigger_reason = save_reason;
        meta.detections = detections;

        std::cout << "🚀 Active learning accepted frame: " << save_reason << "\n";

        // Push to queue
        if (!ram_queue.push({frame.clone(), meta})) {
            std::cout << "⚠️ RAM Queue FULL! Dropped frame.\n";
        }
        
        // Live MQTT Publish
        // mqtt.publish(edge::config::LIVE_MQTT_TOPIC, "JSON_METADATA_HERE");
    }

    disk_writer.stop();
    sync_thread.stop();

    std::cout << "Shutdown complete.\n";
    return 0;
}
