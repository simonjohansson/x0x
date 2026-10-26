#include "adapter.h"

static void position(void *context, uint32_t slot, enum x0z_control control,
                     struct x0z_position value)
{
    (void)slot;
    (void)control;
    ((struct x0z_dn_value *)context)->position = value;
}

int x0z_dn_forget(struct x0z_dn_adapter *adapter, int32_t slot)
{
    if (!adapter || (uint32_t)slot >= 8)
        return 0;
    adapter->slot[slot].active = 0;
    return 1;
}

int x0z_dn_render(struct x0z_dn_adapter *adapter, int32_t slot, int32_t output[32],
                  const struct dnm_voice *voice, enum x0z_instrument instrument,
                  const struct x0z_dn_mapping *mapping, uint32_t count,
                  x0z_dn_receiver receiver, void *context)
{
    struct x0z_dn_input input;
    uint32_t i, j;
    if (!adapter || (uint32_t)slot >= 8 || !output || !voice || !receiver ||
        (uint32_t)voice->track >= 4 || voice->velocity < 1 || voice->velocity > 127 ||
        (voice->fresh != 0 && voice->fresh != 1) || (voice->gate != 0 && voice->gate != 1) ||
        !count || count > X0Z_DN_CONTROLS || !mapping)
        return 0;
    input.output = output;
    input.slot = (uint32_t)slot;
    input.track = (uint32_t)voice->track;
    input.pitch = voice->pitch;
    input.velocity = (uint32_t)voice->velocity;
    input.gate = (uint32_t)voice->gate;
    input.count = count;
    for (i = 0; i < count; ++i) {
        int32_t raw, minimum, maximum;
        if ((uint32_t)mapping[i].knob >= DNM_KNOBS_ALL)
            return 0;
        for (j = 0; j < i; ++j)
            if (mapping[j].knob == mapping[i].knob || mapping[j].control == mapping[i].control)
                return 0;
        dnm_knob_range(mapping[i].knob, &minimum, &maximum);
        raw = dnm_knob(slot, mapping[i].knob);
        if (minimum >= maximum || raw < minimum || raw > maximum)
            return 0;
        input.value[i].control = mapping[i].control;
        input.value[i].raw = raw;
        input.value[i].minimum = minimum;
        input.value[i].maximum = maximum;
        if (!x0z_send_control(instrument, (uint32_t)slot, mapping[i].control,
                             (uint32_t)raw - (uint32_t)minimum,
                             (uint32_t)maximum - (uint32_t)minimum,
                             position, &input.value[i]))
            return 0;
    }
    input.flags = voice->fresh ? X0Z_DN_NATIVE_START : 0;
    input.generation = adapter->slot[slot].generation;
    if (!adapter->slot[slot].active || adapter->slot[slot].track != input.track) {
        input.flags |= X0Z_DN_ASSIGNED;
        ++input.generation;
    }
    adapter->slot[slot].active = 1;
    adapter->slot[slot].track = input.track;
    adapter->slot[slot].generation = input.generation;
    receiver(context, &input);
    return 1;
}
