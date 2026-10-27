#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "../../machines/digitone/adapter.h"

extern const struct dnm_machine x0x_dn_machine;
extern void x0x_dn_begin(void), x0x_dn_capture(int16_t *words), x0x_dn_ready(int32_t *voices), x0x_dn_end(void);
volatile int16_t fw_voice_params[9 + 8 * CORE_PARAMS_VOICE];
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
#define WORD(p, o, v) [60*(p)+(o)] = (v)&255, [60*(p)+(o)+1] = ((v)>>8)&255
#else
#define WORD(p, o, v) [60*(p)+(o)+2] = ((v)>>8)&255, [60*(p)+(o)+3] = (v)&255
#endif
#define RECORD(p, slot) WORD(p, 4, slot), WORD(p, 12, 32512)
const uint8_t fw_params[134 * 60] __attribute__((aligned(4))) = {
    RECORD(119, 27), RECORD(120, 28), RECORD(121, 29), RECORD(124, 32)
};
static uint32_t calls, input_seen[4], zeroes;
static uint32_t body_calls, body_start, body_decay;
static int32_t *body_state, body_before[2];
static uint32_t tone_calls, tone_raw;
static int32_t *tone_state, tone_before;
static uint32_t calls909, start909;
static int32_t *state909, before909[2];
int32_t dnm_knob(int32_t slot, int32_t knob) { (void)slot; (void)knob; assert(0); return 0; }
void dnm_knob_range(int32_t knob, int32_t *lo, int32_t *hi) { (void)knob; (void)lo; (void)hi; assert(0); }
int x0x_selector(uint32_t bank[8][3], uint32_t notice[4], const uint32_t input[4])
{
    assert(bank && notice);
    memcpy(input_seen, input, sizeof input_seen);
    ++calls;
    if (!input[3]) return 2;
    uint32_t *state = bank[input[0]], model = input[1] >= 16384;
    notice[3] = input[2] && (!state[0] || model != state[1]);
    if (input[2]) { state[0] = 1; state[1] = model; }
    notice[0] = state[1];
    return state[0] ? 1 : 4;
}
void x0x_silence(int32_t output[32]) { ++zeroes; memset(output, 0, 128); }
void x0x_808_body(int32_t state[2], int32_t output[32], uint32_t start, uint32_t decay_raw)
{
    ++body_calls; body_start = start; body_state = state; body_decay = decay_raw;
    memcpy(body_before, state, sizeof body_before);
    if (start) { state[0] = 100; state[1] = 200; }
    for (unsigned k = 0; k < 32; ++k) output[k] = ++state[0];
}
void x0x_808_tone(int32_t *state, int32_t output[32], uint32_t raw)
{
    assert(output);
    ++tone_calls; tone_raw = raw; tone_state = state; tone_before = *state;
    ++*state;
}
void x0x_909_body(int32_t state[2], int32_t output[32], uint32_t start)
{
    ++calls909; start909 = start; state909 = state;
    memcpy(before909, state, sizeof before909);
    if (start) { state[0] = -100; state[1] = -200; }
    for (unsigned k = 0; k < 32; ++k) output[k] = --state[0];
}

