#include "disk_writer_thread.hpp"
#include <iostream>
#include <opencv2/opencv.hpp>
#include <nlohmann/json.hpp>
#include <fstream>

using json = nlohmann::json;

namespace edge {
namespace core {

DiskWriterThread::DiskWriterThread(SafeQueue<BufferItem>& queue) : queue_(queue) {}

DiskWriterThread::~DiskWriterThread() {
    stop();
}

void DiskWriterThread::start() {
    running_ = true;
    thread_ = std::thread(&DiskWriterThread::run, this);
}

void DiskWriterThread::stop() {
    running_ = false;
    if (thread_.joinable()) {
        thread_.join();
    }
}

#include <filesystem>

void DiskWriterThread::run() {
    std::cout << "🚀 Disk Writer Thread started.\n";
    std::filesystem::create_directory("buffer");
    while (running_) {
        auto item = queue_.pop(std::chrono::milliseconds(1000));
        if (!item) {
            continue;
        }

        // Save frame
        std::string img_path = "buffer/" + item->metadata.image_url;
        cv::imwrite(img_path, item->frame);

        // Save metadata
        json j;
        j["camera_id"] = item->metadata.camera_id;
        j["image_url"] = item->metadata.image_url;
        j["timestamp"] = item->metadata.timestamp;
        j["trigger_reason"] = item->metadata.trigger_reason;
        
        json dets = json::array();
        for (const auto& d : item->metadata.detections) {
            dets.push_back({
                {"class", d.class_name},
                {"conf", d.conf},
                {"bbox", d.bbox}
            });
        }
        j["detections"] = dets;

        std::string json_path = img_path + ".json";
        std::string tmp_json_path = json_path + ".tmp";
        std::ofstream o(tmp_json_path);
        o << j.dump(4) << std::endl;
        o.close();
        
        // Atomic rename to ensure SyncThread doesn't read partial files
        rename(tmp_json_path.c_str(), json_path.c_str());

        // std::cout << "Saved " << img_path << std::endl;
    }
}

} // namespace core
} // namespace edge
