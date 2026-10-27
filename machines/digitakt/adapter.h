#ifndef X0X_DIGITAKT_ADAPTER_H
#define X0X_DIGITAKT_ADAPTER_H

#include <stdint.h>
#include "x0x/controls.h"

/* A render-time value index, not a committed native page or saved slot layout. */
struct x0x_dt_binding {
    uint32_t parameter;
    enum x0x_control control;
    int32_t minimum, maximum;
};

struct x0x_dt_snapshot {
    uint32_t track, native_start;
    int32_t note;
    uint32_t velocity;
    int32_t amp_phase, amp_level;
};

/* Reads the SDK's post-lock/modulation frame. AMP/velocity remain telemetry. */
int x0x_dt_capture(uint32_t track, enum x0x_instrument instrument,
                   const struct x0x_dt_binding *bindings, uint32_t count,
                   struct x0x_dt_snapshot *snapshot,
                   x0x_control_receiver receiver, void *context);

#endif
