//
// Created by ubuntu on 1/20/23.
//
#include "opencv2/opencv.hpp"
#include "yolov8.hpp"
#include <chrono>
#include <cstdlib>

namespace fs = ghc::filesystem;

const std::vector<std::string> CLASS_NAMES = {
    "person",         "bicycle",    "car",           "motorcycle",    "airplane",     "bus",           "train",
    "truck",          "boat",       "traffic light", "fire hydrant",  "stop sign",    "parking meter", "bench",
    "bird",           "cat",        "dog",           "horse",         "sheep",        "cow",           "elephant",
    "bear",           "zebra",      "giraffe",       "backpack",      "umbrella",     "handbag",       "tie",
    "suitcase",       "frisbee",    "skis",          "snowboard",     "sports ball",  "kite",          "baseball bat",
    "baseball glove", "skateboard", "surfboard",     "tennis racket", "bottle",       "wine glass",    "cup",
    "fork",           "knife",      "spoon",         "bowl",          "banana",       "apple",         "sandwich",
    "orange",         "broccoli",   "carrot",        "hot dog",       "pizza",        "donut",         "cake",
    "chair",          "couch",      "potted plant",  "bed",           "dining table", "toilet",        "tv",
    "laptop",         "mouse",      "remote",        "keyboard",      "cell phone",   "microwave",     "oven",
    "toaster",        "sink",       "refrigerator",  "book",          "clock",        "vase",          "scissors",
    "teddy bear",     "hair drier", "toothbrush"};

const std::vector<std::vector<unsigned int>> COLORS = {
    {0, 114, 189},   {217, 83, 25},   {237, 177, 32},  {126, 47, 142},  {119, 172, 48},  {77, 190, 238},
    {162, 20, 47},   {76, 76, 76},    {153, 153, 153}, {255, 0, 0},     {255, 128, 0},   {191, 191, 0},
    {0, 255, 0},     {0, 0, 255},     {170, 0, 255},   {85, 85, 0},     {85, 170, 0},    {85, 255, 0},
    {170, 85, 0},    {170, 170, 0},   {170, 255, 0},   {255, 85, 0},    {255, 170, 0},   {255, 255, 0},
    {0, 85, 128},    {0, 170, 128},   {0, 255, 128},   {85, 0, 128},    {85, 85, 128},   {85, 170, 128},
    {85, 255, 128},  {170, 0, 128},   {170, 85, 128},  {170, 170, 128}, {170, 255, 128}, {255, 0, 128},
    {255, 85, 128},  {255, 170, 128}, {255, 255, 128}, {0, 85, 255},    {0, 170, 255},   {0, 255, 255},
    {85, 0, 255},    {85, 85, 255},   {85, 170, 255},  {85, 255, 255},  {170, 0, 255},   {170, 85, 255},
    {170, 170, 255}, {170, 255, 255}, {255, 0, 255},   {255, 85, 255},  {255, 170, 255}, {85, 0, 0},
    {128, 0, 0},     {170, 0, 0},     {212, 0, 0},     {255, 0, 0},     {0, 43, 0},      {0, 85, 0},
    {0, 128, 0},     {0, 170, 0},     {0, 212, 0},     {0, 255, 0},     {0, 0, 43},      {0, 0, 85},
    {0, 0, 128},     {0, 0, 170},     {0, 0, 212},     {0, 0, 255},     {0, 0, 0},       {36, 36, 36},
    {73, 73, 73},    {109, 109, 109}, {146, 146, 146}, {182, 182, 182}, {219, 219, 219}, {0, 114, 189},
    {80, 183, 189},  {128, 128, 0}};

