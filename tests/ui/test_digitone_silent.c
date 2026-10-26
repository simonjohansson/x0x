#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "../../machines/digitone/adapter.h"

extern const struct dnm_machine x0z_dn_machine;
extern void x0z_dn_begin(void), x0z_dn_capture(int16_t *words), x0z_dn_ready(int32_t *voices), x0z_dn_end(void);
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
int32_t dnm_knob(int32_t slot, int32_t knob) { (void)slot; (void)knob; assert(0); return 0; }
void dnm_knob_range(int32_t knob, int32_t *lo, int32_t *hi) { (void)knob; (void)lo; (void)hi; assert(0); }
int x0z_selector(uint32_t bank[8][3], uint32_t notice[4], const uint32_t input[4])
{
    assert(bank && notice);
    memcpy(input_seen, input, sizeof input_seen);
    ++calls;
    notice[0] = input[1] >= 16384;
    return input[3] ? 1 : 2;
}
void x0z_silence(int32_t output[32]) { ++zeroes; memset(output, 0, 128); }

int main(void)
{
    const struct dnm_machine *m = &x0z_dn_machine;
    const char *labels[] = {0,0,0,0,0,0,0,0,"TNTUN","DECAY","ATTK",0,0,"MODEL",0,0};
    assert(m->id == 80 && !strcmp(m->name, "X0Z KICKS") && !m->flags && !m->icon);
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
    x0z_dn_begin(); x0z_dn_capture(words); x0z_dn_ready(0);
    m->render(3, guarded + 1, &voice);
    assert(calls == 1 && zeroes == 1);
    assert(input_seen[0] == 3 && input_seen[1] == 32512 && input_seen[2] == 1 && input_seen[3] == 1);
    for (unsigned k = 1; k < 33; ++k) assert(!guarded[k]);
    assert(guarded[0] == 12345 && guarded[33] == 12345);
    x0z_dn_end();
    m->render(3, guarded + 1, &voice);
    assert(calls == 2 && zeroes == 2 && input_seen[3] == 0);
    return 0;
}
