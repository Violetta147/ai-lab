/*
 * nvmsgconv_c2 — payload builder template.
 *
 * This file is intentionally SDK-friendly but still self-contained enough to
 * show the exact JSON shape the backend expects. In a real DeepStream build,
 * replace the placeholder extraction in `build_payload_from_meta()` with code
 * that reads NvDsFrameMeta / NvDsObjectMeta and fills the JSON fields.
 */

#include "c2_payload.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    const char *stream_id;
    unsigned long long frame_id;
    double timestamp;
} c2_frame_info_t;

typedef struct {
    int tracking_id;
    int class_id;
    const char *class_name;
    int x;
    int y;
    int w;
    int h;
    double confidence;
} c2_object_t;

static char *dup_json(const char *text, int *payload_len) {
    size_t len = strlen(text);
    char *out = (char *)malloc(len + 1);
    if (!out) {
        return NULL;
    }
    memcpy(out, text, len + 1);
    if (payload_len) {
        *payload_len = (int)len;
    }
    return out;
}

static int build_payload_from_meta(const c2_frame_info_t *frame,
                                   const c2_object_t *objects,
                                   size_t object_count,
                                   char **payload,
                                   int *payload_len) {
    if (!frame || !payload || !payload_len) {
        return -1;
    }

    char buffer[8192];
    int written = snprintf(
        buffer,
        sizeof(buffer),
        "{"
        "\"stream_id\":\"%s\","
        "\"frame_id\":%llu,"
        "\"timestamp\":\"%.3f\","
        "\"objects\":[",
        frame->stream_id ? frame->stream_id : "unknown",
        frame->frame_id,
        frame->timestamp);
    if (written < 0 || (size_t)written >= sizeof(buffer)) {
        return -1;
    }

    size_t offset = (size_t)written;
    for (size_t i = 0; i < object_count; ++i) {
        const c2_object_t *obj = &objects[i];
        int n = snprintf(
            buffer + offset,
            sizeof(buffer) - offset,
            "%s{"
            "\"tracking_id\":%d,"
            "\"class_id\":%d,"
            "\"class_name\":\"%s\","
            "\"bbox\":{\"x\":%d,\"y\":%d,\"w\":%d,\"h\":%d},"
            "\"confidence\":%.4f"
            "}",
            (i == 0) ? "" : ",",
            obj->tracking_id,
            obj->class_id,
            obj->class_name ? obj->class_name : "unknown",
            obj->x,
            obj->y,
            obj->w,
            obj->h,
            obj->confidence);
        if (n < 0 || (size_t)n >= sizeof(buffer) - offset) {
            return -1;
        }
        offset += (size_t)n;
    }

    int tail = snprintf(buffer + offset, sizeof(buffer) - offset, "]}");
    if (tail < 0 || (size_t)tail >= sizeof(buffer) - offset) {
        return -1;
    }

    return (*payload = dup_json(buffer, payload_len)) ? 0 : -1;
}

int nvds_msg2p_init(void **userdata) {
    *userdata = NULL;
    return 0;
}

void nvds_msg2p_deinit(void *userdata) {
    (void)userdata;
}

int nvds_msg2p_generate(void *userdata, const char *input_meta, char **payload, int *payload_len) {
    (void)userdata;
    (void)input_meta;

    /*
     * Placeholder values to prove the expected schema. In the real DeepStream
     * integration, parse `input_meta` / frame metadata and fill these structs.
     */
    c2_frame_info_t frame = {
        .stream_id = "cam_8554",
        .frame_id = 1,
        .timestamp = 0.000,
    };

    c2_object_t objects[1] = {
        {
            .tracking_id = 45,
            .class_id = 0,
            .class_name = "car",
            .x = 100,
            .y = 200,
            .w = 150,
            .h = 80,
            .confidence = 0.8900,
        },
    };

    return build_payload_from_meta(&frame, objects, 1, payload, payload_len);
}
