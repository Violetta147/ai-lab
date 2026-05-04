
#include <opencv2/opencv.hpp>
#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <thread>
#include <unistd.h>

#include "bt_byte_tracker.hpp"
#include "cpm.hpp"
#include "infer.hpp"
#include "yolo.hpp"

using namespace std;

static bool streq(const char *a, const char *b) { return a && b && strcmp(a, b) == 0; }
static bool env_profile_enabled(const char *name) {
  const char *v = std::getenv(name);
  if (v == nullptr || *v == '\0') return false;
  return !(strcmp(v, "0") == 0 || strcmp(v, "false") == 0 || strcmp(v, "False") == 0 ||
           strcmp(v, "FALSE") == 0);
}

static bool byte_track_enabled() {
  const char *v = std::getenv("BYTETRACK");
  if (v == nullptr || *v == '\0') {
    return true;
  }
  return !(strcmp(v, "0") == 0 || strcmp(v, "false") == 0 || strcmp(v, "False") == 0 ||
           strcmp(v, "FALSE") == 0);
}

static const char *cocolabels[] = {"person",        "bicycle",      "car",
                                   "motorcycle",    "airplane",     "bus",
                                   "train",         "truck",        "boat",
                                   "traffic light", "fire hydrant", "stop sign",
                                   "parking meter", "bench",        "bird",
                                   "cat",           "dog",          "horse",
                                   "sheep",         "cow",          "elephant",
                                   "bear",          "zebra",        "giraffe",
                                   "backpack",      "umbrella",     "handbag",
                                   "tie",           "suitcase",     "frisbee",
                                   "skis",          "snowboard",    "sports ball",
                                   "kite",          "baseball bat", "baseball glove",
                                   "skateboard",    "surfboard",    "tennis racket",
                                   "bottle",        "wine glass",   "cup",
                                   "fork",          "knife",        "spoon",
                                   "bowl",          "banana",       "apple",
                                   "sandwich",      "orange",       "broccoli",
                                   "carrot",        "hot dog",      "pizza",
                                   "donut",         "cake",         "chair",
                                   "couch",         "potted plant", "bed",
                                   "dining table",  "toilet",       "tv",
                                   "laptop",        "mouse",        "remote",
                                   "keyboard",      "cell phone",   "microwave",
                                   "oven",          "toaster",      "sink",
                                   "refrigerator",  "book",         "clock",
                                   "vase",          "scissors",     "teddy bear",
                                   "hair drier",    "toothbrush"};

yolo::Image cvimg(const cv::Mat &image) { return yolo::Image(image.data, image.cols, image.rows); }

// Many UVC webcams (e.g. Logitech C270) default exposure_auto_priority=1: prefer exposure quality
// over sustaining requested FPS — real capture often becomes ~15 fps. v4l2-ctl fixes that.
static void camera_try_uvc_frame_rate_priority(int device_id) {
  const char *skip = std::getenv("CAMERA_SKIP_EXPOSURE_PRIORITY_FIX");
  if (skip != nullptr && (strcmp(skip, "1") == 0 || strcmp(skip, "true") == 0 ||
                          strcmp(skip, "True") == 0)) {
    printf("[camera] CAMERA_SKIP_EXPOSURE_PRIORITY_FIX set, not calling v4l2-ctl\n");
    return;
  }
  char path[64];
  snprintf(path, sizeof(path), "/dev/video%d", device_id);
  if (access(path, F_OK) != 0) {
    printf("[camera] %s missing, skip v4l2 exposure_auto_priority fix\n", path);
    return;
  }
  char cmd[192];
  snprintf(cmd, sizeof(cmd), "v4l2-ctl -d %s -c exposure_auto_priority=0 >/dev/null 2>&1", path);
  const int r = std::system(cmd);
  if (r == 0) {
    printf("[camera] v4l2: exposure_auto_priority=0 (prefer steady FPS over long auto exposure)\n");
  } else {
    printf(
        "[camera] v4l2-ctl exposure_auto_priority failed (status=%d). Install v4l-utils or ignore.\n",
        r);
  }
}

