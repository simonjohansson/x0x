#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "../../machines/digitone/adapter.h"

#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
#define WORD(p, o, v) [60*(p)+(o)] = (v)&255, [60*(p)+(o)+1] = ((v)>>8)&255
#else
#define WORD(p, o, v) [60*(p)+(o)+2] = ((v)>>8)&255, [60*(p)+(o)+3] = (v)&255
#endif
#define RECORD(p, slot, hi) WORD(p, 4, slot), WORD(p, 12, hi)
const uint8_t fw_params[134 * 60] __attribute__((aligned(4))) = {
    RECORD(119, 27, 32512), RECORD(120, 28, 32512), RECORD(121, 29, 32512),
    RECORD(124, 32, 32512), RECORD(133, 79, 32512)
};

static int32_t raw[8][32], low[32], high[32];
static unsigned calls;
static struct x0z_dn_input seen;

int32_t dnm_knob(int32_t slot, int32_t knob) { return raw[slot][knob]; }
void dnm_knob_range(int32_t knob, int32_t *minimum, int32_t *maximum)
{
    *minimum = low[knob]; *maximum = high[knob];
}
static void receive(void *context, const struct x0z_dn_input *input)
{
    assert(context == &seen);
    seen = *input;
    ++calls;
}

static void delivered(void)
{
    struct x0z_dn_frame frame = {0};
    struct x0z_dn_adapter adapter = {0}, before;
    struct dnm_voice voice = {60 << 16, 37, 1, 2, 1};
    const struct x0z_dn_frame_mapping map[] = {
        {X0Z_LEVEL,119}, {X0Z_TONE,120}, {X0Z_DECAY,121}
    };
    int16_t words[2][8 * CORE_PARAMS_VOICE] = {{0}}, saved[8 * CORE_PARAMS_VOICE];
    int32_t output[32] = {0}, value = -1, lo = -1, hi = -1;
    unsigned bank, slot, previous;
    for (bank = 0; bank < 2; ++bank) {
        for (slot = 0; slot < 8; ++slot) {
            words[bank][79 * slot + 27] = 370 + 360 * bank + slot;
            words[bank][79 * slot + 28] = 12345 + slot;
            words[bank][79 * slot + 29] = 16256 + slot;
            words[bank][79 * slot + 32] = slot & 1 ? 16384 : 16383;
        }
        memcpy(saved, words[bank], sizeof(saved));
        x0z_dn_frame_begin(&frame);
        x0z_dn_frame_capture(&frame, words[bank]);
        assert(!x0z_dn_frame_read(&frame, 0, 119, &value, &lo, &hi));
        x0z_dn_frame_ready(&frame);
        for (slot = 0; slot < 8; ++slot) {
            assert(x0z_dn_render_frame(&adapter, slot, output, &voice, X0Z_808,
                                       &frame, map, 3, receive, &seen));
            assert(seen.slot == slot && seen.value[0].raw == 370 + (int32_t)(360 * bank + slot));
            assert(seen.value[0].position.numerator == (uint32_t)seen.value[0].raw);
            assert(seen.value[0].position.denominator == 32512);
            assert(seen.value[1].raw == 12345 + (int32_t)slot);
            assert(x0z_dn_frame_read(&frame, slot, 124, &value, &lo, &hi));
            assert(value == (slot & 1 ? 16384 : 16383) && lo == 0 && hi == 32512);
        }
        assert(!memcmp(saved, words[bank], sizeof(saved)));
        before = adapter; previous = calls;
        const struct x0z_dn_frame_mapping invalid[] = {{X0Z_LEVEL,119}, {X0Z_TONE,133}};
        assert(!x0z_dn_render_frame(&adapter, 0, output, &voice, X0Z_808,
                                    &frame, invalid, 2, receive, &seen));
        assert(calls == previous && !memcmp(&before, &adapter, sizeof(adapter)));
        for (slot = 0; slot < 32; ++slot) assert(output[slot] == 0);
        assert(!x0z_dn_frame_read(&frame, -1, 119, &value, &lo, &hi));
        assert(!x0z_dn_frame_read(&frame, 8, 119, &value, &lo, &hi));
        assert(!x0z_dn_frame_read(&frame, 0, 106, &value, &lo, &hi));
        assert(!x0z_dn_frame_read(&frame, 0, 134, &value, &lo, &hi));
        assert(!x0z_dn_frame_read(&frame, 0, 107, &value, &lo, &hi));
        assert(!x0z_dn_frame_read(&frame, 0, 119, 0, &lo, &hi));
        words[bank][27] = -1;
        value = lo = hi = -123;
        assert(!x0z_dn_frame_read(&frame, 0, 119, &value, &lo, &hi));
        assert(value == -123 && lo == -123 && hi == -123);
        words[bank][27] = 32513;
        assert(!x0z_dn_frame_read(&frame, 0, 119, &value, &lo, &hi));
        x0z_dn_frame_end(&frame);
        assert(!frame.words && !frame.phase);
        assert(!x0z_dn_frame_read(&frame, 0, 119, &value, &lo, &hi));
    }
    x0z_dn_frame_begin(&frame);
    x0z_dn_frame_ready(&frame); /* Missing capture must not reuse the previous bank. */
    assert(!x0z_dn_frame_read(&frame, 0, 119, &value, &lo, &hi));
    x0z_dn_frame_begin(&frame);
    x0z_dn_frame_capture(&frame, words[0]);
    x0z_dn_frame_capture(&frame, words[1]); /* Duplicate capture poisons this block. */
    x0z_dn_frame_ready(&frame);
    assert(!frame.words && !frame.phase);
    x0z_dn_frame_capture(&frame, words[0]); /* No render entry. */
    assert(!frame.words && !frame.phase);
    before = adapter; previous = calls;
    assert(!x0z_dn_render_frame(&adapter, 0, output, &voice, X0Z_808,
                                &frame, map, 3, receive, &seen));
    assert(calls == previous && !memcmp(&before, &adapter, sizeof(adapter)));
}

