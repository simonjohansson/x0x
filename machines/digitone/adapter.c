#include "adapter.h"

static void position(void *context, uint32_t slot, enum x0x_control control,
                     struct x0x_position value)
{
    (void)slot;
    (void)control;
    ((struct x0x_dn_value *)context)->position = value;
}

int x0x_dn_forget(struct x0x_dn_adapter *adapter, int32_t slot)
{
    if (!adapter || (uint32_t)slot >= 8)
        return 0;
    adapter->slot[slot].active = 0;
    return 1;
}

static int prepare(struct x0x_dn_adapter *adapter, int32_t slot, int32_t *output,
                   const struct dnm_voice *voice, uint32_t count,
                   x0x_dn_receiver receiver, struct x0x_dn_input *input)
{
    if (!adapter || (uint32_t)slot >= 8 || !output || !voice || !receiver ||
        (uint32_t)voice->track >= 4 || voice->velocity < 1 || voice->velocity > 127 ||
        (voice->fresh != 0 && voice->fresh != 1) || (voice->gate != 0 && voice->gate != 1) ||
        !count || count > X0X_DN_CONTROLS)
        return 0;
    input->output = output;
    input->slot = (uint32_t)slot;
    input->track = (uint32_t)voice->track;
    input->pitch = voice->pitch;
    input->velocity = (uint32_t)voice->velocity;
    input->gate = (uint32_t)voice->gate;
    input->count = count;
    return 1;
}

static int value(struct x0x_dn_input *input, uint32_t i, enum x0x_instrument instrument,
                 enum x0x_control control, int32_t raw, int32_t minimum, int32_t maximum)
{
    if (minimum >= maximum || raw < minimum || raw > maximum)
        return 0;
    input->value[i].control = control;
    input->value[i].raw = raw;
    input->value[i].minimum = minimum;
    input->value[i].maximum = maximum;
    return x0x_send_control(instrument, input->slot, control,
                            (uint32_t)raw - (uint32_t)minimum,
                            (uint32_t)maximum - (uint32_t)minimum,
                            position, &input->value[i]);
}

static int deliver(struct x0x_dn_adapter *adapter, const struct dnm_voice *voice,
                   struct x0x_dn_input *input, x0x_dn_receiver receiver, void *context)
{
    uint32_t slot = input->slot;
    input->flags = voice->fresh ? X0X_DN_NATIVE_START : 0;
    input->generation = adapter->slot[slot].generation;
    if (!adapter->slot[slot].active || adapter->slot[slot].track != input->track) {
        input->flags |= X0X_DN_ASSIGNED;
        ++input->generation;
    }
    adapter->slot[slot].active = 1;
    adapter->slot[slot].track = input->track;
    adapter->slot[slot].generation = input->generation;
    receiver(context, input);
    return 1;
}

int x0x_dn_render(struct x0x_dn_adapter *adapter, int32_t slot, int32_t output[32],
                  const struct dnm_voice *voice, enum x0x_instrument instrument,
                  const struct x0x_dn_mapping *mapping, uint32_t count,
                  x0x_dn_receiver receiver, void *context)
{
    struct x0x_dn_input input;
    uint32_t i, j;
    if (!mapping || !prepare(adapter, slot, output, voice, count, receiver, &input))
        return 0;
    for (i = 0; i < count; ++i) {
        int32_t raw, minimum, maximum;
        if ((uint32_t)mapping[i].knob >= DNM_KNOBS_ALL)
            return 0;
        for (j = 0; j < i; ++j)
            if (mapping[j].knob == mapping[i].knob || mapping[j].control == mapping[i].control)
                return 0;
        dnm_knob_range(mapping[i].knob, &minimum, &maximum);
        raw = dnm_knob(slot, mapping[i].knob);
        if (!value(&input, i, instrument, mapping[i].control, raw, minimum, maximum))
            return 0;
    }
    return deliver(adapter, voice, &input, receiver, context);
}

void x0x_dn_frame_end(struct x0x_dn_frame *frame)
{
    frame->words = 0;
    frame->phase = 0;
}

void x0x_dn_frame_begin(struct x0x_dn_frame *frame)
{
    x0x_dn_frame_end(frame);
    frame->phase = 1;
}

void x0x_dn_frame_capture(struct x0x_dn_frame *frame, const volatile int16_t *words)
{
    if (frame->phase != 1 || !words) {
        x0x_dn_frame_end(frame);
        return;
    }
    frame->words = words;
    frame->phase = 2;
}

void x0x_dn_frame_ready(struct x0x_dn_frame *frame)
{
    if (frame->phase != 2) {
        x0x_dn_frame_end(frame);
        return;
    }
    frame->phase = 3;
}

int x0x_dn_frame_read(const struct x0x_dn_frame *frame, int32_t slot,
                      uint32_t parameter, int32_t *raw, int32_t *minimum, int32_t *maximum)
{
    const int32_t *record;
    int32_t native_slot, lo, hi, word;
    if (!frame || frame->phase != 3 || !frame->words || (uint32_t)slot >= 8 ||
        parameter < 107 || parameter > 133 || !raw || !minimum || !maximum)
        return 0;
    record = (const int32_t *)(fw_params + 60 * parameter);
    native_slot = record[1]; lo = record[2]; hi = record[3];
    if ((uint32_t)native_slot >= CORE_PARAMS_VOICE || lo >= hi)
        return 0;
    word = frame->words[CORE_PARAMS_VOICE * slot + native_slot];
    if (word < lo || (word > hi &&
        !(parameter >= 119 && parameter <= 126 && lo == 0 && hi == 32512)))
        return 0;
    *raw = word; *minimum = lo; *maximum = hi;
    return 1;
}

int x0x_dn_frame_model(const struct x0x_dn_frame *frame, int32_t slot,
                       uint32_t parameter, int32_t *raw, uint32_t *canonical)
{
    int32_t observed, minimum, maximum;
    if (!raw || !canonical || (void *)raw == (void *)canonical || parameter < 119 || parameter > 126 ||
        !x0x_dn_frame_read(frame, slot, parameter, &observed, &minimum, &maximum) ||
        minimum != 0 || maximum != 32512)
        return 0;
    *raw = observed;
    *canonical = (uint32_t)(observed > maximum ? maximum : observed);
    return 1;
}

int x0x_dn_render_frame(struct x0x_dn_adapter *adapter, int32_t slot, int32_t output[32],
                       const struct dnm_voice *voice, enum x0x_instrument instrument,
                       const struct x0x_dn_frame *frame,
                       const struct x0x_dn_frame_mapping *mapping, uint32_t count,
                       x0x_dn_receiver receiver, void *context)
{
    struct x0x_dn_input input;
    uint32_t i, j;
    if (!mapping || !prepare(adapter, slot, output, voice, count, receiver, &input))
        return 0;
    for (i = 0; i < count; ++i) {
        int32_t raw, minimum, maximum;
        for (j = 0; j < i; ++j)
            if (mapping[j].parameter == mapping[i].parameter || mapping[j].control == mapping[i].control)
                return 0;
        if (!x0x_dn_frame_read(frame, slot, mapping[i].parameter, &raw, &minimum, &maximum) ||
            !value(&input, i, instrument, mapping[i].control,
                   raw > maximum ? maximum : raw, minimum, maximum))
            return 0;
        input.value[i].raw = raw; /* Preserve the observation while bounding its model position. */
    }
    return deliver(adapter, voice, &input, receiver, context);
}
