#include "bt_byte_tracker.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <map>

namespace {

float bbox_iou(const std::vector<float> &a, const std::vector<float> &b) {
  const float ax1 = a[0];
  const float ay1 = a[1];
  const float ax2 = a[2];
  const float ay2 = a[3];
  const float bx1 = b[0];
  const float by1 = b[1];
  const float bx2 = b[2];
  const float by2 = b[3];
  const float iw = std::min(ax2, bx2) - std::max(ax1, bx1);
  if (iw <= 0.0f) {
    return 0.0f;
  }
  const float ih = std::min(ay2, by2) - std::max(ay1, by1);
  if (ih <= 0.0f) {
    return 0.0f;
  }
  const float inter = iw * ih;
  const float area_a = (ax2 - ax1) * (ay2 - ay1);
  const float area_b = (bx2 - bx1) * (by2 - by1);
  const float ua = area_a + area_b - inter;
  if (ua <= 0.0f) {
    return 0.0f;
  }
  return inter / ua;
}

}  // namespace

ByteTracker::ByteTracker(int frame_rate, int track_buffer)
    : track_thresh_(0.5f),
      high_thresh_(0.6f),
      match_thresh_(0.8f),
      frame_id_(0),
      max_time_lost_(static_cast<int>(static_cast<float>(frame_rate) / 30.0f *
                                       static_cast<float>(track_buffer))) {
  printf("[bytetrack] ByteTracker init frame_rate=%d track_buffer=%d max_time_lost=%d\n",
         frame_rate, track_buffer, max_time_lost_);
}

std::vector<STrack *> ByteTracker::joint_stracks(const std::vector<STrack *> &tlista,
                                                   std::vector<STrack> &tlistb) {
  std::map<int, int> exists;
  std::vector<STrack *> res;
  for (size_t i = 0; i < tlista.size(); i++) {
    exists[tlista[i]->track_id] = 1;
    res.push_back(tlista[i]);
  }
  for (size_t i = 0; i < tlistb.size(); i++) {
    const int tid = tlistb[i].track_id;
    if (exists.find(tid) == exists.end()) {
      exists[tid] = 1;
      res.push_back(&tlistb[i]);
    }
  }
  return res;
}

std::vector<STrack> ByteTracker::joint_stracks(std::vector<STrack> &tlista,
                                               std::vector<STrack> &tlistb) {
  std::map<int, int> exists;
  std::vector<STrack> res;
  for (size_t i = 0; i < tlista.size(); i++) {
    exists[tlista[i].track_id] = 1;
    res.push_back(tlista[i]);
  }
  for (size_t i = 0; i < tlistb.size(); i++) {
    const int tid = tlistb[i].track_id;
    if (exists.find(tid) == exists.end()) {
      exists[tid] = 1;
      res.push_back(tlistb[i]);
    }
  }
  return res;
}

std::vector<STrack> ByteTracker::sub_stracks(const std::vector<STrack> &tlista,
                                             const std::vector<STrack> &tlistb) {
  std::map<int, STrack> stracks;
  for (size_t i = 0; i < tlista.size(); i++) {
    stracks.insert(std::pair<int, STrack>(tlista[i].track_id, tlista[i]));
  }
  for (size_t i = 0; i < tlistb.size(); i++) {
    const int tid = tlistb[i].track_id;
    if (stracks.find(tid) != stracks.end()) {
      stracks.erase(tid);
    }
  }
  std::vector<STrack> res;
  for (std::map<int, STrack>::iterator it = stracks.begin(); it != stracks.end(); ++it) {
    res.push_back(it->second);
  }
  return res;
}

void ByteTracker::remove_duplicate_stracks(std::vector<STrack> &resa, std::vector<STrack> &resb,
                                           std::vector<STrack> &stracksa,
                                           std::vector<STrack> &stracksb) {
  const std::vector<std::vector<float>> pdist = iou_distance(stracksa, stracksb);
  std::vector<std::pair<int, int> > pairs;
  for (size_t i = 0; i < pdist.size(); i++) {
    for (size_t j = 0; j < pdist[i].size(); j++) {
      if (pdist[i][j] < 0.15f) {
        pairs.push_back(std::pair<int, int>(static_cast<int>(i), static_cast<int>(j)));
      }
    }
  }
  std::vector<int> dupa;
  std::vector<int> dupb;
  for (size_t i = 0; i < pairs.size(); i++) {
    const int timep =
        stracksa[pairs[i].first].frame_id - stracksa[pairs[i].first].start_frame;
    const int timeq =
        stracksb[pairs[i].second].frame_id - stracksb[pairs[i].second].start_frame;
    if (timep > timeq) {
      dupb.push_back(pairs[i].second);
    } else {
      dupa.push_back(pairs[i].first);
    }
  }
  for (size_t i = 0; i < stracksa.size(); i++) {
    if (std::find(dupa.begin(), dupa.end(), static_cast<int>(i)) == dupa.end()) {
      resa.push_back(stracksa[i]);
    }
  }
  for (size_t i = 0; i < stracksb.size(); i++) {
    if (std::find(dupb.begin(), dupb.end(), static_cast<int>(i)) == dupb.end()) {
      resb.push_back(stracksb[i]);
    }
  }
}

