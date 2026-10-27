#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "controls.h"

struct fake_dsp {
    struct x0x_position values[16][6];
    uint32_t mask[16], tail[16], controls, notices;
    struct x0x_dn2_control_notice last;
};

static void control(void *context, uint32_t slot, enum x0x_control kind,
                     struct x0x_position position)
{
    struct fake_dsp *dsp = context;
    assert(slot < 16 && kind < X0X_STRENGTH && position.denominator == 32512);
    assert(kind != X0X_LEVEL);
    dsp->values[slot][kind] = position;
    dsp->mask[slot] |= 1u << kind;
    ++dsp->controls;
}

static uint32_t expected_mask(enum x0x_instrument instrument)
{
    return (1u << X0X_DECAY) |
           (instrument == X0X_808 ? 1u << X0X_TONE : (1u << X0X_TUNE) | (1u << X0X_ATTACK));
}

static void notice(void *context, const struct x0x_dn2_control_notice *event)
{
    struct fake_dsp *dsp = context;
    uint32_t slot = event->delivered.slot;
    assert(dsp->mask[slot] == expected_mask(event->instrument));
    if (event->clear_tail)
        dsp->tail[slot] = 0; /* Fake dynamic state, not a synth reset implementation. */
    dsp->last = *event;
    ++dsp->notices;
}

static void defaults(uint32_t *params)
{
    for (unsigned index = 0; index < DN2_VOICE_PARAMS; ++index)
        params[index] = UINT32_MAX;
    const struct mk2_page *page = x0x_dn2_voice_pages.page;
    for (unsigned knob = 0; knob < 8; ++knob)
        if (page->knob[knob])
            params[knob] = page->knob[knob]->def << 8;
}

static void deliver(struct x0x_dn2_controls *state, struct dn2_voice_input *input,
                     struct fake_dsp *dsp)
{
    dsp->mask[input->slot] = 0;
    assert(x0x_dn2_controls_deliver(state, input, control, notice, dsp));
}

static void declarations(void)
{
    assert(x0x_dn2_synth.id == 20);
    assert(!strcmp(x0x_dn2_synth.name, "X0X KICKS"));
    assert(!strcmp(x0x_dn2_synth.label, "KICKS"));
    assert(x0x_dn2_voice_pages.id == 20 && x0x_dn2_voice_pages.count == 1);
    const char *labels[] = {"TNTUN", "DECAY", "ATTK", 0, 0, "MODEL", 0, 0};
    const unsigned values[] = {64, 64, 64, 0, 0, 0, 0, 0};
    for (unsigned index = 0; index < 8; ++index) {
        const struct mk2_param *knob = x0x_dn2_voice_pages.page->knob[index];
        if (!labels[index])
            assert(!knob);
        else
            assert(knob && !strcmp(knob->label, labels[index]) && knob->def == values[index]);
    }
}

static void fractions(enum x0x_instrument instrument)
{
    struct x0x_dn2_controls state;
    struct fake_dsp dsp = {0};
    uint32_t params[DN2_VOICE_PARAMS];
    float audio[32];
    for (unsigned index = 0; index < 32; ++index)
        audio[index] = .375f;
    defaults(params);
    params[5] = instrument == X0X_808 ? 0 : 32512;
    struct dn2_voice_input input = {audio, 15, 60 * 256 + 127, DN2_VOICE_START, params};
    x0x_dn2_controls_init(&state);
    const uint32_t values[] = {0, 1, 128, 12345, 32512};
    for (unsigned index = 0; index < sizeof(values) / sizeof(values[0]); ++index) {
        params[0] = values[index];
        params[1] = values[4 - index];
        params[2] = values[(index + 1) % 5];
        deliver(&state, &input, &dsp);
        assert(dsp.last.instrument == instrument);
        assert(dsp.values[15][X0X_LEVEL].denominator == 0);
        assert(dsp.values[15][X0X_DECAY].numerator == values[4 - index]);
        enum x0x_control pitch_control = instrument == X0X_808 ? X0X_TONE : X0X_TUNE;
        assert(dsp.values[15][pitch_control].numerator == values[index]);
        if (instrument == X0X_909)
            assert(dsp.values[15][X0X_ATTACK].numerator == values[(index + 1) % 5]);
        else
            assert(dsp.values[15][X0X_ATTACK].denominator == 0);
        assert(!dsp.last.model_changed && dsp.last.initialize == (index == 0));
        assert(dsp.last.clear_tail == (index == 0));
        assert(dsp.last.delivered.pitch == input.pitch);
        dsp.tail[15] = 777;
        input.pitch = index & 1 ? 0 : 0xffff; /* Note pitch adds no kick tuning control. */
    }
    assert(dsp.tail[15] == 777);
    for (unsigned index = 0; index < 32; ++index)
        assert(audio[index] == .375f);
}

