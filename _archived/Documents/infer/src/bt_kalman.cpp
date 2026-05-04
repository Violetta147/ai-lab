#include "bt_kalman.hpp"

#include <Eigen/Cholesky>

namespace byte_kalman {

KalmanFilter::KalmanFilter()
    : std_weight_position_(1.0f / 20.0f), std_weight_velocity_(1.0f / 160.0f) {
  const int ndim = 4;
  const float dt = 1.0f;
  motion_mat_ = Eigen::Matrix<float, 8, 8>::Identity();
  for (int i = 0; i < ndim; i++) {
    motion_mat_(i, ndim + i) = dt;
  }
  update_mat_ = Eigen::Matrix<float, 4, 8>::Identity();
}

KAL_DATA KalmanFilter::initiate(const DETECTBOX &measurement) {
  KAL_MEAN mean;
  mean.head<4>() = measurement;
  mean.tail<4>().setZero();

  KAL_MEAN std_dev;
  std_dev(0) = 2.0f * std_weight_position_ * measurement(3);
  std_dev(1) = 2.0f * std_weight_position_ * measurement(3);
  std_dev(2) = 1e-2f;
  std_dev(3) = 2.0f * std_weight_position_ * measurement(3);
  std_dev(4) = 10.0f * std_weight_velocity_ * measurement(3);
  std_dev(5) = 10.0f * std_weight_velocity_ * measurement(3);
  std_dev(6) = 1e-5f;
  std_dev(7) = 10.0f * std_weight_velocity_ * measurement(3);

  KAL_COVA covariance = std_dev.array().square().matrix().asDiagonal();
  return std::make_pair(mean, covariance);
}

void KalmanFilter::predict(KAL_MEAN &mean, KAL_COVA &covariance) {
  DETECTBOX std_pos;
  std_pos << std_weight_position_ * mean(3), std_weight_position_ * mean(3), 1e-2f,
      std_weight_position_ * mean(3);
  DETECTBOX std_vel;
  std_vel << std_weight_velocity_ * mean(3), std_weight_velocity_ * mean(3), 1e-5f,
      std_weight_velocity_ * mean(3);
  KAL_MEAN tmp;
  tmp.head<4>() = std_pos;
  tmp.tail<4>() = std_vel;
  KAL_COVA motion_cov = tmp.array().square().matrix().asDiagonal();

  KAL_MEAN mean1 = motion_mat_ * mean;
  KAL_COVA covariance1 = motion_mat_ * covariance * motion_mat_.transpose() + motion_cov;
  mean = mean1;
  covariance = covariance1;
}

KAL_HDATA KalmanFilter::project(const KAL_MEAN &mean, const KAL_COVA &covariance) {
  DETECTBOX std_diag;
  std_diag << std_weight_position_ * mean(3), std_weight_position_ * mean(3), 1e-1f,
      std_weight_position_ * mean(3);
  KAL_HMEAN mean1 = update_mat_ * mean;
  KAL_HCOVA covariance1 = update_mat_ * covariance * update_mat_.transpose();
  covariance1 += std_diag.array().square().matrix().asDiagonal();
  return std::make_pair(mean1, covariance1);
}

KAL_DATA KalmanFilter::update(const KAL_MEAN &mean, const KAL_COVA &covariance,
                              const DETECTBOX &measurement) {
  KAL_HDATA pa = project(mean, covariance);
  KAL_HMEAN projected_mean = pa.first;
  KAL_HCOVA projected_cov = pa.second;

  Eigen::Matrix<float, 8, 4> PHt = covariance * update_mat_.transpose();
  Eigen::Matrix<float, 4, 4> I4 = Eigen::Matrix<float, 4, 4>::Identity();
  Eigen::Matrix<float, 4, 4> Sinv = projected_cov.llt().solve(I4);
  Eigen::Matrix<float, 8, 4> kalman_gain = PHt * Sinv;

  DETECTBOX innovation = measurement - projected_mean;
  KAL_MEAN new_mean = mean + kalman_gain * innovation;
  KAL_COVA new_covariance =
      covariance - kalman_gain * projected_cov * kalman_gain.transpose();
  return std::make_pair(new_mean, new_covariance);
}

}  // namespace byte_kalman