int main(void)
{
    const struct dnm_machine *m = &x0x_dn_machine;
    const char *labels[] = {0,0,0,0,0,0,0,0,"TNTUN","DECAY","ATTK",0,0,"MODEL",0,0};
    assert(m->id == 80 && !strcmp(m->name, "X0X KICKS") && !m->flags && !m->icon);
    for (unsigned k = 0; k < DNM_KNOBS; ++k) {
        assert(!m->knobs[k].fmt && !m->knobs[k].look);
        if (labels[k]) {
            assert(!strcmp(m->knobs[k].name, labels[k]));
            assert(m->defaults[k] == (k == 13 ? 0 : 16384));
        } else assert(!m->knobs[k].name && m->defaults[k] == -1);
    }
    int16_t words[8 * CORE_PARAMS_VOICE] = {0};
    struct dnm_voice voice = {60 << 16, 100, 1, 2, 1};
    int32_t guarded[34];
    for (unsigned k = 0; k < 34; ++k) guarded[k] = 12345;
    FW_VOICE_PARAM(3, 0) = 80 << 8;
    words[3 * 79 + 27] = 12345; words[3 * 79 + 28] = 6789;
    words[3 * 79 + 29] = 16384; words[3 * 79 + 32] = 32767;
    x0x_dn_begin(); x0x_dn_capture(words); x0x_dn_ready(0);
    m->render(3, guarded + 1, &voice);
    assert(calls == 1 && zeroes == 0 && calls909 == 1 && start909 == 1);
    assert(before909[0] == 0 && before909[1] == 0 && body_calls == 0 && tone_calls == 0);
    assert(input_seen[0] == 3 && input_seen[1] == 32512 && input_seen[2] == 1 && input_seen[3] == 1);
    assert(guarded[1] == -101 && guarded[32] == -132);
    assert(guarded[0] == 12345 && guarded[33] == 12345);
    x0x_dn_end();
    m->render(3, guarded + 1, &voice);
    assert(calls == 2 && zeroes == 1 && input_seen[3] == 0);
    for (unsigned k = 1; k < 33; ++k) assert(!guarded[k]);
    words[3 * 79 + 32] = 0;
    x0x_dn_begin(); x0x_dn_capture(words); x0x_dn_ready(0);
    m->render(3, guarded + 1, &voice);
    assert(body_calls == 1 && body_start == 1 && body_before[0] == 0 && body_before[1] == 0);
    assert(body_decay == 6789); /* Preserve the delivered fractional position. */
    assert(tone_calls == 1 && tone_raw == 12345 && tone_before == 0);
    assert(guarded[1] == 101 && guarded[32] == 132);
    int32_t *slot3 = body_state;
    int32_t *tone3 = tone_state;
    voice.fresh = 0;
    words[3 * 79 + 27] = 32767;
    words[3 * 79 + 28] = 32767;
    m->render(3, guarded + 1, &voice);
    assert(body_calls == 2 && body_start == 0 && body_before[0] == 132);
    assert(body_decay == 32512); /* Bound native modulation above the UI maximum. */
    assert(tone_calls == 2 && tone_raw == 32512 && tone_before == 1);
    assert(guarded[1] == 133 && guarded[32] == 164);
    /* A pending 909 edit keeps the 808 until START, then clears that voice. */
    words[3 * 79 + 32] = 32512;
    m->render(3, guarded + 1, &voice);
    assert(body_calls == 3 && body_start == 0);
    voice.fresh = 1;
    m->render(3, guarded + 1, &voice);
    assert(body_calls == 3 && zeroes == 1 && calls909 == 2 && state909 == slot3);
    assert(start909 == 1 && before909[0] == 0 && before909[1] == 0);
    assert(tone_calls == 3 && *tone3 == 0);
    voice.fresh = 0;
    m->render(3, guarded + 1, &voice);
    assert(calls909 == 3 && start909 == 0 && before909[0] == -132 && guarded[1] == -133);
    assert(body_calls == 3 && tone_calls == 3);
    words[3 * 79 + 32] = 0;
    voice.fresh = 1;
    m->render(3, guarded + 1, &voice);
    assert(body_calls == 4 && body_before[0] == 0 && body_before[1] == 0);
    assert(tone_calls == 4 && tone_before == 0);
    /* A second voice gets separate state without changing the first voice. */
    FW_VOICE_PARAM(4, 0) = 80 << 8;
    m->render(4, guarded + 1, &voice);
    assert(body_calls == 5 && body_state != slot3 && slot3[0] == 132);
    assert(tone_state != tone3 && *tone3 == 1);
    m->render(3, guarded + 1, &voice);
    assert(body_calls == 6 && body_start == 1 && tone_before == 0);
    voice.track = 1;
    m->render(3, guarded + 1, &voice);
    assert(body_calls == 7 && body_before[0] == 0 && body_before[1] == 0 && tone_before == 0);
    FW_VOICE_PARAM(3, 0) = 0;
    x0x_dn_begin();
    assert(slot3[0] == 0 && slot3[1] == 0);
    assert(*tone3 == 0);
    assert(guarded[0] == 12345 && guarded[33] == 12345);
    return 0;
}
