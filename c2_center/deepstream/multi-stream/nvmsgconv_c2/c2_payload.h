#pragma once

/*
 * nvmsgconv_c2 — payload builder header (template)
 * Implement `nvds_msg2p_t` compatible functions here.
 * This file is a template; build instructions are in the Makefile.
 */

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Initialization called by DeepStream's msgconv when library is loaded
int nvds_msg2p_init(void **userdata);

// Release resources
void nvds_msg2p_deinit(void *userdata);

// Build payload: called for each frame
// Return 0 on success, non-zero on error
int nvds_msg2p_generate(void *userdata, const char *input_meta, char **payload, int *payload_len);

#ifdef __cplusplus
}
#endif
