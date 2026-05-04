#pragma once

#include "bt_types.hpp"

namespace byte_kalman {

class KalmanFilter {
 public:
  KalmanFilter();
  KAL_DATA initiate(const DETECTBOX &measurement);
  void predict(KAL_MEAN &mean, KAL_COVA &covariance);
  KAL_DATA update(const KAL_MEAN &mean, const KAL_COVA &covariance, const DETECTBOX &measurement);

 private:
  KAL_HDATA project(const KAL_MEAN &mean, const KAL_COVA &covariance);

  Eigen::Matrix<float, 8, 8> motion_mat_;
  Eigen::Matrix<float, 4, 8> update_mat_;
  float std_weight_position_;
  float std_weight_velocity_;
};

}  // namespace byte_kalman
