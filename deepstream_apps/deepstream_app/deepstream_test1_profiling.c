/*
 * Tích hợp Profiling vào deepstream-test1
 */

#include <gst/gst.h>
#include <glib.h>
#include <stdio.h>
#include <cuda_runtime_api.h>
#include "gstnvdsmeta.h"
#include "nvds_latency_meta.h"

#define MAX_DISPLAY_LEN 64
#define PGIE_CLASS_ID_VEHICLE 0
#define PGIE_CLASS_ID_PERSON 2
#define MUXER_OUTPUT_WIDTH 1920
#define MUXER_OUTPUT_HEIGHT 1080
#define MUXER_BATCH_TIMEOUT_USEC 40000

/* Profiling variables */
static GTimer *fps_timer = NULL;
static guint fps_frame_count = 0;
static NvDsLatencyInfo *latency_info = NULL;

gint frame_number = 0;

static GstPadProbeReturn
osd_sink_pad_buffer_probe (GstPad * pad, GstPadProbeInfo * info,
    gpointer u_data)
{
    GstBuffer *buf = (GstBuffer *) info->data;
    NvDsBatchMeta *batch_meta = gst_buffer_get_nvds_batch_meta (buf);
    
    /* 1. FPS Profiling */
    if (!fps_timer) {
        fps_timer = g_timer_new();
    }
    fps_frame_count++;
    gdouble elapsed = g_timer_elapsed(fps_timer, NULL);
    if (elapsed > 2.0) {
        g_print ("\n[PROFILER] Current FPS: %.2f\n", fps_frame_count / elapsed);
        g_timer_start(fps_timer);
        fps_frame_count = 0;
    }

    /* 2. Latency Profiling (DeepStream Native) */
    if (!latency_info) {
        latency_info = (NvDsLatencyInfo *) g_malloc0 (sizeof (NvDsLatencyInfo) * 10);
    }
    guint num_sources_in_batch = nvds_measure_buffer_latency(buf, latency_info);
    if (num_sources_in_batch > 0) {
        g_print ("[PROFILER] Frame Latency: %.2f ms (Source: %d)\n", 
                 latency_info[0].latency, latency_info[0].source_id);
    }

    /* Original Metadata logic */
    guint vehicle_count = 0;
    guint person_count = 0;
    NvDsMetaList * l_frame = NULL;
    NvDsMetaList * l_obj = NULL;

    for (l_frame = batch_meta->frame_meta_list; l_frame != NULL;
      l_frame = l_frame->next) {
        NvDsFrameMeta *frame_meta = (NvDsFrameMeta *) (l_frame->data);
        for (l_obj = frame_meta->obj_meta_list; l_obj != NULL;
                l_obj = l_obj->next) {
            NvDsObjectMeta *obj_meta = (NvDsObjectMeta *) (l_obj->data);
            if (obj_meta->class_id == PGIE_CLASS_ID_VEHICLE) vehicle_count++;
            if (obj_meta->class_id == PGIE_CLASS_ID_PERSON) person_count++;
        }
    }

    g_print ("Frame %d | Objects: %d | Vehicles: %d | Persons: %d\r",
            frame_number, vehicle_count + person_count, vehicle_count, person_count);
    fflush(stdout);
    frame_number++;
    return GST_PAD_PROBE_OK;
}

static gboolean
bus_call (GstBus * bus, GstMessage * msg, gpointer data)
{
  GMainLoop *loop = (GMainLoop *) data;
  switch (GST_MESSAGE_TYPE (msg)) {
    case GST_MESSAGE_EOS:
      g_print ("\nEnd of stream\n");
      g_main_loop_quit (loop);
      break;
    case GST_MESSAGE_ERROR:{
      gchar *debug;
      GError *error;
      gst_message_parse_error (msg, &error, &debug);
      g_printerr ("\nERROR from element %s: %s\n",
          GST_OBJECT_NAME (msg->src), error->message);
      if (debug) g_printerr ("Error details: %s\n", debug);
      g_free (debug); g_error_free (error);
      g_main_loop_quit (loop);
      break;
    }
    default:
      break;
  }
  return TRUE;
}