static void draw_boxes(cv::Mat &image, const yolo::BoxArray &objs) {
  for (auto &obj : objs) {
    uint8_t b, g, r;
    tie(b, g, r) = yolo::random_color(obj.class_label);
    cv::rectangle(image, cv::Point(obj.left, obj.top), cv::Point(obj.right, obj.bottom),
                  cv::Scalar(b, g, r), 2);

    auto name = cocolabels[obj.class_label];
    auto caption = cv::format("%s %.2f", name, obj.confidence);
    int width = cv::getTextSize(caption, 0, 0.6, 1, nullptr).width + 8;
    cv::rectangle(image, cv::Point(obj.left - 2, obj.top - 22),
                  cv::Point(obj.left + width, obj.top), cv::Scalar(b, g, r), -1);
    cv::putText(image, caption, cv::Point(obj.left, obj.top - 5), 0, 0.6,
                cv::Scalar::all(0), 1, 16);
  }
}

static void draw_tracked_boxes(cv::Mat &image, const std::vector<STrack> &tracks) {
  for (size_t ti = 0; ti < tracks.size(); ti++) {
    const STrack &t = tracks[ti];
    if (t.tlbr.size() < 4) {
      printf("[bytetrack] draw_tracked_boxes: skip track %d (bad tlbr)\n", t.track_id);
      continue;
    }
    const int left = static_cast<int>(t.tlbr[0]);
    const int top = static_cast<int>(t.tlbr[1]);
    const int right = static_cast<int>(t.tlbr[2]);
    const int bottom = static_cast<int>(t.tlbr[3]);
    uint8_t b, g, r;
    tie(b, g, r) = yolo::random_color(t.track_id);
    cv::rectangle(image, cv::Point(left, top), cv::Point(right, bottom), cv::Scalar(b, g, r), 2);
    const int li = std::max(0, std::min(t.label, 79));
    const char *name = cocolabels[li];
    auto caption = cv::format("%s id=%d %.2f", name, t.track_id, t.score);
    int width = cv::getTextSize(caption, 0, 0.6, 1, nullptr).width + 8;
    cv::rectangle(image, cv::Point(left - 2, top - 22), cv::Point(left + width, top),
                  cv::Scalar(b, g, r), -1);
    cv::putText(image, caption, cv::Point(left, top - 5), 0, 0.6, cv::Scalar::all(0), 1, 16);
  }
}

