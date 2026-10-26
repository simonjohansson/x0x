#ifndef X0Z_DIGITONE2_CONTROLS_H
#define X0Z_DIGITONE2_CONTROLS_H

#include "adapter.h"

extern const struct mk2_synth x0z_dn2_synth;
extern const struct mk2_voice_pages x0z_dn2_voice_pages;

/* Caller-owned private state, initialized before accepting callback frames. */
struct x0z_dn2_selection {
    uint32_t initialized;
    enum x0z_instrument instrument;
};
struct x0z_dn2_controls {
    struct x0z_dn2_selection voice[16];
};

struct x0z_dn2_control_notice {
    struct x0z_dn2_notice delivered;
    enum x0z_instrument instrument;
    uint32_t initialize, model_changed, clear_tail;
};
typedef void (*x0z_dn2_control_notice_receiver)(void *context,
                                      const struct x0z_dn2_control_notice *notice);

void x0z_dn2_controls_init(struct x0z_dn2_controls *state);
/* Controls precede the notice. clear_tail requests dynamic-state clearing
 * before excitation, retaining those controls; no DSP or trigger is executed.
 * An uninitialized slot emits nothing until START. START remains unclassified
 * with respect to native logical ownership and same-model retrigger identity. */
int x0z_dn2_controls_deliver(struct x0z_dn2_controls *state,
                            const struct dn2_voice_input *input,
                            x0z_control_receiver controls,
                            x0z_dn2_control_notice_receiver notice, void *context);

#endif
