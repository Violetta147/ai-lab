#include "sync_thread.hpp"
#include <iostream>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <nlohmann/json.hpp>
#include "../../include/config.hpp"

#ifndef _WIN32
#include <sys/sysinfo.h>
#include <sys/types.h>
#include <dirent.h>
#include <cstdio>
#endif

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
    std::string buffer_dir = "buffer";

    while (running_) {
        std::this_thread::sleep_for(std::chrono::seconds(2));

#ifndef _WIN32
        DIR* dir = opendir(buffer_dir.c_str());
        if (!dir) {
            continue;
        }

        try {
            struct dirent* ent;
            while ((ent = readdir(dir)) != NULL) {
                std::string filename = ent->d_name;
                if (filename == "." || filename == "..") {
                    continue;
                }

                // Check if it is a JSON file
                if (filename.length() > 5 && filename.substr(filename.length() - 5) == ".json") {
                    std::string json_path = buffer_dir + "/" + filename;
                    std::string img_filename = filename.substr(0, filename.length() - 5); // remove .json
                    std::string img_path = buffer_dir + "/" + img_filename;

                    std::ifstream check_img(img_path);
                    if (check_img.good()) {
                        check_img.close();
                        try {
                            bool img_ok = minio_client_.upload_file(edge::config::MINIO_BUCKET, img_filename, img_path);

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
                                std::remove(img_path.c_str());
                                std::remove(json_path.c_str());
                                std::cout << "[SyncThread] Synced and removed: " << filename << std::endl;
                            } else {
                                std::cerr << "[SyncThread] Failed to sync: " << filename << std::endl;
                            }
                        } catch (const nlohmann::json::exception& e) {
                            std::cerr << "[SyncThread] JSON Parse error for " << json_path << ": " << e.what() << std::endl;
                            std::remove(img_path.c_str());
                            std::remove(json_path.c_str());
                        } catch (const std::exception& e) {
                            std::cerr << "[SyncThread] Error processing file " << json_path << ": " << e.what() << std::endl;
                            std::remove(img_path.c_str());
                            std::remove(json_path.c_str());
                        }
                    }
                }
            }
            closedir(dir);
        } catch (const std::exception& e) {
            std::cerr << "[SyncThread] Exception in read loop: " << e.what() << std::endl;
            struct sysinfo si;
            if (sysinfo(&si) == 0) {
                std::cerr << "[SyncThread] Memory at crash - Free RAM: " 
                          << (si.freeram * si.mem_unit) / (1024 * 1024) << " MB / "
                          << (si.totalram * si.mem_unit) / (1024 * 1024) << " MB, "
                          << "Free Swap: " << (si.freeswap * si.mem_unit) / (1024 * 1024) << " MB"
                          << std::endl;
            }
            closedir(dir);
        }
#else
        // Windows fallback using std::filesystem
        std::filesystem::path buffer_path(buffer_dir);
        if (!std::filesystem::exists(buffer_path) || !std::filesystem::is_directory(buffer_path)) {
            continue;
        }
        try {
            for (const auto& entry : std::filesystem::directory_iterator(buffer_path)) {
                if (!entry.is_regular_file()) continue;

                auto path = entry.path();
                if (path.extension() == ".json") {
                    std::string json_path = path.string();
                    std::string img_path = json_path.substr(0, json_path.length() - 5);

                    if (std::filesystem::exists(img_path)) {
                        try {
                            std::filesystem::path img_p(img_path);
                            bool img_ok = minio_client_.upload_file(edge::config::MINIO_BUCKET, img_p.filename().string(), img_path);

                            if (img_ok) {
                                std::ifstream f(json_path);
                                if (!f.is_open()) continue;
                                nlohmann::json data = nlohmann::json::parse(f);
                                mqtt_client_.publish(edge::config::METADATA_TOPIC, data.dump());
                                f.close();
                                std::filesystem::remove(img_path);
                                std::filesystem::remove(json_path);
                            }
                        } catch (...) {}
                    }
                }
            }
        } catch (...) {}
#endif
    }
}

} // namespace core
} // namespace edge
