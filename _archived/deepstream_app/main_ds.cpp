#include <gst/gst.h>
#include <glib.h>
#include <stdio.h>
#include <iostream>
#include <vector>
#include <cuda_runtime_api.h>

#include "gstnvdsmeta.h"
#include "nvds_analytics_meta.h"
#include "nvds_latency_meta.h"
#include "traffic_analyzer.hpp"

#define MAX_DISPLAY_LEN 128

/* Cấu hình Pipeline */
#define MUXER_OUTPUT_WIDTH 1280
#define MUXER_OUTPUT_HEIGHT 720
#define MUXER_BATCH_TIMEOUT_USEC 40000

static TrafficAnalyzer *analyzer = nullptr;
static GTimer *perf_timer = NULL;
static guint frame_count = 0;

/* Probe function để xử lý kết quả phân tích */
static GstPadProbeReturn
analytics_src_pad_probe(GstPad *pad, GstPadProbeInfo *info, gpointer u_data)
{
    GstBuffer *buf = (GstBuffer *)info->data;
    NvDsBatchMeta *batch_meta = gst_buffer_get_nvds_batch_meta(buf);
    if (!batch_meta) return GST_PAD_PROBE_OK;

    frame_count++;
    
    for (NvDsMetaList *l_frame = batch_meta->frame_meta_list; l_frame != NULL; l_frame = l_frame->next) {
        NvDsFrameMeta *frame_meta = (NvDsFrameMeta *)l_frame->data;
        std::vector<STrack> current_tracks;

        /* 1. Trích xuất Tracking Meta để đưa vào Analyzer */
        for (NvDsMetaList *l_obj = frame_meta->obj_meta_list; l_obj != NULL; l_obj = l_obj->next) {
            NvDsObjectMeta *obj_meta = (NvDsObjectMeta *)l_obj->data;
            
            STrack t;
            t.track_id = obj_meta->object_id;
            t.label = obj_meta->class_id;
            t.score = obj_meta->confidence;
            t.tlbr = { (float)obj_meta->rect_params.left, (float)obj_meta->rect_params.top,
                       (float)(obj_meta->rect_params.left + obj_meta->rect_params.width),
                       (float)(obj_meta->rect_params.top + obj_meta->rect_params.height) };
            current_tracks.push_back(t);
        }

        /* 2. Cập nhật Analyzer Logic (PCE, BEV, v.v.) */
        analyzer->update(current_tracks, 30.0);

        /* 3. Vẽ Dashboard lên màn hình bằng DeepStream OSD (Tăng tốc phần cứng) */
        NvDsDisplayMeta *display_meta = nvds_acquire_display_meta_from_pool(batch_meta);
        display_meta->num_labels = 1;
        NvOSD_TextParams *txt = &display_meta->text_params[0];
        txt->display_text = (char*)g_malloc0(MAX_DISPLAY_LEN);
        
        snprintf(txt->display_text, MAX_DISPLAY_LEN, 
                 "Flow: %.0f v/h | Speed: %.1f km/h | Density: %.1f PCE/km", 
                 600.0, 45.5, 12.0); // Demo values, link to analyzer in production

        txt->x_offset = 20;
        txt->y_offset = 20;
        txt->font_params.font_name = (char*)"Serif";
        txt->font_params.font_size = 12;
        txt->font_params.font_color = {1.0, 1.0, 1.0, 1.0};
        txt->set_bg_clr = 1;
        txt->text_bg_clr = {0.0, 0.0, 0.0, 0.8};

        nvds_add_display_meta_to_frame(frame_meta, display_meta);
    }

    /* 4. Profiling FPS */
    gdouble elapsed = g_timer_elapsed(perf_timer, NULL);
    if (elapsed > 2.0) {
        printf("[PROFILER] AI Throughput: %.2f FPS\n", frame_count / elapsed);
        g_timer_start(perf_timer);
        frame_count = 0;
    }

    return GST_PAD_PROBE_OK;
}