void ByteTracker::linear_assignment(const std::vector<std::vector<float>> &cost_matrix,
                                    int cost_matrix_size, int cost_matrix_size_size, float thresh,
                                    std::vector<std::vector<int>> &matches,
                                    std::vector<int> &unmatched_a, std::vector<int> &unmatched_b) {
  matches.clear();
  unmatched_a.clear();
  unmatched_b.clear();
  if (cost_matrix.empty()) {
    for (int i = 0; i < cost_matrix_size; i++) {
      unmatched_a.push_back(i);
    }
    for (int i = 0; i < cost_matrix_size_size; i++) {
      unmatched_b.push_back(i);
    }
    return;
  }
  struct Edge {
    int i;
    int j;
    float c;
  };
  std::vector<Edge> edges;
  for (int i = 0; i < cost_matrix_size; i++) {
    for (int j = 0; j < cost_matrix_size_size; j++) {
      const float c = cost_matrix[static_cast<size_t>(i)][static_cast<size_t>(j)];
      if (c <= thresh) {
        Edge e;
        e.i = i;
        e.j = j;
        e.c = c;
        edges.push_back(e);
      }
    }
  }
  std::sort(edges.begin(), edges.end(),
            [](const Edge &a, const Edge &b) { return a.c < b.c; });
  std::vector<char> used_row(static_cast<size_t>(cost_matrix_size), 0);
  std::vector<char> used_col(static_cast<size_t>(cost_matrix_size_size), 0);
  for (size_t k = 0; k < edges.size(); k++) {
    const Edge &e = edges[k];
    if (used_row[static_cast<size_t>(e.i)] || used_col[static_cast<size_t>(e.j)]) {
      continue;
    }
    used_row[static_cast<size_t>(e.i)] = 1;
    used_col[static_cast<size_t>(e.j)] = 1;
    std::vector<int> m;
    m.push_back(e.i);
    m.push_back(e.j);
    matches.push_back(m);
  }
  for (int i = 0; i < cost_matrix_size; i++) {
    if (!used_row[static_cast<size_t>(i)]) {
      unmatched_a.push_back(i);
    }
  }
  for (int j = 0; j < cost_matrix_size_size; j++) {
    if (!used_col[static_cast<size_t>(j)]) {
      unmatched_b.push_back(j);
    }
  }
}

std::vector<std::vector<float>> ByteTracker::ious(const std::vector<std::vector<float>> &atlbrs,
                                                  const std::vector<std::vector<float>> &btlbrs) {
  std::vector<std::vector<float>> out;
  if (atlbrs.empty() || btlbrs.empty()) {
    return out;
  }
  out.resize(atlbrs.size());
  for (size_t n = 0; n < atlbrs.size(); n++) {
    out[n].resize(btlbrs.size());
  }
  for (size_t k = 0; k < btlbrs.size(); k++) {
    for (size_t n = 0; n < atlbrs.size(); n++) {
      out[n][k] = bbox_iou(atlbrs[n], btlbrs[k]);
    }
  }
  return out;
}

std::vector<std::vector<float>> ByteTracker::iou_distance(const std::vector<STrack *> &atracks,
                                                            const std::vector<STrack> &btracks,
                                                            int &dist_size, int &dist_size_size) {
  std::vector<std::vector<float>> cost_matrix;
  dist_size = static_cast<int>(atracks.size());
  dist_size_size = static_cast<int>(btracks.size());
  if (atracks.empty() || btracks.empty()) {
    return cost_matrix;
  }
  std::vector<std::vector<float>> atlbrs;
  std::vector<std::vector<float>> btlbrs;
  atlbrs.reserve(atracks.size());
  btlbrs.reserve(btracks.size());
  for (size_t i = 0; i < atracks.size(); i++) {
    atlbrs.push_back(atracks[i]->tlbr);
  }
  for (size_t i = 0; i < btracks.size(); i++) {
    btlbrs.push_back(btracks[i].tlbr);
  }
  const std::vector<std::vector<float>> iou_mat = ious(atlbrs, btlbrs);
  for (size_t i = 0; i < iou_mat.size(); i++) {
    std::vector<float> row;
    row.reserve(iou_mat[i].size());
    for (size_t j = 0; j < iou_mat[i].size(); j++) {
      row.push_back(1.0f - iou_mat[i][j]);
    }
    cost_matrix.push_back(row);
  }
  return cost_matrix;
}

