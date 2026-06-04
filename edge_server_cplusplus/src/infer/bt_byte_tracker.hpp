#pragma once

#include <opencv2/core.hpp>
#include <utility>
#include <vector>

#include "bt_kalman.hpp"
#include "bt_strack.hpp"

struct ByteObject {
  cv::Rect_<float> rect;
  int label;
  float prob;
};

class ByteTracker {
 public:
  ByteTracker(int frame_rate, int track_buffer);
  std::vector<STrack> update(const std::vector<ByteObject> &objects);

 private:
  std::vector<STrack *> joint_stracks(const std::vector<STrack *> &tlista,
                                      std::vector<STrack> &tlistb);
  std::vector<STrack> joint_stracks(std::vector<STrack> &tlista, std::vector<STrack> &tlistb);

  std::vector<STrack> sub_stracks(const std::vector<STrack> &tlista,
                                  const std::vector<STrack> &tlistb);

  void remove_duplicate_stracks(std::vector<STrack> &resa, std::vector<STrack> &resb,
                                std::vector<STrack> &stracksa, std::vector<STrack> &stracksb);

  void linear_assignment(const std::vector<std::vector<float>> &cost_matrix, int cost_matrix_size,
                         int cost_matrix_size_size, float thresh,
                         std::vector<std::vector<int>> &matches, std::vector<int> &unmatched_a,
                         std::vector<int> &unmatched_b);

  std::vector<std::vector<float>> iou_distance(const std::vector<STrack *> &atracks,
                                                 const std::vector<STrack> &btracks, int &dist_size,
                                                 int &dist_size_size);

  std::vector<std::vector<float>> iou_distance(const std::vector<STrack> &atracks,
                                                 const std::vector<STrack> &btracks);

  static std::vector<std::vector<float>> ious(const std::vector<std::vector<float>> &atlbrs,
                                                const std::vector<std::vector<float>> &btlbrs);

  float track_thresh_;
  float high_thresh_;
  float match_thresh_;
  int frame_id_;
  int max_time_lost_;

  std::vector<STrack> tracked_stracks_;
  std::vector<STrack> lost_stracks_;
  std::vector<STrack> removed_stracks_;
  byte_kalman::KalmanFilter kalman_filter_;
};
