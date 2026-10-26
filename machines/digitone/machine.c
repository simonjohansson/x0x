#include "adapter.h"

#define X0Z_ID 80

static struct x0z_dn_frame frame;
static struct x0z_dn_adapter adapter;
/* Existing private ColdFire selector ABI, shared with Digitakt. */
static uint32_t selection[8][3];
extern int x0z_selector(uint32_t bank[8][3], uint32_t notice[4], const uint32_t input[4]);
extern void x0z_silence(int32_t output[32]);

void x0z_dn_begin(void)
{
    x0z_dn_frame_begin(&frame);
    for (uint32_t slot = 0; slot < 8; ++slot) {
        if ((FW_VOICE_PARAM(slot, 0) >> 8) == X0Z_ID)
            continue;
        selection[slot][0] = selection[slot][1] = selection[slot][2] = 0;
        x0z_dn_forget(&adapter, (int32_t)slot);
    }
}

void x0z_dn_capture(int16_t *words) { x0z_dn_frame_capture(&frame, words); }
void x0z_dn_ready(int32_t *voices) { (void)voices; x0z_dn_frame_ready(&frame); }
void x0z_dn_end(void) { x0z_dn_frame_end(&frame); }

static void render_silence(void *context, const struct x0z_dn_input *input)
{
    (void)context;
    /* shortcut: both selected engines stay silent until their DSP lands. */
    x0z_silence(input->output);
}

static void x0z_dn_machine_render(int32_t slot, int32_t *block, const struct dnm_voice *voice)
{
    static const struct x0z_dn_frame_mapping controls_808[] = {{X0Z_TONE, 119}, {X0Z_DECAY, 120}};
    static const struct x0z_dn_frame_mapping controls_909[] = {
        {X0Z_TUNE, 119}, {X0Z_DECAY, 120}, {X0Z_ATTACK, 121}
    };
    int32_t raw, minimum, maximum;
    uint32_t model, notice[4], valid = 1;
    if ((uint32_t)slot >= 8 || !block)
        return;
    if (!voice || (uint32_t)voice->track >= 4 || voice->velocity < 1 || voice->velocity > 127 ||
            (uint32_t)voice->fresh > 1 || (uint32_t)voice->gate > 1) {
        x0z_silence(block);
        return;
    }
    for (uint32_t parameter = 119; parameter <= 121; ++parameter)
        valid &= x0z_dn_frame_read(&frame, slot, parameter, &raw, &minimum, &maximum);
    valid &= x0z_dn_frame_model(&frame, slot, 124, &raw, &model);
    if (adapter.slot[slot].active && adapter.slot[slot].track != (uint32_t)voice->track)
        selection[slot][0] = selection[slot][1] = selection[slot][2] = 0;
    const uint32_t input[] = {(uint32_t)slot, valid ? model : 0, (uint32_t)voice->fresh, valid};
    if (x0z_selector(selection, notice, input) == 1) {
        enum x0z_instrument instrument = notice[0] ? X0Z_909 : X0Z_808;
        if (x0z_dn_render_frame(&adapter, slot, block, voice, instrument, &frame,
                notice[0] ? controls_909 : controls_808, notice[0] ? 3 : 2, render_silence, 0))
            return;
    }
    x0z_silence(block);
}

static const struct dnm_knob knobs[DNM_KNOBS] = {
    [8] = {"TNTUN", 0, 0}, [9] = {"DECAY", 0, 0},
    [10] = {"ATTK", 0, 0}, [13] = {"MODEL", 0, 0}
};
static const int16_t defaults[DNM_KNOBS] = {
    -1, -1, -1, -1, -1, -1, -1, -1,
    16384, 16384, 16384, -1, -1, 0, -1, -1
};
const struct dnm_machine x0z_dn_machine = {X0Z_ID, "X0Z KICKS", 0, knobs, x0z_dn_machine_render, 0, defaults};
