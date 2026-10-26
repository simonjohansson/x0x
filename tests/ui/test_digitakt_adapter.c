#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "machines/digitakt/adapter.h"

volatile int16_t fw_voice_params[53 * 8];
volatile int32_t fw_voice_note[8];
volatile int16_t fw_voice_vel[8];
volatile uint32_t fw_voice_start;
volatile int32_t fw_amp_env[3 * 8];
static unsigned reads;

int32_t cm_src_value(int32_t track, int32_t parameter)
{
    ++reads;
    assert(track >= 0 && track < 8 && parameter >= 0 && parameter < 8);
    return fw_voice_params[53 * track + parameter];
}

struct received {
    unsigned calls;
    uint32_t track;
    enum x0z_control control;
    struct x0z_position position;
};

static void receive(void *context, uint32_t track, enum x0z_control control,
                     struct x0z_position position)
{
    struct received *result = context;
    ++result->calls;
    result->track = track;
    result->control = control;
    result->position = position;
}

int main(void)
{
    const struct x0z_dt_binding mapping = {2, X0Z_DECAY, 0, 32512};
    struct x0z_dt_snapshot snapshot = {0};
    struct received a = {0}, b = {0};
    fw_voice_params[53 * 3 + 2] = 16257;
    fw_voice_note[3] = (60 << 16) + 123;
    fw_voice_vel[3] = 20001;
    fw_voice_start = 1u << 3;
    fw_amp_env[9] = 7;
    fw_amp_env[10] = 0x12345678;
    assert(x0z_dt_capture(3, X0Z_808, &mapping, 1, &snapshot, receive, &a));
    assert(a.calls == 1 && a.track == 3 && a.control == X0Z_DECAY);
    assert(a.position.numerator == 16257 && a.position.denominator == 32512);
    assert(snapshot.track == 3 && snapshot.native_start == 1);
    assert(snapshot.note == (60 << 16) + 123 && snapshot.velocity == 20001);
    assert(snapshot.amp_phase == 7 && snapshot.amp_level == 0x12345678);

    fw_voice_params[53 * 7 + 2] = 32512;
    fw_voice_vel[7] = 32512;
    assert(x0z_dt_capture(7, X0Z_808, &mapping, 1, &snapshot, receive, &b));
    assert(b.track == 7 && b.position.numerator == b.position.denominator);
    assert(snapshot.native_start == 0 && a.calls == 1 && a.position.numerator == 16257);
    fw_voice_start = 0;
    fw_voice_params[53 * 3 + 2] = 0;
    assert(x0z_dt_capture(3, X0Z_808, &mapping, 1, &snapshot, receive, &a));
    assert(a.position.numerator == 0 && snapshot.native_start == 0);

    const struct x0z_dt_binding signed_range = {0, X0Z_TUNE, -6144, 6144};
    fw_voice_params[0] = -6143;
    assert(x0z_dt_capture(0, X0Z_909, &signed_range, 1, &snapshot, receive, &b));
    assert(b.position.numerator == 1 && b.position.denominator == 12288);

    struct x0z_dt_snapshot untouched;
    memset(&untouched, 0x5a, sizeof untouched);
    struct x0z_dt_snapshot before = untouched;
    const struct x0z_dt_binding pair[] = {{2, X0Z_DECAY, 0, 32512}, {0, X0Z_TUNE, -6144, 6144}};
    unsigned calls = a.calls;
    assert(!x0z_dt_capture(3, X0Z_808, pair, 2, &untouched, receive, &a));
    assert(a.calls == calls && memcmp(&untouched, &before, sizeof before) == 0);
    struct x0z_dt_binding invalid = mapping;
    invalid.maximum = invalid.minimum;
    assert(!x0z_dt_capture(3, X0Z_808, &invalid, 1, &untouched, receive, &a));
    invalid = mapping; invalid.parameter = 8;
    assert(!x0z_dt_capture(3, X0Z_808, &invalid, 1, &untouched, receive, &a));
    invalid = mapping; invalid.minimum = INT32_MIN;
    assert(!x0z_dt_capture(3, X0Z_808, &invalid, 1, &untouched, receive, &a));
    fw_voice_vel[3] = -1;
    assert(!x0z_dt_capture(3, X0Z_808, &mapping, 1, &untouched, receive, &a));
    fw_voice_vel[3] = 20001;
    unsigned before_reads = reads;
    assert(!x0z_dt_capture(8, X0Z_808, &mapping, 1, &untouched, receive, &a));
    assert(reads == before_reads && a.calls == calls);
    assert(x0z_dt_capture(3, X0Z_808, 0, 0, &snapshot, 0, 0));
    return 0;
}
