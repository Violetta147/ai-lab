#pragma once

/*
 * nvmsgconv_c2 — payload builder header (template)
 * Implement `nvds_msg2p_t` compatible functions here.
 * This file is a template; build instructions are in the Makefile.
 */

#include <stdint.h>
#include <glib.h>
#include "nvds_msgapi.h"

#ifdef __cplusplus
extern "C" {
#endif

// ABI requirement for DeepStream 6.0
typedef struct {
    uint16_t sensorId;
} NvDsMsg2pCtx;

// Initialization called by DeepStream's msgconv when library is loaded
NvDsMsg2pCtx* nvds_msg2p_ctx_create(const gchar *file, NvDsPayloadType type);

// Release resources
void nvds_msg2p_ctx_destroy(NvDsMsg2pCtx *ctx);

// Build payload: called for each event
NvDsPayload* nvds_msg2p_generate(NvDsMsg2pCtx *ctx, NvDsEventMsgMeta *meta);

// NEW API: Called when msg-conv-msg2p-new-api=1 is set
NvDsPayload* nvds_msg2p_generate_new(NvDsMsg2pCtx *ctx, void *metadataInfo);

// Release payload memory
void nvds_msg2p_release(NvDsMsg2pCtx *ctx, NvDsPayload *payload);

#ifdef __cplusplus
}
#endif
