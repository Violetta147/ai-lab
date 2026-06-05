#include "../../include/utils/dotenv.hpp"
#include <fstream>
#include <sstream>
#include <cstdlib>
#include <iostream>

#ifdef _WIN32
#include <windows.h>
#endif

namespace edge {
namespace utils {

bool load_dotenv(const std::string& filepath) {
    std::ifstream file(filepath);
    if (!file.is_open()) {
        std::cerr << "Warning: Could not open dotenv file: " << filepath << std::endl;
        return false;
    }

    std::string line;
    while (std::getline(file, line)) {
        // Remove leading whitespace
        size_t start = line.find_first_not_of(" \t");
        if (start == std::string::npos) continue;
        line = line.substr(start);

        // Skip comments and empty lines
        if (line.empty() || line[0] == '#') continue;

        // Find '='
        size_t equals_pos = line.find('=');
        if (equals_pos != std::string::npos) {
            std::string key = line.substr(0, equals_pos);
            std::string value = line.substr(equals_pos + 1);

            // Trim trailing whitespace from value and key
            key.erase(key.find_last_not_of(" \t") + 1);
            value.erase(value.find_last_not_of(" \t\r\n") + 1);
            
            // Remove quotes if present
            if (value.size() >= 2 && ((value.front() == '"' && value.back() == '"') || (value.front() == '\'' && value.back() == '\''))) {
                value = value.substr(1, value.size() - 2);
            }

            // Set environment variable
#ifdef _WIN32
            if (std::getenv(key.c_str()) == nullptr) {
                _putenv_s(key.c_str(), value.c_str());
            }
#else
            setenv(key.c_str(), value.c_str(), 0);
#endif
        }
    }
    
    return true;
}

} // namespace utils
} // namespace edge
