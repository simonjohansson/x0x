#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "adapter.h"

static const struct mk2_param level = {"PROBE", 0}, decay = {"STATE", 64};
static const struct x0z_dn2_binding bindings[] = {
    {0, X0Z_LEVEL, &level}, {8, X0Z_DECAY, &decay}
};

struct receiver {
    uint32_t values[16][DN2_VOICE_PARAMS];
    uint32_t control_calls, notices, sequence, last_control, notice_sequence;
    struct x0z_dn2_notice last;
};

static void receive(void *context, uint32_t slot, enum x0z_control control,
                     struct x0z_position position)
{
    struct receiver *receiver = context;
    assert(slot < 16 && position.denominator == 32512);
    uint32_t parameter = control == X0Z_LEVEL ? 0 : 8;
    assert(control == X0Z_LEVEL || control == X0Z_DECAY);
    receiver->values[slot][parameter] = position.numerator;
    ++receiver->control_calls;
    receiver->last_control = ++receiver->sequence;
}

static void notice(void *context, const struct x0z_dn2_notice *event)
{
    struct receiver *receiver = context;
    receiver->last = *event;
    receiver->notice_sequence = ++receiver->sequence;
    ++receiver->notices;
    assert(receiver->notice_sequence > receiver->last_control);
}

static void trace(const struct receiver *receiver)
{
    const struct x0z_dn2_notice *event = &receiver->last;
    printf("{\"slot\":%u,\"pitch\":%u,\"flags\":%u,\"params\":[",
           (unsigned)event->slot, (unsigned)event->pitch,
           (unsigned)(event->boundary == X0Z_DN2_START_UNCLASSIFIED));
    for (unsigned index = 0; index < DN2_VOICE_PARAMS; ++index)
        printf("%s%u", index ? "," : "", (unsigned)receiver->values[event->slot][index]);
    printf("]}\n");
}

int main(int argc, char **argv)
{
    (void)argv;
    struct mk2_page pages[2] = {0};
    struct receiver receiver = {0};
    uint32_t params[DN2_VOICE_PARAMS] = {0};
    float audio[32];
    for (unsigned index = 0; index < 32; ++index)
        audio[index] = .25f;
    struct dn2_voice_input input = {audio, 15, 60 * 256 + 127, DN2_VOICE_START, params};
    assert(x0z_dn2_pages(X0Z_808, bindings, 2, pages, 2));
    assert(pages[0].knob[0] == &level && pages[1].knob[0] == &decay);
    for (unsigned index = 1; index < 8; ++index)
        assert(!pages[0].knob[index] && !pages[1].knob[index]);
    const uint32_t values[] = {1, 32512, 128, 12345, 0, 256};
    const uint32_t slots[] = {15, 2, 15, 15, 15, 15};
    const uint32_t starts[] = {1, 1, 0, 0, 1, 0};
    for (unsigned index = 0; index < 6; ++index) {
        input.slot = slots[index];
        input.flags = starts[index];
        params[0] = values[index];
        params[8] = 257 + index;
        params[39] = UINT32_MAX; /* An undeclared value must never be consumed. */
        assert(x0z_dn2_deliver(X0Z_808, &input, bindings, 2, receive, notice, &receiver));
        assert(receiver.last.slot == slots[index] && receiver.last.pitch == input.pitch);
        assert(receiver.values[slots[index]][0] == values[index]);
        assert(receiver.values[slots[index]][8] == 257 + index);
        if (argc > 1)
            trace(&receiver);
    }
    assert(receiver.control_calls == 12 && receiver.notices == 6);
    assert(receiver.values[2][0] == 32512 && receiver.values[15][0] == 256);
    for (unsigned index = 0; index < 32; ++index)
        assert(audio[index] == .25f); /* Host AMP is not applied by this adapter. */
    uint32_t calls = receiver.control_calls, events = receiver.notices;
    params[0] = 32513;
    assert(!x0z_dn2_deliver(X0Z_808, &input, bindings, 2, receive, notice, &receiver));
    params[0] = 1;
    params[8] = 32513;
    assert(!x0z_dn2_deliver(X0Z_808, &input, bindings, 2, receive, notice, &receiver));
    params[8] = 1;
    input.slot = 16;
    assert(!x0z_dn2_deliver(X0Z_808, &input, bindings, 2, receive, notice, &receiver));
    input.slot = 15;
    input.pitch = 0x10000;
    assert(!x0z_dn2_deliver(X0Z_808, &input, bindings, 2, receive, notice, &receiver));
    input.pitch = 60 * 256 + 127;
    input.flags = 2;
    assert(!x0z_dn2_deliver(X0Z_808, &input, bindings, 2, receive, notice, &receiver));
    input.flags = 0;
    input.param = 0;
    assert(!x0z_dn2_deliver(X0Z_808, &input, bindings, 2, receive, notice, &receiver));
    input.param = params;
    assert(receiver.control_calls == calls && receiver.notices == events);
    struct x0z_dn2_binding bad[2] = {{0, X0Z_LEVEL, &level}, {0, X0Z_DECAY, &decay}};
    assert(!x0z_dn2_pages(X0Z_808, bad, 2, pages, 2));
    bad[1].parameter = 8;
    bad[1].control = X0Z_LEVEL;
    assert(!x0z_dn2_pages(X0Z_808, bad, 2, pages, 2));
    bad[1].control = X0Z_TUNE;
    assert(!x0z_dn2_deliver(X0Z_808, &input, bad, 2, receive, notice, &receiver));
    assert(!x0z_dn2_pages(X0Z_808, bindings, 2, pages, 1));
    assert(!x0z_dn2_pages(X0Z_808, bindings, 2, pages, 6));
    assert(!x0z_dn2_pages(X0Z_808, bindings, 0, pages, 2));
    bad[1].parameter = 40;
    assert(!x0z_dn2_deliver(X0Z_808, &input, bad, 2, receive, notice, &receiver));
    bad[1].parameter = 8;
    const struct mk2_param invalid_label = {"TOOLONG", 0}, invalid_default = {"TEST", 128};
    bad[1].control = X0Z_DECAY;
    bad[1].knob = &invalid_label;
    assert(!x0z_dn2_pages(X0Z_808, bad, 2, pages, 2));
    bad[1].knob = &invalid_default;
    assert(!x0z_dn2_pages(X0Z_808, bad, 2, pages, 2));
    assert(receiver.control_calls == calls && receiver.notices == events);
    return 0;
}
