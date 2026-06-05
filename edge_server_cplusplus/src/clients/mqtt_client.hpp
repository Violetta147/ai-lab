#pragma once

#include <string>
#include <functional>
#include <MQTTClient.h>

namespace edge {
namespace clients {

class MqttClient {
public:
    MqttClient(const std::string& broker, int port, const std::string& client_id);
    ~MqttClient();

    // Delete copy/move as per C.21
    MqttClient(const MqttClient&) = delete;
    MqttClient& operator=(const MqttClient&) = delete;
    MqttClient(MqttClient&&) = delete;
    MqttClient& operator=(MqttClient&&) = delete;

    bool publish(const std::string& topic, const std::string& payload, int qos = 0);
    void subscribe(const std::string& topic, std::function<void(const std::string&)> callback, int qos = 1);
    void loop_start();
    void loop_stop();

private:
    std::string broker_;
    int port_;
    std::string client_id_;
    MQTTClient client_;
    bool is_connected_;
};

} // namespace clients
} // namespace edge
