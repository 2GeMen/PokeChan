/*
 * StackChan bridge: stands in for the Muse SDK's muse_state.h, of which the
 * chat code only needs the caption page size.
 */

#pragma once

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

void muse_state_page(bool cjk, int *cols, int *lines);

#ifdef __cplusplus
}
#endif