int main(void)
{
    struct x0z_dn_adapter adapter = {0}, before;
    struct dnm_voice voice = {60 << 16, 37, 1, 2, 1};
    const struct x0z_dn_mapping map[] = {{X0Z_LEVEL, 8}, {X0Z_TONE, 4}, {X0Z_DECAY, 9}};
    int32_t output[32], i;
    for (i = 0; i < 32; ++i) { high[i] = 32512; output[i] = 0x12345678; }
    low[4] = -6656; high[4] = 6656;
    raw[3][8] = 12345; raw[3][4] = -1; raw[3][9] = 16256;
    assert(x0z_dn_render(&adapter, 3, output, &voice, X0Z_808, map, 3, receive, &seen));
    assert(calls == 1 && seen.slot == 3 && seen.track == 2 && seen.generation == 1);
    assert(seen.flags == (X0Z_DN_ASSIGNED | X0Z_DN_NATIVE_START));
    assert(seen.pitch == 60 << 16 && seen.velocity == 37 && seen.gate == 1);
    assert(seen.value[0].raw == 12345 && seen.value[0].position.numerator == 12345);
    assert(seen.value[0].position.denominator == 32512);
    assert(seen.value[1].raw == -1 && seen.value[1].position.numerator == 6655);
    assert(seen.value[1].position.denominator == 13312);
    for (i = 0; i < 32; ++i) assert(output[i] == 0x12345678);
    voice.fresh = 0; voice.velocity = 127; voice.gate = 0;
    assert(x0z_dn_render(&adapter, 3, output, &voice, X0Z_808, map, 3, receive, &seen));
    assert(seen.flags == 0 && seen.generation == 1 && seen.velocity == 127 && seen.gate == 0);
    voice.fresh = 1;
    assert(x0z_dn_render(&adapter, 3, output, &voice, X0Z_808, map, 3, receive, &seen));
    assert(seen.flags == X0Z_DN_NATIVE_START && seen.generation == 1);
    voice.track = 1;
    assert(x0z_dn_render(&adapter, 3, output, &voice, X0Z_808, map, 3, receive, &seen));
    assert(seen.flags == 3 && seen.generation == 2);
    assert(x0z_dn_forget(&adapter, 3));
    assert(x0z_dn_render(&adapter, 3, output, &voice, X0Z_808, map, 3, receive, &seen));
    assert(seen.generation == 3 && (seen.flags & X0Z_DN_ASSIGNED));
    assert(adapter.slot[2].active == 0);
    before = adapter;
    unsigned previous = calls;
    for (i = -1; i <= 8; i += 9)
        assert(!x0z_dn_render(&adapter, i, output, &voice, X0Z_808, map, 3, receive, &seen));
    raw[3][4] = 6657;
    assert(!x0z_dn_render(&adapter, 3, output, &voice, X0Z_808, map, 3, receive, &seen));
    raw[3][4] = -1;
    const struct x0z_dn_mapping duplicate[] = {{X0Z_LEVEL, 8}, {X0Z_LEVEL, 9}};
    assert(!x0z_dn_render(&adapter, 3, output, &voice, X0Z_808, duplicate, 2, receive, &seen));
    const struct x0z_dn_mapping empty[] = {{X0Z_LEVEL, 20}};
    high[20] = 0;
    assert(!x0z_dn_render(&adapter, 3, output, &voice, X0Z_808, empty, 1, receive, &seen));
    const struct x0z_dn_mapping wrong[] = {{X0Z_TUNE, 8}};
    assert(!x0z_dn_render(&adapter, 3, output, &voice, X0Z_808, wrong, 1, receive, &seen));
    assert(calls == previous && memcmp(&before, &adapter, sizeof(adapter)) == 0);
    assert(!x0z_dn_forget(&adapter, 8));
    delivered();
    return 0;
}
