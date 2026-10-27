#include "adapter.h"

#define X0X_ID 80

static struct x0x_dn_frame frame;
static struct x0x_dn_adapter adapter;
/* Existing private ColdFire selector ABI, shared with Digitakt. */
static uint32_t selection[8][3];
static int32_t body[8][2];
extern int x0x_selector(uint32_t bank[8][3], uint32_t notice[4], const uint32_t input[4]);
extern void x0x_silence(int32_t output[32]);
extern void x0x_808_body(int32_t state[2], int32_t output[32], uint32_t start);

void x0x_dn_begin(void)
{
    x0x_dn_frame_begin(&frame);
    for (uint32_t slot = 0; slot < 8; ++slot) {
        if ((FW_VOICE_PARAM(slot, 0) >> 8) == X0X_ID)
            continue;
        selection[slot][0] = selection[slot][1] = selection[slot][2] = 0;
        body[slot][0] = body[slot][1] = 0;
        x0x_dn_forget(&adapter, (int32_t)slot);
    }
}

void x0x_dn_capture(int16_t *words) { x0x_dn_frame_capture(&frame, words); }
void x0x_dn_ready(int32_t *voices) { (void)voices; x0x_dn_frame_ready(&frame); }
void x0x_dn_end(void) { x0x_dn_frame_end(&frame); }

static void render_body(void *context, const struct x0x_dn_input *input)
{
    (void)context;
    /* shortcut: fixed provisional 808 body; controls and circuit calibration follow in #9. */
    if (selection[input->slot][1] == 0)
        x0x_808_body(body[input->slot], input->output, !!(input->flags & X0X_DN_NATIVE_START));
    else
        x0x_silence(input->output);
}

static void x0x_dn_machine_render(int32_t slot, int32_t *block, const struct dnm_voice *voice)
{
    static const struct x0x_dn_frame_mapping controls_808[] = {{X0X_TONE, 119}, {X0X_DECAY, 120}};
    static const struct x0x_dn_frame_mapping controls_909[] = {
        {X0X_TUNE, 119}, {X0X_DECAY, 120}, {X0X_ATTACK, 121}
    };
    int32_t raw, minimum, maximum;
    uint32_t model, notice[4], valid = 1;
    if ((uint32_t)slot >= 8 || !block)
        return;
    if (!voice || (uint32_t)voice->track >= 4 || voice->velocity < 1 || voice->velocity > 127 ||
            (uint32_t)voice->fresh > 1 || (uint32_t)voice->gate > 1) {
        x0x_silence(block);
        return;
    }
    for (uint32_t parameter = 119; parameter <= 121; ++parameter)
        valid &= x0x_dn_frame_read(&frame, slot, parameter, &raw, &minimum, &maximum);
    valid &= x0x_dn_frame_model(&frame, slot, 124, &raw, &model);
    if (adapter.slot[slot].active && adapter.slot[slot].track != (uint32_t)voice->track) {
        selection[slot][0] = selection[slot][1] = selection[slot][2] = 0;
        body[slot][0] = body[slot][1] = 0;
    }
    const uint32_t input[] = {(uint32_t)slot, valid ? model : 0, (uint32_t)voice->fresh, valid};
    if (x0x_selector(selection, notice, input) == 1) {
        enum x0x_instrument instrument = notice[0] ? X0X_909 : X0X_808;
        if (notice[3])
            body[slot][0] = body[slot][1] = 0;
        if (x0x_dn_render_frame(&adapter, slot, block, voice, instrument, &frame,
                notice[0] ? controls_909 : controls_808, notice[0] ? 3 : 2, render_body, 0))
            return;
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
