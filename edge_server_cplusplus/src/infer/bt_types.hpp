#pragma once

#include <Eigen/Core>
#include <utility>
#include <vector>

typedef Eigen::Matrix<float, 4, 1> DETECTBOX;
typedef Eigen::Matrix<float, 8, 1> KAL_MEAN;
typedef Eigen::Matrix<float, 8, 8> KAL_COVA;
typedef Eigen::Matrix<float, 4, 1> KAL_HMEAN;
typedef Eigen::Matrix<float, 4, 4> KAL_HCOVA;

using KAL_DATA = std::pair<KAL_MEAN, KAL_COVA>;
using KAL_HDATA = std::pair<KAL_HMEAN, KAL_HCOVA>;

enum class TrackState : int { New = 0, Tracked, Lost, Removed };
