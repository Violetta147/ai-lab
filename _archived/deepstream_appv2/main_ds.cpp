#include <gst/gst.h>
#include <glib.h>
#include <stdio.h>

/* 
   PHIÊN BẢN SIÊU TỐI GIẢN (MINIMALIST)
   Không cần DeepStream SDK Headers (.h)
   Chỉ cần GStreamer (Luôn có sẵn trong Docker Samples)
*/

static gboolean bus_call(GstBus *bus, GstMessage *msg, gpointer data) {
    GMainLoop *loop = (GMainLoop *)data;
    switch (GST_MESSAGE_TYPE(msg)) {
        case GST_MESSAGE_EOS:
            g_print("End of stream\n");
            g_main_loop_quit(loop);
            break;
        case GST_MESSAGE_ERROR: {
            gchar *debug; GError *error;
            gst_message_parse_error(msg, &error, &debug);
            g_printerr("ERROR: %s\n", error->message);
            g_free(debug); g_error_free(error);
            g_main_loop_quit(loop);
            break;
        }
        default: break;
    }
    return TRUE;
}

int main(int argc, char *argv[]) {
    GMainLoop *loop = NULL;
    GstElement *pipeline, *source, *streammux, *pgie, *tracker, *analytics, *nvvidconv, *osd, *sink;
    GstBus *bus;
    guint bus_watch_id;

    gst_init(&argc, &argv);
    loop = g_main_loop_new(NULL, FALSE);

    pipeline = gst_pipeline_new("minimal-pipeline");

    /* Khởi tạo các thành phần bằng Factory (Không cần Header) */
    source = gst_element_factory_make("v4l2src", "src");
    streammux = gst_element_factory_make("nvstreammux", "muxer");
    pgie = gst_element_factory_make("nvinfer", "gie");
    tracker = gst_element_factory_make("nvtracker", "tracker");
    analytics = gst_element_factory_make("nvdsanalytics", "analytics");
    nvvidconv = gst_element_factory_make("nvvideoconvert", "conv");
    osd = gst_element_factory_make("nvdsosd", "osd");
    sink = gst_element_factory_make("fakesink", "sink");

    if (!pipeline || !source || !pgie || !sink) {
        g_printerr("Không thể tạo Plugin! Hãy kiểm tra trong Docker bằng lệnh: gst-inspect-1.0 nvinfer\n");
        if (!pgie) g_printerr("LỖI: nvinfer không khởi tạo được!\n");
        return -1;
    }

    /* Cấu hình qua GObject (Không cần SDK) */
    g_object_set(G_OBJECT(source), "device", "/dev/video0", NULL);
    g_object_set(G_OBJECT(streammux), "width", 1280, "height", 720, "batch-size", 1, "batched-push-timeout", 40000, NULL);
    g_object_set(G_OBJECT(pgie), "config-file-path", "config_infer_primary_yolov8.txt", NULL);
    g_object_set(G_OBJECT(tracker), "ll-lib-file", "/opt/nvidia/deepstream/deepstream/lib/libnvds_nvdcf.so", "ll-config-file", "tracker_config.txt", NULL);
    g_object_set(G_OBJECT(analytics), "config-file", "config_nvdsanalytics.txt", NULL);

    bus = gst_pipeline_get_bus(GST_PIPELINE(pipeline));
    bus_watch_id = gst_bus_add_watch(bus, bus_call, loop);
    gst_object_unref(bus);

    /* Link các thành phần */
    gst_bin_add_many(GST_BIN(pipeline), source, streammux, pgie, tracker, analytics, nvvidconv, osd, sink, NULL);

    /* Link đặc biệt cho streammux */
    GstPad *sinkpad = gst_element_get_request_pad(streammux, "sink_0");
    GstPad *srcpad = gst_element_get_static_pad(source, "src");
    gst_pad_link(srcpad, sinkpad);
    gst_object_unref(sinkpad);
    gst_object_unref(srcpad);

    gst_element_link_many(streammux, pgie, tracker, analytics, nvvidconv, osd, sink, NULL);

    g_print("Đang khởi chạy Pipeline...\n");
    gst_element_set_state(pipeline, GST_STATE_PLAYING);
    g_main_loop_run(loop);

    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(GST_OBJECT(pipeline));
    g_source_remove(bus_watch_id);
    g_main_loop_unref(loop);
    return 0;
}
