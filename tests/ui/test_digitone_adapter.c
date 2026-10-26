#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "../../machines/digitone/adapter.h"

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
    return 0;
}