int main(int argc, char** argv)
{
    if (argc != 3) {
        fprintf(stderr, "Usage: %s [engine_path] [image_path/image_dir/video_path|camera]\n", argv[0]);
        return -1;
    }

    // cuda:0
    cudaSetDevice(0);

    const std::string engine_file_path{argv[1]};
    const std::string input_arg{argv[2]};
    const fs::path    path{input_arg};

    std::vector<std::string> imagePathList;
    bool                     isVideo{false};
    bool                     isCamera{input_arg == "camera"};

    auto yolov8 = new YOLOv8(engine_file_path);
    yolov8->make_pipe(true);

    if (isCamera) {
        isVideo = true;
    }
    else if (fs::exists(path)) {
        std::string suffix = path.extension();
        if (suffix == ".jpg" || suffix == ".jpeg" || suffix == ".png") {
            imagePathList.push_back(path);
        }
        else if (suffix == ".mp4" || suffix == ".avi" || suffix == ".m4v" || suffix == ".mpeg" || suffix == ".mov"
                 || suffix == ".mkv") {
            isVideo = true;
        }
        else {
            printf("suffix %s is wrong !!!\n", suffix.c_str());
            std::abort();
        }
    }
    else if (fs::is_directory(path)) {
        cv::glob(path.string() + "/*.jpg", imagePathList);
    }
    else {
        printf("input %s is invalid (use image/video path or \"camera\")\n", input_arg.c_str());
        return -1;
    }

    cv::Mat             res, image;
    cv::Size            size = cv::Size{640, 640};
    std::vector<Object> objs;
    bool                headless = std::getenv("DISPLAY") == nullptr;
    bool                profile_enabled = std::getenv("PIPELINE_PROFILE") != nullptr;
    int                 profile_every = 30;
    const char*         profile_every_env = std::getenv("PIPELINE_PROFILE_EVERY");
    if (profile_every_env != nullptr) {
        int n = std::atoi(profile_every_env);
        if (n > 0) profile_every = n;
    }
    int warmup_frames = 10;

    if (profile_enabled) {
        printf("[profile] enabled | warmup=%d | every=%d\n", warmup_frames, profile_every);
    }

    if (!headless) {
        cv::namedWindow("result", cv::WINDOW_AUTOSIZE);
    }

    if (isVideo) {
        cv::VideoCapture cap;
        if (isCamera) {
            cap.open(0, cv::CAP_V4L2);
            cap.set(cv::CAP_PROP_FOURCC, cv::VideoWriter::fourcc('M', 'J', 'P', 'G'));
            cap.set(cv::CAP_PROP_FRAME_WIDTH, 640);
            cap.set(cv::CAP_PROP_FRAME_HEIGHT, 480);
        }
        else {
            cap.open(path);
        }

        if (!cap.isOpened()) {
            if (isCamera) {
                printf("can not open camera 0 (V4L2)\n");
            }
            else {
                printf("can not open %s\n", path.c_str());
            }
            return -1;
        }

        double read_ms_sum = 0.0, preprocess_ms_sum = 0.0, infer_ms_sum = 0.0;
        double post_ms_sum = 0.0, draw_ms_sum = 0.0, total_ms_sum = 0.0;
        int    measured = 0;
        int    seen = 0;
        while (true) {
            auto total_t0 = std::chrono::steady_clock::now();
            auto t_read0 = std::chrono::steady_clock::now();
            if (!cap.read(image)) break;
            auto t_read1 = std::chrono::steady_clock::now();

            objs.clear();
            auto t_pre0 = std::chrono::steady_clock::now();
            yolov8->copy_from_Mat(image, size);
            auto t_pre1 = std::chrono::steady_clock::now();

            auto t_inf0 = std::chrono::steady_clock::now();
            yolov8->infer();
            auto t_inf1 = std::chrono::steady_clock::now();

            auto t_post0 = std::chrono::steady_clock::now();
            yolov8->postprocess(objs);
            auto t_post1 = std::chrono::steady_clock::now();

            auto t_draw0 = std::chrono::steady_clock::now();
            if (!headless) {
                yolov8->draw_objects(image, res, objs, CLASS_NAMES, COLORS);
            }
            auto t_draw1 = std::chrono::steady_clock::now();

            auto total_t1 = std::chrono::steady_clock::now();
            double infer_ms =
                (double)std::chrono::duration_cast<std::chrono::microseconds>(t_inf1 - t_inf0).count() / 1000.0;
            printf("cost %2.4lf ms\n", infer_ms);

            seen++;
            if (profile_enabled && seen > warmup_frames) {
                read_ms_sum +=
                    (double)std::chrono::duration_cast<std::chrono::microseconds>(t_read1 - t_read0).count() / 1000.0;
                preprocess_ms_sum +=
                    (double)std::chrono::duration_cast<std::chrono::microseconds>(t_pre1 - t_pre0).count() / 1000.0;
                infer_ms_sum +=
                    (double)std::chrono::duration_cast<std::chrono::microseconds>(t_inf1 - t_inf0).count() / 1000.0;
                post_ms_sum +=
                    (double)std::chrono::duration_cast<std::chrono::microseconds>(t_post1 - t_post0).count() / 1000.0;
                draw_ms_sum +=
                    (double)std::chrono::duration_cast<std::chrono::microseconds>(t_draw1 - t_draw0).count() / 1000.0;
                total_ms_sum +=
                    (double)std::chrono::duration_cast<std::chrono::microseconds>(total_t1 - total_t0).count() / 1000.0;
                measured++;
                if (measured % profile_every == 0) {
                    double inv = 1.0 / profile_every;
                    printf(
                        "[profile] avg over %d frames | read=%.3f ms | preprocess=%.3f ms | infer=%.3f ms | "
                        "postprocess=%.3f ms | draw=%.3f ms | total=%.3f ms\n",
                        profile_every, read_ms_sum * inv, preprocess_ms_sum * inv, infer_ms_sum * inv,
                        post_ms_sum * inv, draw_ms_sum * inv, total_ms_sum * inv);
                    read_ms_sum = preprocess_ms_sum = infer_ms_sum = 0.0;
                    post_ms_sum = draw_ms_sum = total_ms_sum = 0.0;
                }
            }

            if (!headless) {
                cv::imshow("result", res);
                if (cv::waitKey(10) == 'q') break;
            }
        }
    }
    else {
        for (auto& p : imagePathList) {
            objs.clear();
            image = cv::imread(p);
            yolov8->copy_from_Mat(image, size);
            auto start = std::chrono::system_clock::now();
            yolov8->infer();
            auto end = std::chrono::system_clock::now();
            yolov8->postprocess(objs);
            yolov8->draw_objects(image, res, objs, CLASS_NAMES, COLORS);
            auto tc = (double)std::chrono::duration_cast<std::chrono::microseconds>(end - start).count() / 1000.;
            printf("cost %2.4lf ms\n", tc);
            if (!headless) {
                cv::imshow("result", res);
                cv::waitKey(0);
            }
        }
    }
    if (!headless) {
        cv::destroyAllWindows();
    }
    delete yolov8;
    return 0;
}
