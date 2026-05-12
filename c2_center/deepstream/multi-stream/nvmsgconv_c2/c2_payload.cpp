#include <iostream>
#include <string>
#include <glib.h>
#include <json-glib/json-glib.h>
#include "nvds_msgapi.h"
#include "nvdsmeta_schema.h"
#include "c2_payload.h"

extern "C" {

/**
 * Called when the library is loaded. 
 * Creates a context for the message conversion.
 */
NvDsMsg2pCtx* nvds_msg2p_ctx_create(const gchar *file, NvDsPayloadType type) {
    NvDsMsg2pCtx *ctx = (NvDsMsg2pCtx *) g_malloc0(sizeof(NvDsMsg2pCtx));
    ctx->sensorId = 0;
    return ctx;
}

/**
 * Called when the library is unloaded.
 */
void nvds_msg2p_ctx_destroy(NvDsMsg2pCtx *ctx) {
    g_free(ctx);
}

#include "nvdsmeta.h"

// DeepStream 6.0 New API internal struct
typedef struct {
  void *objMeta;
  void *frameMeta;
  gchar *mediaType;
} NvDsMsg2pMetaInfo;

/**
 * Helper to generate the common C2 JSON structure
 */
static NvDsPayload* generate_json_payload(NvDsMsg2pCtx *ctx, int classId, int trackingId, int streamId, unsigned int frameNum, double timestamp, NvOSD_RectParams *rect) {
    JsonBuilder *builder = json_builder_new();
    json_builder_begin_object(builder);

    json_builder_set_member_name(builder, "message_type");
    json_builder_add_string_value(builder, "c2_event");

    json_builder_set_member_name(builder, "stream_id");
    json_builder_add_string_value(builder, std::to_string(streamId).c_str());

    json_builder_set_member_name(builder, "timestamp");
    json_builder_add_double_value(builder, timestamp);

    json_builder_set_member_name(builder, "frame_num");
    json_builder_add_int_value(builder, (int)frameNum);

    // Objects array for backend consistency
    json_builder_set_member_name(builder, "objects");
    json_builder_begin_array(builder);
    json_builder_begin_object(builder);

    json_builder_set_member_name(builder, "class_id");
    json_builder_add_int_value(builder, classId);

    json_builder_set_member_name(builder, "tracking_id");
    json_builder_add_int_value(builder, trackingId);

    if (rect) {
        json_builder_set_member_name(builder, "bbox");
        json_builder_begin_array(builder);
        json_builder_add_double_value(builder, rect->left);
        json_builder_add_double_value(builder, rect->top);
        json_builder_add_double_value(builder, rect->left + rect->width);
        json_builder_add_double_value(builder, rect->top + rect->height);
        json_builder_end_array(builder);
    }

    json_builder_end_object(builder);
    json_builder_end_array(builder);

    json_builder_end_object(builder);

    JsonGenerator *gen = json_generator_new();
    JsonNode *root = json_builder_get_root(builder);
    json_generator_set_root(gen, root);

    gsize length;
    gchar *json_str = json_generator_to_data(gen, &length);

    // DEBUG: Uncomment for payload inspection
    //g_print("[C2-DEBUG] Generated Payload (%d bytes): %s\n", (int)length, json_str);

    NvDsPayload *payload = (NvDsPayload *) g_malloc0(sizeof(NvDsPayload));
    payload->payload = json_str;
    payload->payloadSize = (int)length;

    g_object_unref(gen);
    g_object_unref(builder);

    return payload;
}

/**
 * The core logic: converts DeepStream event metadata into a custom JSON string.
 */
NvDsPayload* nvds_msg2p_generate(NvDsMsg2pCtx *ctx, NvDsEventMsgMeta *meta) {
    return generate_json_payload(ctx, meta->objClassId, (int)meta->trackingId, meta->sensorId, 0, 0, NULL);
}

/**
 * NEW API: Called when msg-conv-msg2p-new-api=1 is set.
 */
NvDsPayload* nvds_msg2p_generate_new(NvDsMsg2pCtx *ctx, void *metadataInfo) {
    NvDsMsg2pMetaInfo *info = (NvDsMsg2pMetaInfo *)metadataInfo;
    NvDsObjectMeta *objMeta = (NvDsObjectMeta *)info->objMeta;
    NvDsFrameMeta *frameMeta = (NvDsFrameMeta *)info->frameMeta;

    if (objMeta && frameMeta) {
        double ts = (double)frameMeta->ntp_timestamp / 1e9;
        if (ts <= 0) {
            // Fallback to system clock if NTP timestamp is not set
            GDateTime *now = g_date_time_new_now_local();
            ts = (double)g_date_time_to_unix(now);
            g_date_time_unref(now);
        }
        return generate_json_payload(ctx, 
            objMeta->class_id, 
            (int)objMeta->object_id, 
            (int)frameMeta->source_id, 
            frameMeta->frame_num,
            ts,
            &objMeta->rect_params);
    }
    return NULL;
}

/**
 * Called after the payload has been sent to release memory.
 */
void nvds_msg2p_release(NvDsMsg2pCtx *ctx, NvDsPayload *payload) {
    if (payload) {
        if (payload->payload) g_free(payload->payload);
        g_free(payload);
    }
}

} // extern "C"
