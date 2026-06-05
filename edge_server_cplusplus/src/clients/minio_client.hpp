#pragma once

#include <string>
#include <curl/curl.h>

namespace edge {
namespace clients {

class MinioClient {
public:
    MinioClient(const std::string& endpoint, const std::string& access_key, const std::string& secret_key);
    ~MinioClient();

    // Prevent copies
    MinioClient(const MinioClient&) = delete;
    MinioClient& operator=(const MinioClient&) = delete;
    MinioClient(MinioClient&&) = delete;
    MinioClient& operator=(MinioClient&&) = delete;

    bool upload_file(const std::string& bucket_name, const std::string& object_name, const std::string& file_path);

private:
    std::string endpoint_;
    std::string access_key_;
    std::string secret_key_;
};

} // namespace clients
} // namespace edge
