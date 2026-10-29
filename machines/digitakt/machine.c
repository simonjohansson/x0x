#include "digitakt-mk1/core3.h"
#include "../../targets/coldfire/engine.h"
#define X0X_ID 80
static struct x0x_voice voices[8];
void x0x_dt_render(int32_t *blocks)
{
    for (uint32_t track = 0; track < 8; ++track) {
        if (fw_render_machine[track] != X0X_ID) {
            voices[track].selected = 0;
            continue;
        }
        x0x_render(&voices[track], blocks + 32 * track, (fw_voice_start >> track) & 1u,
            (uint32_t)cm_src_value(track, 0), (uint32_t)cm_src_value(track, 1),
            (uint32_t)cm_src_value(track, 5), (uint32_t)cm_src_value(track, 2));
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
