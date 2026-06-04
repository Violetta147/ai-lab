#include "sync_thread.hpp"
#include <iostream>
#include <chrono>

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
    while (running_) {
        // Sleep to yield CPU
        std::this_thread::sleep_for(std::chrono::seconds(2));

        // In a full implementation, this would scan the "buffer/" directory,
        // read the .json and .jpg files, upload them via minio_client_,
        // and then publish success to mqtt_client_.
        // For the sake of this C++ structure scaffolding, we sleep.
    }
}

} // namespace core
} // namespace edge
