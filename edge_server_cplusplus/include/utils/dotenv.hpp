#pragma once

#include <string>

namespace edge {
namespace utils {

/**
 * Loads environment variables from a .env file.
 * Lines should be in KEY=VALUE format. Comments starting with # are ignored.
 * @param filepath Path to the .env file.
 * @return true if file was successfully opened and read, false otherwise.
 */
bool load_dotenv(const std::string& filepath = ".env");

} // namespace utils
} // namespace edge