int
main (int argc, char *argv[])
{
  GMainLoop *loop = NULL;
  GstElement *pipeline = NULL, *source = NULL, *h264parser = NULL,
      *decoder = NULL, *streammux = NULL, *sink = NULL, *pgie = NULL, *nvvidconv = NULL,
      *nvosd = NULL, *transform = NULL;
  GstBus *bus = NULL;
  guint bus_watch_id;
  GstPad *osd_sink_pad = NULL;

  if (argc != 2) {
    g_printerr ("Usage: %s <H264 filename>\n", argv[0]);
    return -1;
  }

  /* Khởi tạo GStreamer */
  gst_init (&argc, &argv);
  loop = g_main_loop_new (NULL, FALSE);

  pipeline = gst_pipeline_new ("profiling-pipeline");
  source = gst_element_factory_make ("filesrc", "file-source");
  h264parser = gst_element_factory_make ("h264parse", "h264-parser");
  decoder = gst_element_factory_make ("nvv4l2decoder", "nvv4l2-decoder");
  streammux = gst_element_factory_make ("nvstreammux", "stream-muxer");
  pgie = gst_element_factory_make ("nvinfer", "primary-nvinference-engine");
  nvvidconv = gst_element_factory_make ("nvvideoconvert", "nvvideo-converter");
  nvosd = gst_element_factory_make ("nvdsosd", "nv-onscreendisplay");
  
  /* Cấu hình cho Jetson Nano */
  transform = gst_element_factory_make ("nvegltransform", "nvegl-transform");
  sink = gst_element_factory_make ("nveglglessink", "nvvideo-renderer");

  if (!pipeline || !source || !h264parser || !decoder || !streammux || !pgie || !nvvidconv || !nvosd || !sink || !transform) {
    g_printerr ("Failed to create elements. Exiting.\n");
    return -1;
  }

  g_object_set (G_OBJECT (source), "location", argv[1], NULL);
  g_object_set (G_OBJECT (streammux), "batch-size", 1, "width", 1280, "height", 720, "batched-push-timeout", 40000, NULL);
  g_object_set (G_OBJECT (pgie), "config-file-path", "dstest1_pgie_config.txt", NULL);

  bus = gst_pipeline_get_bus (GST_PIPELINE (pipeline));
  bus_watch_id = gst_bus_add_watch (bus, bus_call, loop);
  gst_object_unref (bus);

  gst_bin_add_many (GST_BIN (pipeline), source, h264parser, decoder, streammux, pgie, nvvidconv, nvosd, transform, sink, NULL);

  /* Link decoder to streammux */
  GstPad *sinkpad = gst_element_get_request_pad (streammux, "sink_0");
  GstPad *srcpad = gst_element_get_static_pad (decoder, "src");
  gst_pad_link (srcpad, sinkpad);
  gst_object_unref (sinkpad);
  gst_object_unref (srcpad);

  gst_element_link_many (source, h264parser, decoder, NULL);
  gst_element_link_many (streammux, pgie, nvvidconv, nvosd, transform, sink, NULL);

  /* Add OSD probe for profiling */
  osd_sink_pad = gst_element_get_static_pad (nvosd, "sink");
  gst_pad_add_probe (osd_sink_pad, GST_PAD_PROBE_TYPE_BUFFER, osd_sink_pad_buffer_probe, NULL, NULL);
  gst_object_unref (osd_sink_pad);

  g_print ("\n[INFO] Bắt đầu chạy pipeline với Profiling...\n");
  g_print ("[HINT] Để xem độ trễ từng plugin, hãy chạy lệnh:\n");
  g_print ("       export NVDS_ENABLE_COMPONENT_LATENCY_MEASUREMENT=1\n\n");
  
  gst_element_set_state (pipeline, GST_STATE_PLAYING);
  g_main_loop_run (loop);

  gst_element_set_state (pipeline, GST_STATE_NULL);
  gst_object_unref (GST_OBJECT (pipeline));
  g_source_remove (bus_watch_id);
  g_main_loop_unref (loop);
  if (fps_timer) g_timer_destroy(fps_timer);
  if (latency_info) g_free(latency_info);
  
  return 0;
}
