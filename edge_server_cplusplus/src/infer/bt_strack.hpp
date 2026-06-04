#pragma once

#include <opencv2/core.hpp>
#include <vector>

#include "bt_kalman.hpp"
#include "bt_types.hpp"

class STrack {
 public:
  STrack(const std::vector<float> &tlwh_, float score, int label);

  static std::vector<float> tlbr_to_tlwh(std::vector<float> &tlbr);
  static void multi_predict(std::vector<STrack *> &stracks, byte_kalman::KalmanFilter &kalman_filter);

  void static_tlwh();
  void static_tlbr();
  std::vector<float> tlwh_to_xyah(const std::vector<float> &tlwh_tmp);
  void mark_lost();
  void mark_removed();
  static int next_id();
  int end_frame() const;

  void activate(byte_kalman::KalmanFilter &kalman_filter, int frame_id);
  void re_activate(STrack &new_track, int frame_id, bool new_id);
  void update(STrack &new_track, int frame_id);

  bool is_activated;
  int track_id;
  int state;
  int label;

  std::vector<float> _tlwh;
  std::vector<float> tlwh;
  std::vector<float> tlbr;
  int frame_id;
  int tracklet_len;
  int start_frame;

  KAL_MEAN mean;
  KAL_COVA covariance;
  float score;

 private:
  byte_kalman::KalmanFilter kalman_filter_;
};
