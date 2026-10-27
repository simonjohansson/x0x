#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "digitakt-mk1/core3.h"

extern const struct cm_machine x0x_dt_machine;
extern void x0x_dt_render(int32_t *blocks);
volatile uint8_t fw_render_machine[8];
volatile uint32_t fw_voice_start;
const char cm_ui_v3[] = "test";
static uint32_t reads[8], calls[8], starts[8], models[8], body_calls, tone_calls, body909_calls, coupling_calls;
static int32_t values[8][8];

int32_t cm_src_value(int32_t track, int32_t parameter)
{
    assert(track >= 0 && track < 8 && parameter >= 0 && parameter < 8);
    reads[track] |= 1u << parameter;
    return values[track][parameter];
}

int x0x_selector(uint32_t bank[8][3], uint32_t notice[4], const uint32_t input[4])
{
    assert(bank && notice && input[0] < 8 && input[3] == 1);
    ++calls[input[0]];
    starts[input[0]] = input[2];
    models[input[0]] = input[1];
    if (!bank[input[0]][0] && !input[2]) return 4;
    bank[input[0]][0] = 1;
    notice[0] = input[1] >= 16384;
    notice[3] = 1;
    return 1;
}

void x0x_808_body(int32_t state[2], int32_t output[32], uint32_t start, uint32_t decay_raw)
{
    assert(state && start == 1 && decay_raw == 12345);
    ++body_calls;
    for (unsigned i = 0; i < 32; ++i) output[i] = 17;
}

void x0x_909_body(int32_t state[2], int32_t output[32], uint32_t start)
{
    assert(state && start == (body909_calls == 0));
    ++body909_calls;
    for (unsigned i = 0; i < 32; ++i) output[i] = 29;
}

void x0x_808_tone(int32_t *state, int32_t output[32], uint32_t tone_raw)
{
    assert(state && *state == 0 && tone_raw == 23456 && output[0] == 17);
    ++tone_calls;
}

void x0x_808_coupling(int32_t state[2], int32_t output[32])
{
    assert(state && !state[0] && !state[1] && output[0] == 17 && tone_calls == 1);
    ++coupling_calls;
    state[0] = 17; state[1] = 23;
    for (unsigned i = 0; i < 32; ++i) output[i] = 23;
}

void x0x_silence(int32_t output[32]) { memset(output, 0, 32 * sizeof *output); }

int main(void)
{
    const struct cm_machine *m = &x0x_dt_machine;
    assert(m->id == 80 && m->render == 80 && m->params == 3 && m->tag == CM_UI_TAG);
    assert(strcmp(m->name, "X0X KICKS") == 0 && strcmp(m->sname, "KICKS") == 0);
    assert(m->ui->abi == cm_ui_v3 && m->ui->page_from == 3 && !m->ui->on_switch);
    const char *names[] = {"TNTUN", "DECAY", "ATTK", 0, 0, "MODEL", 0, 0};
    const int32_t defaults[] = {16384, 16384, 16384, 0, 0, 0, 0, 0};
    for (unsigned k = 0; k < 8; ++k) {
        const struct cm_knob *knob = &m->ui->knob[k];
        if (!names[k]) {
            assert(knob->flags == (CM_HIDDEN | (k == 3 ? CM_NOT_SAMPLE : 0)) && !knob->name);
            continue;
        }
        assert(strcmp(knob->name, names[k]) == 0 && knob->look == 0x86);
        assert(knob->flags == (CM_RANGE | CM_DEFAULT));
        assert(knob->min == 0 && knob->max == 32512 && knob->def == defaults[k]);
    }
    int32_t blocks[256];
    for (unsigned i = 0; i < 256; ++i) blocks[i] = (int32_t)i + 1;
    fw_render_machine[0] = fw_render_machine[7] = 80;
    fw_voice_start = 1u << 7;
    values[0][0] = 23456;
    values[0][1] = 12345;
    values[0][5] = 16383;
    values[7][5] = 16384;
    x0x_dt_render(blocks);
    for (unsigned track = 0; track < 8; ++track) {
        int active = track == 0 || track == 7;
        assert(reads[track] == (active ? 0x27 : 0));
        assert(calls[track] == (unsigned)active);
        for (unsigned i = 0; i < 32; ++i)
            assert(blocks[32 * track + i] == (track == 7 ? 29 : active ? 0 : (int32_t)(32 * track + i + 1)));
    }
    assert(starts[0] == 0 && starts[7] == 1 && models[0] == 16383 && models[7] == 16384);
    assert(body_calls == 0 && body909_calls == 1 && tone_calls == 0);
    fw_voice_start = 1;
    x0x_dt_render(blocks);
    assert(body_calls == 1 && tone_calls == 1 && body909_calls == 2 && coupling_calls == 1);
    for (unsigned i = 0; i < 32; ++i) assert(blocks[i] == 23);
    for (unsigned i = 224; i < 256; ++i) assert(blocks[i] == 29);
    return 0;
}
