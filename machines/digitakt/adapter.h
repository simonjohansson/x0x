#ifndef X0Z_DIGITAKT_ADAPTER_H
#define X0Z_DIGITAKT_ADAPTER_H

#include <stdint.h>
#include "x0z/controls.h"

/* A render-time value index, not a committed native page or saved slot layout. */
struct x0z_dt_binding {
    uint32_t parameter;
    enum x0z_control control;
    int32_t minimum, maximum;
};

struct x0z_dt_snapshot {
    uint32_t track, native_start;
    int32_t note;
    uint32_t velocity;
    int32_t amp_phase, amp_level;
};

/* Reads the SDK's post-lock/modulation frame. AMP/velocity remain telemetry. */
int x0z_dt_capture(uint32_t track, enum x0z_instrument instrument,
                   const struct x0z_dt_binding *bindings, uint32_t count,
                   struct x0z_dt_snapshot *snapshot,
                   x0z_control_receiver receiver, void *context);

#endif
