#include <assert.h>
#include <stdint.h>
#include "x0z/controls.h"

struct fake_receiver {
    unsigned calls;
    uint32_t voice;
    enum x0z_control control;
    struct x0z_position position;
};

static void receive(void *context, uint32_t voice, enum x0z_control control, struct x0z_position position)
{
    struct fake_receiver *fake = context;
    ++fake->calls;
    fake->voice = voice;
    fake->control = control;
    fake->position = position;
}

int main(void)
{
    struct fake_receiver a = {0}, b = {0};
    assert(x0z_send_control(X0Z_808, 3, X0Z_DECAY, 0, 32512, receive, &a));
    assert(a.calls == 1 && a.voice == 3 && a.control == X0Z_DECAY);
    assert(a.position.numerator == 0 && a.position.denominator == 32512);
    assert(x0z_send_control(X0Z_808, 3, X0Z_DECAY, 32512, 32512, receive, &a));
    assert(a.position.numerator == a.position.denominator);
    assert(x0z_send_control(X0Z_909, 7, X0Z_TUNE, 16256, 32512, receive, &b));
    assert(b.voice == 7 && b.control == X0Z_TUNE);
    assert(b.position.numerator * 2 == b.position.denominator);
    assert(a.calls == 2 && a.position.numerator == a.position.denominator);
    assert(x0z_send_control(X0Z_808, 3, X0Z_TONE, 1, 32512, receive, &a));
    assert(a.position.numerator == 1 && a.position.denominator == 32512);
    unsigned before = a.calls;
    assert(!x0z_send_control(X0Z_808, 3, X0Z_TUNE, 1, 127, receive, &a));
    assert(!x0z_send_control(X0Z_909, 3, X0Z_TONE, 1, 127, receive, &a));
    assert(!x0z_send_control(X0Z_808, 3, X0Z_DECAY, 1, 0, receive, &a));
    assert(!x0z_send_control(X0Z_808, 3, X0Z_DECAY, 128, 127, receive, &a));
    assert(!x0z_send_control((enum x0z_instrument)99, 3, X0Z_LEVEL, 0, 127, receive, &a));
    assert(!x0z_send_control(X0Z_808, 3, (enum x0z_control)99, 0, 127, receive, &a));
    assert(!x0z_send_control(X0Z_808, 3, X0Z_LEVEL, 0, 127, 0, &a));
    assert(a.calls == before);
    assert(x0z_send_control(X0Z_909, 3, X0Z_LEVEL, UINT32_MAX, UINT32_MAX, receive, &a));
    assert(a.position.numerator == UINT32_MAX && a.position.denominator == UINT32_MAX);
    return 0;
}
