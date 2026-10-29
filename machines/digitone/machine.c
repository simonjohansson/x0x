#include "adapter.h"
#include "../../targets/coldfire/engine.h"

#define X0X_ID 20

static struct x0x_dn_frame frame;
static struct x0x_dn_adapter adapter;
static struct x0x_voice voices[8];

void x0x_dn_begin(void)
{
    x0x_dn_frame_begin(&frame);
    for (uint32_t slot = 0; slot < 8; ++slot) {
        if ((FW_VOICE_PARAM(slot, 0) >> 8) == X0X_ID)
            continue;
        voices[slot].selected = 0;
        x0x_dn_forget(&adapter, (int32_t)slot);
    }
}

void x0x_dn_capture(int16_t *words) { x0x_dn_frame_capture(&frame, words); }
void x0x_dn_ready(int32_t *voices) { (void)voices; x0x_dn_frame_ready(&frame); }
void x0x_dn_end(void) { x0x_dn_frame_end(&frame); }

static void render_body(void *context, const struct x0x_dn_input *input)
{
    uint32_t model = *(const uint32_t *)context;
    x0x_render(&voices[input->slot], input->output, !!(input->flags & X0X_DN_NATIVE_START),
        input->value[0].position.numerator, input->value[1].position.numerator,
        model, model >= 16384 ? input->value[2].position.numerator : 0);
}

static void x0x_dn_machine_render(int32_t slot, int32_t *block, const struct dnm_voice *voice)
{
    static const struct x0x_dn_frame_mapping controls_808[] = {{X0X_TONE, 119}, {X0X_DECAY, 120}};
    static const struct x0x_dn_frame_mapping controls_909[] = {
        {X0X_TUNE, 119}, {X0X_DECAY, 120}, {X0X_ATTACK, 121}
    };
    int32_t raw, minimum, maximum;
    uint32_t model, valid = 1;
    if ((uint32_t)slot >= 8 || !block)
        return;
    if (!voice || (uint32_t)voice->track >= 4 || voice->velocity < 1 || voice->velocity > 127 ||
            (uint32_t)voice->fresh > 1 || (uint32_t)voice->gate > 1) {
        x0x_silence(block);
        return;
    }
    for (uint32_t parameter = 119; parameter <= 120; ++parameter)
        valid &= x0x_dn_frame_read(&frame, slot, parameter, &raw, &minimum, &maximum);
    valid &= x0x_dn_frame_model(&frame, slot, 124, &raw, &model);
    if (adapter.slot[slot].active && adapter.slot[slot].track != (uint32_t)voice->track) {
        voices[slot].selected = 0;
    }
    /* Commit a new tag only after the complete frame reaches render_body. */
    uint32_t selected = valid && voice->fresh ? (model < 16384 ? 1 : 2) : voices[slot].selected;
    uint32_t chosen_model = selected == 2 ? 32512 : 0;
    if (valid && (selected == 1 || selected == 2)) {
        enum x0x_instrument instrument=selected == 2 ? X0X_909 : X0X_808;
        if (x0x_dn_render_frame(&adapter,slot,block,voice,instrument,&frame,
                selected == 2 ? controls_909 : controls_808,
                selected == 2 ? 3 : 2, render_body, &chosen_model)) return;
    }
    x0x_silence(block);
}

static const struct dnm_knob knobs[DNM_KNOBS] = {
    [8] = {"TNTUN", 0, 0}, [9] = {"DECAY", 0, 0},
    [10] = {"ATTK", 0, 0}, [13] = {"MODEL", 0, 0}
};
static const int16_t defaults[DNM_KNOBS] = {
    -1, -1, -1, -1, -1, -1, -1, -1,
    16384, 16384, 16384, -1, -1, 0, -1, -1
};
const struct dnm_machine x0x_dn_machine = {X0X_ID, "X0X KICKS", 0, knobs, x0x_dn_machine_render, 0, defaults};
