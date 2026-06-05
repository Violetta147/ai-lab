#include "minio_client.hpp"
#include <iostream>
#include <sys/stat.h>

namespace edge {
namespace clients {

MinioClient::MinioClient(const std::string& endpoint, const std::string& access_key, const std::string& secret_key)
    : endpoint_(endpoint), access_key_(access_key), secret_key_(secret_key) {
    curl_global_init(CURL_GLOBAL_ALL);
    std::cout << "[MinioClient] Initialized for endpoint: " << endpoint_ << std::endl;
}

MinioClient::~MinioClient() {
    curl_global_cleanup();
}

bool MinioClient::upload_file(const std::string& bucket_name, const std::string& object_name, const std::string& file_path) {
    CURL* curl = curl_easy_init();
    if (!curl) {
        std::cerr << "[MinioClient] Failed to initialize CURL" << std::endl;
        return false;
    }

    FILE* fd = fopen(file_path.c_str(), "rb");
    if (!fd) {
        std::cerr << "[MinioClient] Failed to open file: " << file_path << std::endl;
        curl_easy_cleanup(curl);
        return false;
    }

    struct stat file_info;
    if (fstat(fileno(fd), &file_info) != 0) {
        std::cerr << "[MinioClient] Failed to get file size: " << file_path << std::endl;
        fclose(fd);
        curl_easy_cleanup(curl);
        return false;
    }

    std::string url = "http://" + endpoint_ + "/" + bucket_name + "/" + object_name;

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_UPLOAD, 1L);
    curl_easy_setopt(curl, CURLOPT_READDATA, fd);
    curl_easy_setopt(curl, CURLOPT_INFILESIZE_LARGE, static_cast<curl_off_t>(file_info.st_size));

    std::string user_pwd = access_key_ + ":" + secret_key_;
    curl_easy_setopt(curl, CURLOPT_USERPWD, user_pwd.c_str());
    
    // Use libcurl's built-in AWS SigV4 support (curl >= 7.75.0)
    curl_easy_setopt(curl, CURLOPT_AWS_SIGV4, "s3:us-east-1:auto");

    // MinIO requires x-amz-content-sha256 header. Libcurl doesn't add it automatically.
    struct curl_slist* headers = NULL;
    headers = curl_slist_append(headers, "x-amz-content-sha256: UNSIGNED-PAYLOAD");
    headers = curl_slist_append(headers, "Content-Type: application/octet-stream");
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);

    CURLcode res = curl_easy_perform(curl);
    
    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);

    fclose(fd);
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);

    if (res != CURLE_OK) {
        std::cerr << "[MinioClient] Upload failed: " << curl_easy_strerror(res) << std::endl;
        return false;
    }
    
    if (http_code != 200 && http_code != 204) {
        std::cerr << "[MinioClient] Upload failed with HTTP code: " << http_code << std::endl;
        return false;
    }

    std::cout << "[MinioClient] Successfully uploaded " << file_path << " to " << bucket_name << "/" << object_name << std::endl;
    return true;
}

} // namespace clients
} // namespace edge