std::vector<std::vector<float>> ByteTracker::iou_distance(const std::vector<STrack> &atracks,
                                                          const std::vector<STrack> &btracks) {
  std::vector<std::vector<float>> atlbrs;
  std::vector<std::vector<float>> btlbrs;
  for (size_t i = 0; i < atracks.size(); i++) {
    atlbrs.push_back(atracks[i].tlbr);
  }
  for (size_t i = 0; i < btracks.size(); i++) {
    btlbrs.push_back(btracks[i].tlbr);
  }
  const std::vector<std::vector<float>> iou_mat = ious(atlbrs, btlbrs);
  std::vector<std::vector<float>> cost_matrix;
  for (size_t i = 0; i < iou_mat.size(); i++) {
    std::vector<float> row;
    for (size_t j = 0; j < iou_mat[i].size(); j++) {
      row.push_back(1.0f - iou_mat[i][j]);
    }
    cost_matrix.push_back(row);
  }
  return cost_matrix;
}

std::vector<STrack> ByteTracker::update(const std::vector<ByteObject> &objects) {
  frame_id_++;
  std::vector<STrack> activated_stracks;
  std::vector<STrack> refind_stracks;
  std::vector<STrack> removed_stracks;
  std::vector<STrack> lost_stracks;
  std::vector<STrack> detections;
  std::vector<STrack> detections_low;
  std::vector<STrack> detections_cp;
  std::vector<STrack> tracked_stracks_swap;
  std::vector<STrack> resa;
  std::vector<STrack> resb;
  std::vector<STrack> output_stracks;
  std::vector<STrack *> unconfirmed;
  std::vector<STrack *> tracked_stracks;
  std::vector<STrack *> strack_pool;
  std::vector<STrack *> r_tracked_stracks;

  if (!objects.empty()) {
    for (size_t i = 0; i < objects.size(); i++) {
      std::vector<float> tlbr_(4);
      tlbr_[0] = objects[i].rect.x;
      tlbr_[1] = objects[i].rect.y;
      tlbr_[2] = objects[i].rect.x + objects[i].rect.width;
      tlbr_[3] = objects[i].rect.y + objects[i].rect.height;
      const float score = objects[i].prob;
      const int label = objects[i].label;
      std::vector<float> tlwh = STrack::tlbr_to_tlwh(tlbr_);
      STrack strack(tlwh, score, label);
      if (score >= track_thresh_) {
        detections.push_back(strack);
      } else {
        detections_low.push_back(strack);
      }
    }
  }

  for (size_t i = 0; i < tracked_stracks_.size(); i++) {
    if (!tracked_stracks_[i].is_activated) {
      unconfirmed.push_back(&tracked_stracks_[i]);
    } else {
      tracked_stracks.push_back(&tracked_stracks_[i]);
    }
  }

  strack_pool = joint_stracks(tracked_stracks, lost_stracks_);
  STrack::multi_predict(strack_pool, kalman_filter_);

  int dist_size = 0;
  int dist_size_size = 0;
  std::vector<std::vector<float>> dists =
      iou_distance(strack_pool, detections, dist_size, dist_size_size);
  std::vector<std::vector<int>> matches;
  std::vector<int> u_track;
  std::vector<int> u_detection;
  linear_assignment(dists, dist_size, dist_size_size, match_thresh_, matches, u_track, u_detection);

  for (size_t i = 0; i < matches.size(); i++) {
    STrack *track = strack_pool[static_cast<size_t>(matches[i][0])];
    STrack *det = &detections[static_cast<size_t>(matches[i][1])];
    if (track->state == static_cast<int>(TrackState::Tracked)) {
      track->update(*det, frame_id_);
      activated_stracks.push_back(*track);
    } else {
      track->re_activate(*det, frame_id_, false);
      refind_stracks.push_back(*track);
    }
  }

  for (size_t i = 0; i < u_detection.size(); i++) {
    detections_cp.push_back(detections[static_cast<size_t>(u_detection[i])]);
  }
  detections.clear();
  detections.assign(detections_low.begin(), detections_low.end());

  for (size_t i = 0; i < u_track.size(); i++) {
    if (strack_pool[static_cast<size_t>(u_track[i])]->state == static_cast<int>(TrackState::Tracked)) {
      r_tracked_stracks.push_back(strack_pool[static_cast<size_t>(u_track[i])]);
    }
  }

  dists.clear();
  dists = iou_distance(r_tracked_stracks, detections, dist_size, dist_size_size);
  matches.clear();
  u_track.clear();
  u_detection.clear();
  linear_assignment(dists, dist_size, dist_size_size, 0.5f, matches, u_track, u_detection);

  for (size_t i = 0; i < matches.size(); i++) {
    STrack *track = r_tracked_stracks[static_cast<size_t>(matches[i][0])];
    STrack *det = &detections[static_cast<size_t>(matches[i][1])];
    if (track->state == static_cast<int>(TrackState::Tracked)) {
      track->update(*det, frame_id_);
      activated_stracks.push_back(*track);
    } else {
      track->re_activate(*det, frame_id_, false);
      refind_stracks.push_back(*track);
    }
  }

  for (size_t i = 0; i < u_track.size(); i++) {
    STrack *track = r_tracked_stracks[static_cast<size_t>(u_track[i])];
    if (track->state != static_cast<int>(TrackState::Lost)) {
      track->mark_lost();
      lost_stracks.push_back(*track);
    }
  }

  detections.clear();
  detections.assign(detections_cp.begin(), detections_cp.end());

  dists.clear();
  dists = iou_distance(unconfirmed, detections, dist_size, dist_size_size);
  matches.clear();
  std::vector<int> u_unconfirmed;
  u_detection.clear();
  linear_assignment(dists, dist_size, dist_size_size, 0.7f, matches, u_unconfirmed, u_detection);

  for (size_t i = 0; i < matches.size(); i++) {
    unconfirmed[static_cast<size_t>(matches[i][0])]->update(
        detections[static_cast<size_t>(matches[i][1])], frame_id_);
    activated_stracks.push_back(*unconfirmed[static_cast<size_t>(matches[i][0])]);
  }

  for (size_t i = 0; i < u_unconfirmed.size(); i++) {
    STrack *track = unconfirmed[static_cast<size_t>(u_unconfirmed[i])];
    track->mark_removed();
    removed_stracks.push_back(*track);
  }

  for (size_t i = 0; i < u_detection.size(); i++) {
    STrack *track = &detections[static_cast<size_t>(u_detection[i])];
    if (track->score < high_thresh_) {
      continue;
    }
    track->activate(kalman_filter_, frame_id_);
    activated_stracks.push_back(*track);
  }

  for (size_t i = 0; i < lost_stracks_.size(); i++) {
    if (frame_id_ - lost_stracks_[i].end_frame() > max_time_lost_) {
      lost_stracks_[i].mark_removed();
      removed_stracks.push_back(lost_stracks_[i]);
    }
  }

  for (size_t i = 0; i < tracked_stracks_.size(); i++) {
    if (tracked_stracks_[i].state == static_cast<int>(TrackState::Tracked)) {
      tracked_stracks_swap.push_back(tracked_stracks_[i]);
    }
  }
  tracked_stracks_.clear();
  tracked_stracks_.assign(tracked_stracks_swap.begin(), tracked_stracks_swap.end());

  tracked_stracks_ = joint_stracks(tracked_stracks_, activated_stracks);
  tracked_stracks_ = joint_stracks(tracked_stracks_, refind_stracks);

  lost_stracks_ = sub_stracks(lost_stracks_, tracked_stracks_);
  for (size_t i = 0; i < lost_stracks.size(); i++) {
    lost_stracks_.push_back(lost_stracks[i]);
  }

  lost_stracks_ = sub_stracks(lost_stracks_, removed_stracks);
  for (size_t i = 0; i < removed_stracks.size(); i++) {
    removed_stracks_.push_back(removed_stracks[i]);
  }

  remove_duplicate_stracks(resa, resb, tracked_stracks_, lost_stracks_);

  tracked_stracks_.clear();
  tracked_stracks_.assign(resa.begin(), resa.end());
  lost_stracks_.clear();
  lost_stracks_.assign(resb.begin(), resb.end());

  for (size_t i = 0; i < tracked_stracks_.size(); i++) {
    if (tracked_stracks_[i].is_activated) {
      output_stracks.push_back(tracked_stracks_[i]);
    }
  }
  return output_stracks;
}