static void selector_and_tails(void)
{
    struct x0x_dn2_controls state;
    struct fake_dsp dsp = {0};
    uint32_t params[DN2_VOICE_PARAMS];
    defaults(params);
    struct dn2_voice_input input = {0, 2, 12345, 0, params};
    x0x_dn2_controls_init(&state);
    params[5] = 32512;
    deliver(&state, &input, &dsp);
    assert(!state.voice[2].initialized && !dsp.controls && !dsp.notices);
    input.flags = DN2_VOICE_START;
    deliver(&state, &input, &dsp);
    assert(dsp.last.initialize && dsp.last.clear_tail && !dsp.last.model_changed);
    assert(state.voice[2].instrument == X0X_909);
    dsp.tail[2] = 901;
    params[5] = 0;
    input.flags = 0;
    deliver(&state, &input, &dsp);
    assert(dsp.last.instrument == X0X_909 && !dsp.last.clear_tail && dsp.tail[2] == 901);
    assert(dsp.last.delivered.boundary == X0X_DN2_CONTINUE);
    input.flags = DN2_VOICE_START;
    deliver(&state, &input, &dsp);
    assert(dsp.last.model_changed && dsp.last.clear_tail && !dsp.last.initialize);
    assert(dsp.last.instrument == X0X_808 && dsp.tail[2] == 0);
    dsp.tail[2] = 808;
    deliver(&state, &input, &dsp);
    assert(!dsp.last.clear_tail && !dsp.last.model_changed && dsp.tail[2] == 808);
    assert(dsp.last.delivered.boundary == X0X_DN2_START_UNCLASSIFIED);

    const uint32_t thresholds[] = {0, 16383, 16384, 32512};
    for (unsigned slot = 0; slot < 16; ++slot) {
        input.slot = slot;
        params[5] = thresholds[slot % 4];
        deliver(&state, &input, &dsp);
        assert(state.voice[slot].instrument == (slot % 4 < 2 ? X0X_808 : X0X_909));
        dsp.tail[slot] = slot + 1;
    }
    input.slot = 15;
    params[5] = 0;
    deliver(&state, &input, &dsp);
    assert(dsp.tail[15] == 0);
    for (unsigned slot = 0; slot < 15; ++slot)
        assert(dsp.tail[slot] == slot + 1);
}

static void ignored_and_invalid(void)
{
    struct x0x_dn2_controls state;
    struct fake_dsp dsp = {0};
    uint32_t params[DN2_VOICE_PARAMS];
    defaults(params);
    struct dn2_voice_input input = {0, 0, 0, DN2_VOICE_START, params};
    x0x_dn2_controls_init(&state);
    deliver(&state, &input, &dsp);
    dsp.tail[0] = 900;
    struct x0x_position previous_values[16][6];
    memcpy(previous_values, dsp.values, sizeof(previous_values));
    input.flags = 0;
    params[2] = 1; /* Declared ATTK is inert for 808. */
    params[3] = 32513; /* Blank D is not a declared control. */
    params[4] = 42; /* E has no strength control. */
    params[6] = 1;
    params[7] = 0;
    deliver(&state, &input, &dsp);
    assert(dsp.tail[0] == 900 && !dsp.values[0][X0X_ATTACK].denominator);
    assert(!dsp.values[0][X0X_STRENGTH].denominator);
    assert(!memcmp(dsp.values, previous_values, sizeof(previous_values)));

    struct x0x_dn2_controls previous = state;
    unsigned char dsp_before[sizeof(dsp)];
    memcpy(dsp_before, &dsp, sizeof(dsp));
    for (unsigned parameter = 0; parameter < 6; ++parameter) {
        if (parameter == 3 || parameter == 4)
            continue;
        uint32_t saved = params[parameter];
        params[parameter] = 32513;
        assert(!x0x_dn2_controls_deliver(&state, &input, control, notice, &dsp));
        params[parameter] = saved;
        assert(!memcmp(&state, &previous, sizeof(state)));
        assert(!memcmp(&dsp, dsp_before, sizeof(dsp)));
    }
    for (unsigned invalid = 0; invalid < 6; ++invalid) {
        struct dn2_voice_input bad = input;
        if (invalid == 0) bad.slot = 16;
        if (invalid == 1) bad.pitch = 0x10000;
        if (invalid == 2) bad.flags = 2;
        if (invalid == 3) bad.param = 0;
        assert(!x0x_dn2_controls_deliver(&state, &bad,
            invalid == 4 ? 0 : control, invalid == 5 ? 0 : notice, &dsp));
    }
    assert(!x0x_dn2_controls_deliver(0, &input, control, notice, &dsp));
    assert(!x0x_dn2_controls_deliver(&state, 0, control, notice, &dsp));
    assert(!memcmp(&state, &previous, sizeof(state)));
    assert(!memcmp(&dsp, dsp_before, sizeof(dsp)));
}

int main(void)
{
    declarations();
    fractions(X0X_808);
    fractions(X0X_909);
    selector_and_tails();
    ignored_and_invalid();
    return 0;
}
