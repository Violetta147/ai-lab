#pragma once

#include <string>
#include <vector>
#include <opencv2/opencv.hpp>

namespace edge {
namespace utils {

/**
 * @brief Encode a raw byte buffer into a Base64 string.
 * 
 * @param buf Pointer to the byte buffer.
 * @param bufLen Length of the byte buffer.
 * @return std::string Base64 encoded string.
 */
std::string base64_encode(const unsigned char* buf, unsigned int bufLen);

/**
 * @brief Compress an OpenCV Mat to JPEG and encode it to a Base64 string.
 * 
 * @param image The input image.
 * @param quality JPEG compression quality (0-100). Default is 80.
 * @return std::string Base64 encoded string of the JPEG image.
 */
std::string base64_encode_image(const cv::Mat& image, int quality = 80);

} // namespace utils
} // namespace edge
