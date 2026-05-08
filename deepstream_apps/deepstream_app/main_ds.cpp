#include <gst/gst.h>
#include <glib.h>
#include <stdio.h>

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
            g_printerr("GStreamer Error: %s\n", error->message);
            if (debug) g_printerr("Debug details: %s\n", debug);
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
    GstElement *pipeline, *source, *nvvidconv, *caps_filter, *streammux, *pgie, *sink;
    GstBus *bus;
    guint bus_watch_id;

    gst_init(&argc, &argv);
    loop = g_main_loop_new(NULL, FALSE);

    pipeline = gst_pipeline_new("minimal-pipeline");

    source = gst_element_factory_make("v4l2src", "src");
    nvvidconv = gst_element_factory_make("nvvideoconvert", "nvconv");
    caps_filter = gst_element_factory_make("capsfilter", "filter");
    streammux = gst_element_factory_make("nvstreammux", "muxer");
    pgie = gst_element_factory_make("nvinfer", "gie");
    sink = gst_element_factory_make("fakesink", "sink");

    if (!pipeline || !source || !nvvidconv || !caps_filter || !streammux || !pgie || !sink) {
        g_printerr("ERROR: Failed to create one or more elements\n");
        return -1;
    }

    /* Configuration */
    g_object_set(G_OBJECT(source), "device", "/dev/video0", NULL);
    
    /* Set Caps to force NV12 in hardware memory (NVMM) */
    GstCaps *caps = gst_caps_from_string("video/x-raw(memory:NVMM), format=NV12, width=640, height=480, framerate=30/1");
    g_object_set(G_OBJECT(caps_filter), "caps", caps, NULL);
    gst_caps_unref(caps);

    g_object_set(G_OBJECT(streammux), "width", 1280, "height", 720, "batch-size", 1, "batched-push-timeout", 40000, "live-source", 1, NULL);
    g_object_set(G_OBJECT(pgie), "config-file-path", "config_infer_primary_yolov8.txt", NULL);

    bus = gst_pipeline_get_bus(GST_PIPELINE(pipeline));
    bus_watch_id = gst_bus_add_watch(bus, bus_call, loop);
    gst_object_unref(bus);

    /* Build the pipeline: source -> nvvidconv -> caps_filter -> muxer -> pgie -> sink */
    gst_bin_add_many(GST_BIN(pipeline), source, nvvidconv, caps_filter, streammux, pgie, sink, NULL);

    if (!gst_element_link(source, nvvidconv)) {
        g_printerr("ERROR: Failed to link source to nvvidconv\n");
        return -1;
    }
    if (!gst_element_link(nvvidconv, caps_filter)) {
        g_printerr("ERROR: Failed to link nvvidconv to caps_filter\n");
        return -1;
    }

    GstPad *sinkpad = gst_element_get_request_pad(streammux, "sink_0");
    GstPad *srcpad = gst_element_get_static_pad(caps_filter, "src");
    if (!sinkpad || !srcpad || gst_pad_link(srcpad, sinkpad) != GST_PAD_LINK_OK) {
        g_printerr("ERROR: Failed to link filter to muxer\n");
        return -1;
    }
    gst_object_unref(sinkpad);
    gst_object_unref(srcpad);

    if (!gst_element_link_many(streammux, pgie, sink, NULL)) {
        g_printerr("ERROR: Failed to link remaining elements\n");
        return -1;
    }

    g_print("Running Pipeline (NVMM-Accelerated)...\n");
    gst_element_set_state(pipeline, GST_STATE_PLAYING);
    g_main_loop_run(loop);

    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(GST_OBJECT(pipeline));
    g_source_remove(bus_watch_id);
    g_main_loop_unref(loop);
    return 0;
}
