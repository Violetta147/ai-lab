#include "bt_strack.hpp"

#include <algorithm>
#include <cstdio>

STrack::STrack(const std::vector<float> &tlwh_, float score, int label_)
    : is_activated(false),
      track_id(0),
      state(static_cast<int>(TrackState::New)),
      label(label_),
      frame_id(0),
      tracklet_len(0),
      start_frame(0),
      score(score) {
  _tlwh.resize(4);
  _tlwh.assign(tlwh_.begin(), tlwh_.end());
  tlwh.resize(4);
  tlbr.resize(4);
  static_tlwh();
  static_tlbr();
}

std::vector<float> STrack::tlbr_to_tlwh(std::vector<float> &tlbr) {
  tlbr[2] -= tlbr[0];
  tlbr[3] -= tlbr[1];
  return tlbr;
}

void STrack::multi_predict(std::vector<STrack *> &stracks,
                           byte_kalman::KalmanFilter &kalman_filter) {
  for (size_t i = 0; i < stracks.size(); i++) {
    if (stracks[i]->state != static_cast<int>(TrackState::Tracked)) {
      stracks[i]->mean(7) = 0.0f;
    }
    kalman_filter.predict(stracks[i]->mean, stracks[i]->covariance);
    stracks[i]->static_tlwh();
    stracks[i]->static_tlbr();
  }
}

void STrack::activate(byte_kalman::KalmanFilter &kalman_filter, int frame_id_in) {
  this->kalman_filter_ = kalman_filter;
  this->track_id = STrack::next_id();

  std::vector<float> _tlwh_tmp(4);
  _tlwh_tmp[0] = this->_tlwh[0];
  _tlwh_tmp[1] = this->_tlwh[1];
  _tlwh_tmp[2] = this->_tlwh[2];
  _tlwh_tmp[3] = this->_tlwh[3];
  std::vector<float> xyah = tlwh_to_xyah(_tlwh_tmp);
  DETECTBOX xyah_box;
  xyah_box(0) = xyah[0];
  xyah_box(1) = xyah[1];
  xyah_box(2) = xyah[2];
  xyah_box(3) = xyah[3];
  auto mc = this->kalman_filter_.initiate(xyah_box);
  this->mean = mc.first;
  this->covariance = mc.second;

  static_tlwh();
  static_tlbr();

  this->tracklet_len = 0;
  this->state = static_cast<int>(TrackState::Tracked);
  if (frame_id_in == 1) {
    this->is_activated = true;
  }
  this->frame_id = frame_id_in;
  this->start_frame = frame_id_in;
}

void STrack::re_activate(STrack &new_track, int frame_id_in, bool new_id) {
  std::vector<float> xyah = tlwh_to_xyah(new_track.tlwh);
  DETECTBOX xyah_box;
  xyah_box(0) = xyah[0];
  xyah_box(1) = xyah[1];
  xyah_box(2) = xyah[2];
  xyah_box(3) = xyah[3];
  auto mc = this->kalman_filter_.update(this->mean, this->covariance, xyah_box);
  this->mean = mc.first;
  this->covariance = mc.second;

  static_tlwh();
  static_tlbr();

  this->tracklet_len = 0;
  this->state = static_cast<int>(TrackState::Tracked);
  this->is_activated = true;
  this->frame_id = frame_id_in;
  this->score = new_track.score;
  this->label = new_track.label;
  if (new_id) {
    this->track_id = STrack::next_id();
  }
}

void STrack::update(STrack &new_track, int frame_id_in) {
  this->frame_id = frame_id_in;
  this->tracklet_len++;
  std::vector<float> xyah = tlwh_to_xyah(new_track.tlwh);
  DETECTBOX xyah_box;
  xyah_box(0) = xyah[0];
  xyah_box(1) = xyah[1];
  xyah_box(2) = xyah[2];
  xyah_box(3) = xyah[3];

  auto mc = this->kalman_filter_.update(this->mean, this->covariance, xyah_box);
  this->mean = mc.first;
  this->covariance = mc.second;

  static_tlwh();
  static_tlbr();

  this->state = static_cast<int>(TrackState::Tracked);
  this->is_activated = true;
  this->score = new_track.score;
  this->label = new_track.label;
}

void STrack::static_tlwh() {
  if (this->state == static_cast<int>(TrackState::New)) {
    tlwh[0] = _tlwh[0];
    tlwh[1] = _tlwh[1];
    tlwh[2] = _tlwh[2];
    tlwh[3] = _tlwh[3];
    return;
  }

  tlwh[0] = mean(0);
  tlwh[1] = mean(1);
  tlwh[2] = mean(2);
  tlwh[3] = mean(3);
  tlwh[2] *= tlwh[3];
  tlwh[0] -= tlwh[2] / 2.0f;
  tlwh[1] -= tlwh[3] / 2.0f;
}

void STrack::static_tlbr() {
  tlbr.clear();
  tlbr.assign(tlwh.begin(), tlwh.end());
  tlbr[2] += tlbr[0];
  tlbr[3] += tlbr[1];
}

std::vector<float> STrack::tlwh_to_xyah(const std::vector<float> &tlwh_tmp) {
  std::vector<float> out = tlwh_tmp;
  out[0] += out[2] / 2.0f;
  out[1] += out[3] / 2.0f;
  out[2] /= out[3];
  return out;
}

void STrack::mark_lost() { state = static_cast<int>(TrackState::Lost); }

void STrack::mark_removed() { state = static_cast<int>(TrackState::Removed); }

int STrack::next_id() {
  static int count = 0;
  count++;
  return count;
}

int STrack::end_frame() const { return this->frame_id; }
