#include "digitakt-mk1/core3.h"

#define X0X_ID 80

/* Existing private selector ABI: eight {initialized, model, tail} lanes. */
static uint32_t selection[8][3];
static int32_t body_state[8][5];
static int32_t tone_state[8];
static int32_t coupling_state[8][2];
extern int x0x_selector(uint32_t bank[8][3], uint32_t notice[4],
                        const uint32_t input[4]);
extern void x0x_silence(int32_t output[32]);
extern void x0x_808_tone(int32_t *state, int32_t output[32], uint32_t tone_raw);
extern void x0x_808_coupling(int32_t state[2], int32_t output[32]);
extern void x0x_909_body(int32_t state[4], int32_t output[32], uint32_t start, uint32_t decay_raw, uint32_t tune_raw);
extern void x0x_808_body(int32_t state[5], int32_t output[32], uint32_t start, uint32_t decay_raw);

void x0x_dt_render(int32_t *blocks)
{
    static const int32_t parameters[] = {0, 1, 2, 5};
    for (uint32_t track = 0; track < 8; ++track) {
        if (fw_render_machine[track] != X0X_ID) {
            selection[track][0] = selection[track][1] = selection[track][2] = 0;
            body_state[track][0] = body_state[track][1] = body_state[track][2] = body_state[track][3] = body_state[track][4] = 0;
            tone_state[track] = 0;
            coupling_state[track][0] = coupling_state[track][1] = 0;
            continue;
        }
        int32_t values[4];
        uint32_t valid = 1;
        for (uint32_t k = 0; k < 4; ++k) {
            values[k] = cm_src_value((int32_t)track, parameters[k]);
            valid &= values[k] >= 0 && values[k] <= 32512;
        }
        uint32_t notice[4];
        const uint32_t input[] = {track, (uint32_t)values[3],
                                 (fw_voice_start >> track) & 1u, valid};
        if (x0x_selector(selection, notice, input) == 1) {
            if (notice[3]) {
                body_state[track][0] = body_state[track][1] = body_state[track][2] = body_state[track][3] = body_state[track][4] = 0;
                tone_state[track] = 0;
                coupling_state[track][0] = coupling_state[track][1] = 0;
            }
            if (notice[0] == 0) {
                /* shortcut: the provisional body restarts all audio state on START. */
                if (input[2]) {
                    tone_state[track] = 0;
                    coupling_state[track][0] = coupling_state[track][1] = 0;
                }
                x0x_808_body(body_state[track], blocks + 32 * track, input[2], (uint32_t)values[1]);
                x0x_808_tone(&tone_state[track], blocks + 32 * track, (uint32_t)values[0]);
                x0x_808_coupling(coupling_state[track], blocks + 32 * track);
            } else {
                x0x_909_body(body_state[track], blocks + 32 * track, input[2], (uint32_t)values[1], (uint32_t)values[0]);
            }
            continue;
        }
        x0x_silence(blocks + 32 * track);
    }
}

#define CONTROL(label, long_name, initial, extra_flags) \
    { .name = label, .lname = long_name, .look = 0x86, \
      .flags = CM_RANGE | CM_DEFAULT | (extra_flags), \
      .min = 0, .max = 32512, .def = (initial) << 8 }

static const struct cm_ui page = {
    .abi = cm_ui_v3,
    .page_from = 3,
    .knob = {
        CONTROL("TNTUN", "Tone / Tune", 64, 0),
        CONTROL("DECAY", "Decay", 64, 0),
        CONTROL("ATTK", "909 Attack", 64, 0),
        /* Keep SRC on this page instead of cycling to the stock sample view. */
        { .flags = CM_HIDDEN | CM_NOT_SAMPLE },
        { .flags = CM_HIDDEN },
        CONTROL("MODEL", "Model", 0, 0),
        { .flags = CM_HIDDEN },
        { .flags = CM_HIDDEN },
    },
};

const struct cm_machine x0x_dt_machine = {
    .id = X0X_ID,
    .name = "X0X KICKS",
    .sname = "KICKS",
    .params = 3,
    .render = X0X_ID,
    .tag = CM_UI_TAG,
    .ui = &page,
};
