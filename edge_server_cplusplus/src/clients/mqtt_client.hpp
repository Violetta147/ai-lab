#pragma once

#include <string>
#include <functional>

namespace edge {
namespace clients {

class MqttClient {
public:
    MqttClient(const std::string& broker, int port, const std::string& client_id);
    ~MqttClient();

    bool publish(const std::string& topic, const std::string& payload, int qos = 1);
    void subscribe(const std::string& topic, std::function<void(const std::string&)> callback, int qos = 1);
    void loop_start();
    void loop_stop();

private:
    std::string broker_;
    int port_;
    std::string client_id_;
    // In a real implementation this would hold the MQTTAsync handle from paho-mqtt3c
};

} // namespace clients
} // namespace edge