static void camera_inference(int device_id = 0) {
  bool headless = std::getenv("DISPLAY") == nullptr;
  cv::VideoCapture cap(device_id, cv::CAP_V4L2);
  cap.set(cv::CAP_PROP_FRAME_WIDTH, 640);
  cap.set(cv::CAP_PROP_FRAME_HEIGHT, 480);
  cap.set(cv::CAP_PROP_FOURCC, cv::VideoWriter::fourcc('M', 'J', 'P', 'G'));
  cap.set(cv::CAP_PROP_FPS, 30);
  if (!cap.isOpened()) {
    printf("Failed to open camera: %d\n", device_id);
    return;
  }
  camera_try_uvc_frame_rate_priority(device_id);
  {
    cv::Mat w;
    for (int i = 0; i < 4; i++) {
      cap.read(w);
    }
  }
  cap.set(cv::CAP_PROP_FPS, 30);
  printf("[camera] CAP_PROP_FPS get=%.2f size=%.0fx%.0f fourcc=%.0f\n", cap.get(cv::CAP_PROP_FPS),
         cap.get(cv::CAP_PROP_FRAME_WIDTH), cap.get(cv::CAP_PROP_FRAME_HEIGHT),
         cap.get(cv::CAP_PROP_FOURCC));

  const char* engine_path = std::getenv("PIPELINE_ENGINE");
  if (engine_path == nullptr || strlen(engine_path) == 0) {
    engine_path = "workspace/yolov8n.transd.engine";
  }
  printf("[infer] Using engine: %s\n", engine_path);
  auto yolo = yolo::load(engine_path, yolo::Type::V8);
  if (yolo == nullptr) return;

  std::atomic<bool> stop{false};
  std::mutex frame_mtx;
  std::condition_variable frame_cv;
  cv::Mat latest_frame;
  uint64_t latest_seq = 0;

  std::mutex render_mtx;
  cv::Mat latest_render;
  uint64_t latest_render_seq = 0;

  std::atomic<int> captured_frames_sec{0};
  std::atomic<int> infer_frames_sec{0};
  std::mutex stats_mtx;
  double read_ms_acc = 0.0;
  int read_count = 0;
  double infer_ms_acc = 0.0;
  double draw_ms_acc = 0.0;
  int infer_count = 0;
  const int warmup_frames = 10;
  std::atomic<int> infer_seen{0};
  double capture_fps = 0.0;
  double infer_fps = 0.0;
  double infer_ms = 0.0;
  double capture_wait_ms = 0.0;
  double draw_ms = 0.0;
  auto report_last = chrono::steady_clock::now();
  bool pipeline_profile = env_profile_enabled("PIPELINE_PROFILE");
  if (pipeline_profile) {
    printf("[profile] PIPELINE_PROFILE enabled. Set YOLO_PROFILE=1 for internal breakdown.\n");
  }
  const bool use_byte_track = byte_track_enabled();
  if (use_byte_track) {
    printf("[bytetrack] ByteTrack enabled (set BYTETRACK=0 to disable).\n");
  } else {
    printf("[bytetrack] ByteTrack disabled (raw detector boxes).\n");
  }
  ByteTracker byte_tracker(30, 30);

  std::thread capture_thread([&]() {
    while (!stop.load()) {
      cv::Mat frame;
      auto read_t0 = chrono::steady_clock::now();
      if (!cap.read(frame) || frame.empty()) continue;
      auto read_t1 = chrono::steady_clock::now();
      double read_cost =
          chrono::duration_cast<chrono::microseconds>(read_t1 - read_t0).count() / 1000.0;
      {
        std::lock_guard<std::mutex> lk(frame_mtx);
        latest_frame = frame;
        latest_seq++;
      }
      frame_cv.notify_one();
      captured_frames_sec.fetch_add(1);
      if (latest_seq > (uint64_t)warmup_frames) {
        std::lock_guard<std::mutex> slk(stats_mtx);
        read_ms_acc += read_cost;
        read_count++;
      }
    }
  });

  std::thread infer_thread([&]() {
    uint64_t consumed_seq = 0;
    while (!stop.load()) {
      cv::Mat frame_ref;
      {
        std::unique_lock<std::mutex> lk(frame_mtx);
        frame_cv.wait(lk, [&]() { return stop.load() || latest_seq > consumed_seq; });
        if (stop.load()) break;
        frame_ref = latest_frame;
        consumed_seq = latest_seq;
      }
      cv::Mat frame = frame_ref.clone();
      auto infer_t0 = chrono::steady_clock::now();
      auto objs = yolo->forward(cvimg(frame));
      auto infer_t1 = chrono::steady_clock::now();
      double infer_cost =
          chrono::duration_cast<chrono::microseconds>(infer_t1 - infer_t0).count() / 1000.0;

      auto draw_t0 = chrono::steady_clock::now();
      if (use_byte_track) {
        std::vector<ByteObject> det_inputs;
        det_inputs.reserve(objs.size());
        for (size_t oi = 0; oi < objs.size(); oi++) {
          const yolo::Box &obj = objs[oi];
          ByteObject bo;
          bo.rect =
              cv::Rect_<float>(obj.left, obj.top, obj.right - obj.left, obj.bottom - obj.top);
          bo.label = obj.class_label;
          bo.prob = obj.confidence;
          det_inputs.push_back(bo);
        }
        std::vector<STrack> tracks = byte_tracker.update(det_inputs);
        draw_tracked_boxes(frame, tracks);
      } else {
        draw_boxes(frame, objs);
      }
      auto draw_t1 = chrono::steady_clock::now();
      double draw_cost =
          chrono::duration_cast<chrono::microseconds>(draw_t1 - draw_t0).count() / 1000.0;

      int seen = infer_seen.fetch_add(1) + 1;
      if (seen > warmup_frames) {
        std::lock_guard<std::mutex> slk(stats_mtx);
        infer_ms_acc += infer_cost;
        draw_ms_acc += draw_cost;
        infer_count++;
      }
      infer_frames_sec.fetch_add(1);
      {
        std::lock_guard<std::mutex> lk(render_mtx);
        latest_render = frame;
        latest_render_seq = consumed_seq;
      }
    }
  });

  uint64_t shown_seq = 0;
  while (!stop.load()) {
    auto now = chrono::steady_clock::now();
    auto elapsed_ms = chrono::duration_cast<chrono::milliseconds>(now - report_last).count();
    if (elapsed_ms >= 1000) {
      int cam_count = captured_frames_sec.exchange(0);
      int inf_count = infer_frames_sec.exchange(0);
      capture_fps = cam_count * 1000.0 / elapsed_ms;
      infer_fps = inf_count * 1000.0 / elapsed_ms;
      int infer_samples = 0;
      int read_samples = 0;
      double infer_sum = 0.0;
      double read_sum = 0.0;
      double draw_sum = 0.0;
      {
        std::lock_guard<std::mutex> slk(stats_mtx);
        infer_samples = infer_count;
        read_samples = read_count;
        infer_sum = infer_ms_acc;
        read_sum = read_ms_acc;
        draw_sum = draw_ms_acc;
        infer_count = 0;
        read_count = 0;
        infer_ms_acc = 0.0;
        read_ms_acc = 0.0;
        draw_ms_acc = 0.0;
      }
      infer_ms = infer_samples > 0 ? (infer_sum / infer_samples) : 0.0;
      capture_wait_ms = read_samples > 0 ? (read_sum / read_samples) : 0.0;
      draw_ms = infer_samples > 0 ? (draw_sum / infer_samples) : 0.0;

      if (pipeline_profile) {
        printf(
            "Capture FPS: %.2f | Infer(E2E) FPS: %.2f | capture_wait=%.3f ms | infer=%.3f ms | "
            "draw=%.3f ms\n",
            capture_fps, infer_fps, capture_wait_ms, infer_ms, draw_ms);
      } else {
        printf("Capture FPS: %.2f | Infer(E2E) FPS: %.2f | Infer avg: %.3f ms\n", capture_fps,
               infer_fps, infer_ms);
      }
      report_last = now;
    }

    cv::Mat render;
    {
      std::lock_guard<std::mutex> lk(render_mtx);
      if (latest_render_seq > shown_seq) {
        render = latest_render.clone();
        shown_seq = latest_render_seq;
      }
    }

    if (!render.empty()) {
      cv::putText(render, cv::format("Capture FPS: %.2f", capture_fps), cv::Point(20, 40), 0, 0.8,
                  cv::Scalar(0, 255, 0), 2);
      cv::putText(render, cv::format("Infer FPS: %.2f", infer_fps), cv::Point(20, 75), 0, 0.8,
                  cv::Scalar(0, 255, 255), 2);
      cv::putText(render, cv::format("Infer: %.3f ms", infer_ms), cv::Point(20, 110), 0, 0.8,
                  cv::Scalar(255, 255, 0), 2);
      if (headless) {
        if ((shown_seq % 100) == 0) cv::imwrite("output_headless.jpg", render);
      } else {
        cv::imshow("YOLOv8 Camera", render);
      }
    }

    if (!headless && cv::waitKey(1) == 'q') {
      stop.store(true);
      frame_cv.notify_all();
      break;
    }
    if (headless) {
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
  }

  stop.store(true);
  frame_cv.notify_all();
  if (capture_thread.joinable()) capture_thread.join();
  if (infer_thread.joinable()) infer_thread.join();
}

void perf() {
  int max_infer_batch = 16;
  int batch = 16;
  std::vector<cv::Mat> images{cv::imread("workspace/inference/car.jpg"),
                              cv::imread("workspace/inference/gril.jpg"),
                              cv::imread("workspace/inference/group.jpg")};

  for (int i = images.size(); i < batch; ++i) images.push_back(images[i % 3]);

  cpm::Instance<yolo::BoxArray, yolo::Image, yolo::Infer> cpmi;
  bool ok = cpmi.start(
      [] { return yolo::load("workspace/yolov8n.transd.engine", yolo::Type::V8); },
                       max_infer_batch);

  if (!ok) return;

  std::vector<yolo::Image> yoloimages(images.size());
  std::transform(images.begin(), images.end(), yoloimages.begin(), cvimg);

  trt::Timer timer;
  for (int i = 0; i < 5; ++i) {
    timer.start();
    cpmi.commits(yoloimages).back().get();
    timer.stop("BATCH16");
  }

  for (int i = 0; i < 5; ++i) {
    timer.start();
    cpmi.commit(yoloimages[0]).get();
    timer.stop("BATCH1");
  }
}

void batch_inference() {
  std::vector<cv::Mat> images{cv::imread("workspace/inference/car.jpg"),
                              cv::imread("workspace/inference/gril.jpg"),
                              cv::imread("workspace/inference/group.jpg")};
  auto yolo = yolo::load("workspace/yolov8n.transd.engine", yolo::Type::V8);
  if (yolo == nullptr) return;

  std::vector<yolo::Image> yoloimages(images.size());
  std::transform(images.begin(), images.end(), yoloimages.begin(), cvimg);
  auto batched_result = yolo->forwards(yoloimages);
  for (int ib = 0; ib < (int)batched_result.size(); ++ib) {
    auto &objs = batched_result[ib];
    auto &image = images[ib];
    for (auto &obj : objs) {
      uint8_t b, g, r;
      tie(b, g, r) = yolo::random_color(obj.class_label);
      cv::rectangle(image, cv::Point(obj.left, obj.top), cv::Point(obj.right, obj.bottom),
                    cv::Scalar(b, g, r), 5);

      auto name = cocolabels[obj.class_label];
      auto caption = cv::format("%s %.2f", name, obj.confidence);
      int width = cv::getTextSize(caption, 0, 1, 2, nullptr).width + 10;
      cv::rectangle(image, cv::Point(obj.left - 3, obj.top - 33),
                    cv::Point(obj.left + width, obj.top), cv::Scalar(b, g, r), -1);
      cv::putText(image, caption, cv::Point(obj.left, obj.top - 5), 0, 1, cv::Scalar::all(0), 2,
                  16);
    }
    printf("Save result to Result.jpg, %d objects\n", (int)objs.size());
    cv::imwrite(cv::format("Result%d.jpg", ib), image);
  }
}

void single_inference() {
  cv::Mat image = cv::imread("workspace/inference/car.jpg");
  auto yolo = yolo::load("workspace/yolov8n-seg.b1.transd.engine", yolo::Type::V8Seg);
  if (yolo == nullptr) return;

  auto objs = yolo->forward(cvimg(image));
  int i = 0;
  for (auto &obj : objs) {
    uint8_t b, g, r;
    tie(b, g, r) = yolo::random_color(obj.class_label);
    cv::rectangle(image, cv::Point(obj.left, obj.top), cv::Point(obj.right, obj.bottom),
                  cv::Scalar(b, g, r), 5);

    auto name = cocolabels[obj.class_label];
    auto caption = cv::format("%s %.2f", name, obj.confidence);
    int width = cv::getTextSize(caption, 0, 1, 2, nullptr).width + 10;
    cv::rectangle(image, cv::Point(obj.left - 3, obj.top - 33),
                  cv::Point(obj.left + width, obj.top), cv::Scalar(b, g, r), -1);
    cv::putText(image, caption, cv::Point(obj.left, obj.top - 5), 0, 1, cv::Scalar::all(0), 2, 16);

    if (obj.seg) {
      cv::imwrite(cv::format("%d_mask.jpg", i),
                  cv::Mat(obj.seg->height, obj.seg->width, CV_8U, obj.seg->data));
      i++;
    }
  }

  printf("Save result to Result.jpg, %d objects\n", (int)objs.size());
  cv::imwrite("Result.jpg", image);
}

int main(int argc, char **argv) {
  if (argc > 1 && streq(argv[1], "camera")) {
    camera_inference(0);
    return 0;
  }

  perf();
  batch_inference();
  single_inference();
  return 0;
}