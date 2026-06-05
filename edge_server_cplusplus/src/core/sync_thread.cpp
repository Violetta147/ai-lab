#include "sync_thread.hpp"
#include <iostream>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <nlohmann/json.hpp>
#include "../../include/config.hpp"

namespace edge {
namespace core {

SyncThread::SyncThread(clients::MinioClient& minio_client, clients::MqttClient& mqtt_client)
    : minio_client_(minio_client), mqtt_client_(mqtt_client) {}

SyncThread::~SyncThread() {
    stop();
}

void SyncThread::start() {
    running_ = true;
    thread_ = std::thread(&SyncThread::run, this);
}

void SyncThread::stop() {
    running_ = false;
    if (thread_.joinable()) {
        thread_.join();
    }
}

void SyncThread::run() {
    std::cout << "☁️ Background Sync Thread started.\n";
    std::filesystem::path buffer_dir("buffer");

    while (running_) {
        std::this_thread::sleep_for(std::chrono::seconds(2));

        if (!std::filesystem::exists(buffer_dir) || !std::filesystem::is_directory(buffer_dir)) {
            continue;
        }

        try {
            for (const auto& entry : std::filesystem::directory_iterator(buffer_dir)) {
                if (!entry.is_regular_file()) continue;

                auto path = entry.path();
                if (path.extension() == ".json") {
                    std::string json_path = path.string();
                    std::string img_path = json_path.substr(0, json_path.length() - 5); // remove .json

                    if (std::filesystem::exists(img_path)) {
                        try {
                            std::filesystem::path img_p(img_path);
                            bool img_ok = minio_client_.upload_file(edge::config::MINIO_BUCKET, img_p.filename().string(), img_path);

                            if (img_ok) {
                                // Read JSON to publish to MQTT
                                std::ifstream f(json_path);
                                if (!f.is_open()) {
                                    std::cerr << "[SyncThread] Cannot open JSON file: " << json_path << std::endl;
                                    continue;
                                }
                                nlohmann::json data = nlohmann::json::parse(f);
                                mqtt_client_.publish(edge::config::METADATA_TOPIC, data.dump());

                                // Delete both
                                f.close();
                                std::filesystem::remove(img_path);
                                std::filesystem::remove(json_path);
                                std::cout << "[SyncThread] Synced and removed: " << path.filename().string() << std::endl;
                            } else {
                                std::cerr << "[SyncThread] Failed to sync: " << path.filename().string() << std::endl;
                            }
                        } catch (const nlohmann::json::exception& e) {
                            std::cerr << "[SyncThread] JSON Parse error for " << json_path << ": " << e.what() << std::endl;
                            std::filesystem::remove(img_path);
                            std::filesystem::remove(json_path);
                        } catch (const std::exception& e) {
                            std::cerr << "[SyncThread] Error processing file " << json_path << ": " << e.what() << std::endl;
                            // Optionally remove corrupted files to prevent infinite loop
                            std::filesystem::remove(img_path);
                            std::filesystem::remove(json_path);
                        }
                    }
                }
            }
        } catch (const std::filesystem::filesystem_error& e) {
            std::cerr << "[SyncThread] Filesystem error: " << e.what() << std::endl;
        } catch (const std::exception& e) {
            std::cerr << "[SyncThread] Exception: " << e.what() << std::endl;
        }
    }
}

} // namespace core
} // namespace edge