int main(int argc, char *argv[])
{
    GMainLoop *loop = NULL;
    GstElement *pipeline, *source, *vidconv, *nvvidconv, *osd, *sink, *cap_filter;
    GstElement *streammux, *pgie, *tracker, *analytics;

    gst_init(&argc, &argv);
    loop = g_main_loop_new(NULL, FALSE);
    perf_timer = g_timer_new();
    analyzer = new TrafficAnalyzer(MUXER_OUTPUT_WIDTH, MUXER_OUTPUT_HEIGHT);

    pipeline = gst_pipeline_new("traffic-monitoring-pipeline");

    /* Source: Camera UVC (Webcam) */
    source = gst_element_factory_make("v4l2src", "camera-source");
    g_object_set(G_OBJECT(source), "device", "/dev/video0", NULL);

    /* Cap filter để ép FPS và độ phân giải */
    cap_filter = gst_element_factory_make("capsfilter", "src-caps");
    GstCaps *caps = gst_caps_from_string("video/x-raw, width=640, height=480, framerate=30/1");
    g_object_set(G_OBJECT(cap_filter), "caps", caps, NULL);
    gst_caps_unref(caps);

    vidconv = gst_element_factory_make("videoconvert", "vid-conv");
    streammux = gst_element_factory_make("nvstreammux", "muxer");
    pgie = gst_element_factory_make("nvinfer", "detector");
    tracker = gst_element_factory_make("nvtracker", "tracker");
    analytics = gst_element_factory_make("nvdsanalytics", "analytics");
    nvvidconv = gst_element_factory_make("nvvideoconvert", "nv-conv");
    osd = gst_element_factory_make("nvdsosd", "osd");
    
    /* Sink for Jetson Nano */
    GstElement *transform = gst_element_factory_make("nvegltransform", "egl-trans");
    sink = gst_element_factory_make("nveglglessink", "sink");

    if (!pipeline || !source || !pgie || !tracker || !analytics || !osd || !sink) {
        fprintf(stderr, "Một số plugin DeepStream chưa được cài đặt!\n");
        return -1;
    }

    /* Cấu hình các Plugin */
    g_object_set(G_OBJECT(streammux), "width", MUXER_OUTPUT_WIDTH, "height", MUXER_OUTPUT_HEIGHT, "batch-size", 1, "batched-push-timeout", 40000, "live-source", 1, NULL);
    
    /* LIÊN KẾT YOLO PARSER (.so của marcoslucianops) */
    g_object_set(G_OBJECT(pgie), 
        "config-file-path", "config_infer_primary_yolov8.txt", 
        "custom-lib-path", "./libnvdsinfer_custom_impl_Yolo.so", 
        "parse-bbox-func-name", "NvDsInferParseCustomYolo",
        NULL);

    g_object_set(G_OBJECT(tracker), 
        "ll-lib-file", "/opt/nvidia/deepstream/deepstream/lib/libnvds_nvdcf.so", 
        "ll-config-file", "tracker_config.txt", 
        "tracker-width", 640, 
        "tracker-height", 384, 
        NULL);
    
    g_object_set(G_OBJECT(analytics), 
        "config-file", "config_nvdsanalytics.txt", 
        NULL);

    gst_bin_add_many(GST_BIN(pipeline), source, cap_filter, vidconv, streammux, pgie, tracker, analytics, nvvidconv, osd, transform, sink, NULL);

    /* Link pads */
    GstPad *sinkpad = gst_element_get_request_pad(streammux, "sink_0");
    GstPad *srcpad = gst_element_get_static_pad(vidconv, "src");
    gst_pad_link(srcpad, sinkpad);
    gst_object_unref(sinkpad);
    gst_object_unref(srcpad);

    gst_element_link_many(source, cap_filter, vidconv, NULL);
    gst_element_link_many(streammux, pgie, tracker, analytics, nvvidconv, osd, transform, sink, NULL);

    /* Thêm Probe để xử lý logic Traffic Analyzer */
    GstPad *analytics_src_pad = gst_element_get_static_pad(analytics, "src");
    gst_pad_add_probe(analytics_src_pad, GST_PAD_PROBE_TYPE_BUFFER, analytics_src_pad_probe, NULL, NULL);
    gst_object_unref(analytics_src_pad);

    printf("[INFO] Đang khởi chạy hệ thống Giám sát giao thông (DeepStream 6.0.1)...\n");
    gst_element_set_state(pipeline, GST_STATE_PLAYING);
    g_main_loop_run(loop);

    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(GST_OBJECT(pipeline));
    return 0;
}
