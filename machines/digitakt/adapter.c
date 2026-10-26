#include "adapter.h"
#include "digitakt-mk1/core3.h"

struct pending_control {
    enum x0z_control control;
    struct x0z_position position;
};

static void stage(void *context, uint32_t voice, enum x0z_control control,
                  struct x0z_position position)
{
    struct pending_control *pending = context;
    (void)voice;
    pending->control = control;
    pending->position = position;
}

int x0z_dt_capture(uint32_t track, enum x0z_instrument instrument,
                   const struct x0z_dt_binding *bindings, uint32_t count,
                   struct x0z_dt_snapshot *snapshot,
                   x0z_control_receiver receiver, void *context)
{
    struct pending_control pending[6];
    if (track >= 8 || !snapshot || count > 6 || (count && (!bindings || !receiver)))
        return 0;
    if (instrument != X0Z_808 && instrument != X0Z_909)
        return 0;
    for (uint32_t i = 0; i < count; ++i) {
        const struct x0z_dt_binding *binding = bindings + i;
        if (binding->parameter >= 8 || binding->minimum < INT16_MIN ||
            binding->maximum > INT16_MAX || binding->minimum >= binding->maximum)
            return 0;
        for (uint32_t j = 0; j < i; ++j)
            if (bindings[j].control == binding->control || bindings[j].parameter == binding->parameter)
                return 0;
        int32_t value = cm_src_value((int32_t)track, (int32_t)binding->parameter);
        if (value < binding->minimum || value > binding->maximum)
            return 0;
        if (!x0z_send_control(instrument, track, binding->control,
                              (uint32_t)(value - binding->minimum),
                              (uint32_t)(binding->maximum - binding->minimum),
                              stage, pending + i))
            return 0;
    }
    int32_t velocity = fw_voice_vel[track];
    if (velocity < 0 || velocity > 32512)
        return 0;
    struct x0z_dt_snapshot captured = {
        track, (fw_voice_start >> track) & 1u, fw_voice_note[track], (uint32_t)velocity,
        fw_amp_env[3 * track], fw_amp_env[3 * track + 1]
    };
    *snapshot = captured;
    for (uint32_t i = 0; i < count; ++i)
        receiver(context, track, pending[i].control, pending[i].position);
    return 1;
}
