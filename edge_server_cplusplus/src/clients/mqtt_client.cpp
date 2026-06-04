#include "mqtt_client.hpp"
#include <iostream>

// Note: Using stub implementation for paho-mqtt3c to keep the example clean

namespace edge {
namespace clients {

MqttClient::MqttClient(const std::string& broker, int port, const std::string& client_id)
    : broker_(broker), port_(port), client_id_(client_id) {
    std::cout << "[MqttClient] Initializing client " << client_id << " at " << broker << ":" << port << std::endl;
}

MqttClient::~MqttClient() {
    std::cout << "[MqttClient] Disconnected" << std::endl;
}

bool MqttClient::publish(const std::string& topic, const std::string& payload, int qos) {
    // std::cout << "[MqttClient] Publish to " << topic << std::endl;
    return true;
}

void MqttClient::subscribe(const std::string& topic, std::function<void(const std::string&)> callback, int qos) {
    std::cout << "[MqttClient] Subscribed to " << topic << std::endl;
}

void MqttClient::loop_start() {
    std::cout << "[MqttClient] Loop started" << std::endl;
}

void MqttClient::loop_stop() {
    std::cout << "[MqttClient] Loop stopped" << std::endl;
}

} // namespace clients
} // namespace edge
