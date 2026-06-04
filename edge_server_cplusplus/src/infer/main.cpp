
#include <opencv2/opencv.hpp>
#include <chrono>
#include <atomic>
#include <condition_variable>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <thread>

#include "cpm.hpp"
#include "infer.hpp"
#include "yolo.hpp"

using namespace std;

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


static bool streq(const char *a, const char *b) { return a && b && strcmp(a, b) == 0; }

static bool env_flag_enabled(const char *name, bool default_value) {
  const char *value = std::getenv(name);
  if (value == nullptr || *value == '\0') return default_value;
  return streq(value, "1") || streq(value, "true") || streq(value, "TRUE") || streq(value, "on") ||
         streq(value, "ON") || streq(value, "yes") || streq(value, "YES");
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

static void camera_inference(int device_id = 0) {
  const bool pipeline_profile_enabled = env_flag_enabled("PIPELINE_PROFILE", true);
  const int pipeline_profile_every = 30;
  const char *display_env = std::getenv("DISPLAY");
  const bool headless_mode = display_env == nullptr || *display_env == '\0';
  printf("[camera] start device_id=%d\n", device_id);
  cv::VideoCapture cap(device_id, cv::CAP_V4L2);
  cap.set(cv::CAP_PROP_FRAME_WIDTH, 640);
  cap.set(cv::CAP_PROP_FRAME_HEIGHT, 480);
  cap.set(cv::CAP_PROP_FOURCC, cv::VideoWriter::fourcc('M', 'J', 'P', 'G'));
  cap.set(cv::CAP_PROP_FPS, 30);
  if (!cap.isOpened()) {
    printf("Failed to open camera: %d\n", device_id);
    return;
  }

  const char *engine_path = std::getenv("PIPELINE_ENGINE");
  if (engine_path == nullptr || *engine_path == '\0') {
    engine_path = "yolov8n.transd.engine";
  }
  printf("[infer] Using engine: %s\n", engine_path);
  printf("[camera] opened=%d width=%.0f height=%.0f fps=%.2f\n", cap.isOpened(),
         cap.get(cv::CAP_PROP_FRAME_WIDTH), cap.get(cv::CAP_PROP_FRAME_HEIGHT),
         cap.get(cv::CAP_PROP_FPS));
  printf("[camera] headless_mode=%d (set FORWARD_DISPLAY=1 to show window)\n", headless_mode);
  auto yolo = yolo::load(engine_path, yolo::Type::V8);
  if (yolo == nullptr) return;

  printf("[camera] PIPELINE_PROFILE=%d print_every=%d\n", pipeline_profile_enabled,
         pipeline_profile_every);
  std::mutex frame_mutex;
  std::condition_variable frame_cv;
  cv::Mat latest_frame;
  cv::Mat latest_rendered;
  uint64_t latest_frame_id = 0;
  std::atomic<bool> stop{false};
  std::atomic<uint64_t> capture_count{0};
  std::atomic<uint64_t> infer_count{0};
  std::atomic<int> last_det_count{0};
  std::atomic<double> capture_ms_avg{0.0};
  std::atomic<double> infer_ms_avg{0.0};
  std::atomic<double> draw_ms_avg{0.0};

  std::thread capture_thread([&]() {
    while (!stop.load()) {
      trt::Timer cap_timer;
      cap_timer.start();
      cv::Mat frame;
      if (!cap.read(frame) || frame.empty()) {
        printf("[camera] empty frame\n");
        continue;
      }
      const float cap_ms = cap_timer.stop("", false);
      {
        std::lock_guard<std::mutex> lock(frame_mutex);
        latest_frame = frame;
        latest_frame_id++;
      }
      capture_count.fetch_add(1);
      capture_ms_avg.store(cap_ms);
      frame_cv.notify_one();
    }
  });

  std::thread infer_thread([&]() {
    uint64_t consumed_frame_id = 0;
    int profile_count = 0;
    double profile_capture_ms_sum = 0.0;
    double profile_forward_ms_sum = 0.0;
    double profile_draw_ms_sum = 0.0;

    while (!stop.load()) {
      cv::Mat frame_ref;
      uint64_t frame_id = 0;
      {
        std::unique_lock<std::mutex> lock(frame_mutex);
        frame_cv.wait(lock, [&]() { return stop.load() || latest_frame_id > consumed_frame_id; });
        if (stop.load()) break;
        frame_ref = latest_frame;
        frame_id = latest_frame_id;
      }

      cv::Mat frame = frame_ref.clone();
      trt::Timer infer_timer;
      infer_timer.start();
      auto objs = yolo->forward(cvimg(frame));
      const float forward_ms = infer_timer.stop("", false);

      trt::Timer draw_timer;
      draw_timer.start();
      draw_boxes(frame, objs);
      const float draw_ms = draw_timer.stop("", false);

      {
        std::lock_guard<std::mutex> lock(frame_mutex);
        latest_rendered = frame;
      }

      consumed_frame_id = frame_id;
      infer_count.fetch_add(1);
      last_det_count.store(static_cast<int>(objs.size()));
      infer_ms_avg.store(forward_ms);
      draw_ms_avg.store(draw_ms);

      if (pipeline_profile_enabled) {
        profile_count++;
        profile_capture_ms_sum += capture_ms_avg.load();
        profile_forward_ms_sum += forward_ms;
        profile_draw_ms_sum += draw_ms;
        if (profile_count % pipeline_profile_every == 0) {
          const double inv = 1.0 / static_cast<double>(pipeline_profile_every);
          printf("[PIPELINE_PROFILE] every=%d capture=%.3fms forward=%.3fms draw=%.3fms\n",
                 pipeline_profile_every, profile_capture_ms_sum * inv, profile_forward_ms_sum * inv,
                 profile_draw_ms_sum * inv);
          profile_capture_ms_sum = 0.0;
          profile_forward_ms_sum = 0.0;
          profile_draw_ms_sum = 0.0;
        }
      }
    }
  });

  uint64_t prev_capture = 0;
  uint64_t prev_infer = 0;
  auto t0 = std::chrono::steady_clock::now();
  while (!stop.load()) {
    if (!headless_mode) {
      cv::Mat render;
      {
        std::lock_guard<std::mutex> lock(frame_mutex);
        render = latest_rendered.clone();
      }
      if (!render.empty()) cv::imshow("YOLOv8 Camera", render);
      if (cv::waitKey(1) == 'q') {
        stop.store(true);
        frame_cv.notify_all();
        break;
      }
    } else {
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    auto now = std::chrono::steady_clock::now();
    auto elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(now - t0).count();
    if (elapsed_ms >= 1000) {
      const uint64_t cap_now = capture_count.load();
      const uint64_t inf_now = infer_count.load();
      const uint64_t cap_delta = cap_now - prev_capture;
      const uint64_t inf_delta = inf_now - prev_infer;
      const float cap_fps = cap_delta * 1000.0f / static_cast<float>(elapsed_ms);
      const float inf_fps = inf_delta * 1000.0f / static_cast<float>(elapsed_ms);
      printf(
          "[camera] capture_fps=%.4f infer_fps=%.4f capture_ms=%.3f infer_ms=%.3f draw_ms=%.3f "
          "detections=%d\n",
          cap_fps, inf_fps, capture_ms_avg.load(), infer_ms_avg.load(), draw_ms_avg.load(),
          last_det_count.load());
      prev_capture = cap_now;
      prev_infer = inf_now;
      t0 = now;
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
  std::vector<cv::Mat> images{cv::imread("inference/car.jpg"), cv::imread("inference/gril.jpg"),
                              cv::imread("inference/group.jpg")};

  for (int i = images.size(); i < batch; ++i) images.push_back(images[i % 3]);

  cpm::Instance<yolo::BoxArray, yolo::Image, yolo::Infer> cpmi;
  bool ok = cpmi.start([] { return yolo::load("yolov8n.transd.engine", yolo::Type::V8); },
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
  std::vector<cv::Mat> images{cv::imread("inference/car.jpg"), cv::imread("inference/gril.jpg"),
                              cv::imread("inference/group.jpg")};
  auto yolo = yolo::load("yolov8n.transd.engine", yolo::Type::V8);
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
  cv::Mat image = cv::imread("inference/car.jpg");
  auto yolo = yolo::load("yolov8n-seg.b1.transd.engine", yolo::Type::V8Seg);
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
