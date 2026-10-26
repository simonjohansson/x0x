#include "digitakt-mk1/core3.h"

#define X0Z_ID 80

/* Existing private selector ABI: eight {initialized, model, tail} lanes. */
static uint32_t selection[8][3];
extern int x0z_selector(uint32_t bank[8][3], uint32_t notice[4],
                        const uint32_t input[4]);
extern void x0z_silence(int32_t output[32]);

void x0z_dt_render(int32_t *blocks)
{
    static const int32_t parameters[] = {0, 1, 2, 5};
    for (uint32_t track = 0; track < 8; ++track) {
        if (fw_render_machine[track] != X0Z_ID) {
            selection[track][0] = selection[track][1] = selection[track][2] = 0;
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
        (void)x0z_selector(selection, notice, input);
        /* shortcut: both selected engines remain silent until their DSP lands. */
        x0z_silence(blocks + 32 * track);
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

const struct cm_machine x0z_dt_machine = {
    .id = X0Z_ID,
    .name = "X0Z KICKS",
    .sname = "KICKS",
    .params = 3,
    .render = X0Z_ID,
    .tag = CM_UI_TAG,
    .ui = &page,
};
