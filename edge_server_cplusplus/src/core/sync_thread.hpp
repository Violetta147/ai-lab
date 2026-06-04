#pragma once

#include "../clients/minio_client.hpp"
#include "../clients/mqtt_client.hpp"
#include <thread>
#include <atomic>

namespace edge {
namespace core {

class SyncThread {
public:
    SyncThread(clients::MinioClient& minio_client, clients::MqttClient& mqtt_client);
    ~SyncThread();

    void start();
    void stop();

private:
    void run();

    clients::MinioClient& minio_client_;
    clients::MqttClient& mqtt_client_;
    std::thread thread_;
    std::atomic<bool> running_{false};
};

} // namespace core
} // namespace edge
