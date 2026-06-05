#include "mqtt_client.hpp"
#include <iostream>

namespace edge {
namespace clients {

MqttClient::MqttClient(const std::string& broker, int port, const std::string& client_id)
    : broker_(broker), port_(port), client_id_(client_id), is_connected_(false) {
    std::string address = "tcp://" + broker + ":" + std::to_string(port);
    
    int rc = MQTTClient_create(&client_, address.c_str(), client_id.c_str(),
        MQTTCLIENT_PERSISTENCE_NONE, NULL);
    if (rc != MQTTCLIENT_SUCCESS) {
        std::cerr << "[MqttClient] Failed to create client, return code " << rc << std::endl;
        return;
    }

    MQTTClient_connectOptions conn_opts = MQTTClient_connectOptions_initializer;
    conn_opts.keepAliveInterval = 20;
    conn_opts.cleansession = 1;

    rc = MQTTClient_connect(client_, &conn_opts);
    if (rc != MQTTCLIENT_SUCCESS) {
        std::cerr << "[MqttClient] Failed to connect, return code " << rc << std::endl;
        return;
    }
    
    is_connected_ = true;
    std::cout << "[MqttClient] Initializing client " << client_id << " at " << address << std::endl;
}

MqttClient::~MqttClient() {
    if (is_connected_) {
        MQTTClient_disconnect(client_, 10000);
    }
    MQTTClient_destroy(&client_);
    std::cout << "[MqttClient] Disconnected" << std::endl;
}

bool MqttClient::publish(const std::string& topic, const std::string& payload, int qos) {
    if (!is_connected_) return false;

    MQTTClient_message pubmsg = MQTTClient_message_initializer;
    pubmsg.payload = (void*)payload.c_str();
    pubmsg.payloadlen = (int)payload.length();
    pubmsg.qos = qos;
    pubmsg.retained = 0;

    MQTTClient_deliveryToken token;
    int rc = MQTTClient_publishMessage(client_, topic.c_str(), &pubmsg, &token);
    if (rc != MQTTCLIENT_SUCCESS) {
        std::cerr << "[MqttClient] Failed to publish message, return code " << rc << std::endl;
        return false;
    }

    // Wait briefly (or rely on QoS 0 fire-and-forget for live video)
    // For live video streaming we might use QoS 0. If QoS > 0, we wait.
    if (qos > 0) {
        rc = MQTTClient_waitForCompletion(client_, token, 1000L);
        if (rc != MQTTCLIENT_SUCCESS) {
            std::cerr << "[MqttClient] Failed to wait for publish completion, return code " << rc << std::endl;
            return false;
        }
    }

    return true;
}

void MqttClient::subscribe(const std::string& topic, std::function<void(const std::string&)> callback, int qos) {
    // TODO: Implement actual Paho MQTT subscribe using MQTTClient_subscribe and MQTTClient_setCallbacks
    std::cout << "[MqttClient] Subscribed to " << topic << std::endl;
}

void MqttClient::loop_start() {
    // TODO: Implement background network thread or call MQTTClient_yield periodically
    std::cout << "[MqttClient] Loop started" << std::endl;
}

void MqttClient::loop_stop() {
    // TODO: Stop background thread if implemented
    std::cout << "[MqttClient] Loop stopped" << std::endl;
}

} // namespace clients
} // namespace edge
