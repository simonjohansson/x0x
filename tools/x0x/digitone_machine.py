"""Bounded native DN companion dispatch into a generated diagnostic machine.

ID 127 exists only in ignored test firmware. Initial state and note events
are injected; one SDK live edit executes the stock setter. This is not UI,
allocator or full-OS qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import signal
import struct
from pathlib import Path

from . import cpu, digitone_transport as transport

ROOT = cpu.ROOT
FOLDER = ROOT / "out/dn/machine"
LIVE_TRACK, LIVE_SLOT, LIVE_VALUE = 2, 27, 20001
LOCK_VOICE, LOCK_SLOT, LOCK_VALUE, RESTORE_VALUE = 1, 27, 17003, 12458
LOCK_BITS, SMOOTHER = 0x431f26b4, 0x800046b0
CC_TRACK, CC_NUMBER, CC_VALUE = 0, 1, 127
CC_RAW, CC_TABLE = 0x80004640, 0x80004690
BREATH_NUMBER, BREATH_VALUE = 2, 64
BREATH_RAW, BREATH_TABLE = 0x80004638, 0x80004680
PRESSURE_VALUE = 32
PRESSURE_RAW, PRESSURE_TABLE = 0x80004630, 0x80004670
DRIVER = r'''
#include <stdint.h>
#include "adapter.h"
struct x0x_dn_frame probe_frame;
struct x0x_dn_adapter probe_adapter;
const struct x0x_dn_frame_mapping probe_mapping[] = {{X0X_LEVEL, 119}};
int32_t probe_status[8], probe_model[8];
uint32_t probe_seen[8][10], probe_count[5];
extern void x0x_diagnostic(int32_t *, int32_t);
static void receive(void *context, const struct x0x_dn_input *in)
{
    uint32_t *seen = probe_seen[in->slot];
    (void)context;
    seen[0] = in->value[0].raw;
    seen[1] = in->value[0].position.numerator;
    seen[2] = in->value[0].position.denominator;
    seen[3] = in->slot; seen[4] = in->track; seen[5] = in->generation;
    seen[6] = in->flags; seen[7] = in->pitch;
    seen[8] = in->velocity; seen[9] = in->gate;
    x0x_diagnostic(in->output, in->value[0].raw);
}
void probe_machine_render(int32_t slot, int32_t *block, const struct dnm_voice *voice)
{
    int32_t raw, minimum, maximum;
    probe_status[slot] = 0;
    if (!x0x_dn_frame_read(&probe_frame, slot, 124, &raw, &minimum, &maximum)) return;
    if (x0x_dn_render_frame(&probe_adapter, slot, block, voice, X0X_808,
                            &probe_frame, probe_mapping, 1, receive, 0)) {
        probe_model[slot] = raw;
        probe_status[slot] = 1;
    }
}
static const struct dnm_knob knobs[DNM_KNOBS] = {{0}};
const struct dnm_machine probe_machine = {
    127, "X0X TEST", 0, knobs, probe_machine_render, DNM_OWN_ENV, 0
};
void probe_in(void) { x0x_dn_frame_begin(&probe_frame); ++probe_count[0]; }
void probe_pre(int16_t *words) { x0x_dn_frame_capture(&probe_frame, words); ++probe_count[1]; }
void probe_late(int32_t *voices) { (void)voices; x0x_dn_frame_ready(&probe_frame); ++probe_count[2]; }
void probe_end(void) { x0x_dn_frame_end(&probe_frame); ++probe_count[3]; }
void probe_out(void) { x0x_dn_frame_end(&probe_frame); ++probe_count[4]; }
'''


def validate_case(case):
    """Check final native fractions and real companion metadata separately."""
    if type(case.get("slot")) is not int or not 0 <= case["slot"] < 8:
        raise AssertionError("invalid machine slot")
    expected = case["expected"]
    if len(expected) != 10 or any(type(value) is not int for value in expected):
        raise AssertionError("invalid machine expectation")
    if case["seen"] != expected or any(type(value) is not int for value in case["seen"]):
        raise AssertionError("registered machine lost final controls or companion metadata")
    if (type(case["model"]) is not int or type(case["final_model"]) is not int or
        case["model"] != case["final_model"] or case["output"] != [expected[0]] * 32 or
        any(type(value) is not int for value in case["output"])):
        raise AssertionError("registered machine lost MODEL or diagnostic ASM output")
    if expected[0] == case["target"]:
        raise AssertionError("machine fixture cannot distinguish final controls from targets")


def validate_live_edit(before, after, kit_before, kit_after, tracks):
    """Only the edited kit word and its track's live target words may change."""
    expected = bytearray(before)
    expected_kit = bytearray(kit_before)
    word = struct.pack(">h", LIVE_VALUE)
    for lane, track in enumerate(tracks):
        if track == LIVE_TRACK:
            offset = 18 + 158 * lane + 2 * LIVE_SLOT
            expected[offset:offset + 2] = word
    offset = 0x2c + 326 * LIVE_TRACK + 2 * LIVE_SLOT
    expected_kit[offset:offset + 2] = word
    if after != expected or kit_after != expected_kit:
        raise AssertionError("native live edit changed unintended target/kit bytes or omitted the live store")


def validate_lock_transition(before, after, bits_before, bits_after, smooth_before, smooth_after,
                             kit_before, kit_after, apply):
    """Native locks change one voice's target, lock bit and Q16 smoother state."""
    expected, bits, smooth = bytearray(before), bytearray(bits_before), bytearray(smooth_before)
    value = LOCK_VALUE if apply else RESTORE_VALUE
    struct.pack_into(">h", expected, 18 + 158 * LOCK_VOICE + 2 * LOCK_SLOT, value)
    bit_offset = 12 * LOCK_VOICE + 4 * (LOCK_SLOT // 32)
    old = struct.unpack_from(">I", bits, bit_offset)[0]
    bit = 1 << (LOCK_SLOT % 32)
    struct.pack_into(">I", bits, bit_offset, old | bit if apply else old & ~bit)
    struct.pack_into(">I", smooth, 4 * (9 + 79 * LOCK_VOICE + LOCK_SLOT), value << 16)
    if after != expected or bits_after != bits or smooth_after != smooth or kit_after != kit_before:
        raise AssertionError("native lock transition changed unintended bytes or omitted its target store")


def controller_step(state, raw):
    """Independent Q31 recurrence for the stock controller-producer fixture."""
    if type(state) is not int or not 0 <= state < 1 << 31 or type(raw) is not int or not 0 <= raw <= 32767:
        raise ValueError("invalid controller fixture state/raw word")
    result = (((raw + 32768) << 15) * 0x03d70000 + state * 0x7c290000) >> 31
    return result, (result - 0x40000000 + 0x4000) >> 15


def controller_raw(msb):
    """Stock decoded CC MSB scaling with the fixture's untouched zero LSB cache."""
    if type(msb) is not int or not 0 <= msb <= 127:
        raise ValueError("invalid decoded CC fixture MSB")
    return min(((msb << 8) * 0x8102) >> 15, 32767)


def bounded(image_path, names, stock, omit_live_store=False, omit_lock_store=False,
            omit_controller_producer=False, alias_breath_source=False, alias_pressure_source=False):
    from elekloader import formats
    from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
    from unicorn import m68k_const as regs

    harness = cpu.require_module("emu.harness", "digiemu")
    _, device, _ = formats.load(Path(stock["image"]))
    image = formats.main_image(formats.parse(image_path, device), device)
    machine = harness.Machine()
    try:
        machine.load(image, device.main_load)
        machine.install_isa_patches_scoped(image, device.main_load)
        for address in (0x43000000, names["fw_kit"], 0x47000000, 0x80000000, 0x43400000, 0x431F2928,
                        0x419f0de0, 0x419a93a4,
                        names["fw_lfo_state"], names["fw_voice_pitch"], names["__run_start"]):
            machine.ensure(address)
        uc = machine.uc
        offset = names["__run_load"] - device.main_load
        extent = 4 * names["__run_words"]
        if offset < 0 or offset + extent > len(image):
            raise ValueError("machine diagnostic run image exceeds firmware")
        uc.mem_write(names["__run_start"], image[offset:offset + extent])
        uc.mem_write(names["__bss_start"], bytes(4 * names["__bss_words"]))
        uc.reg_write(regs.UC_M68K_REG_SR, 0x2700)
        read32 = lambda address: int.from_bytes(uc.mem_read(address, 4), "big")
        read_words = lambda address, count: list(struct.unpack(">" + "I" * count, uc.mem_read(address, 4 * count)))
        state = dict(active=None, errors=[], returns=set(), calls=[], order=[], block=-1, frame=None,
                     reads=0, setter=None, native_reads=None, native_stack_end=transport.STACK)
        saved_regs = [*(getattr(regs, "UC_M68K_REG_D" + str(i)) for i in range(2, 8)),
                      *(getattr(regs, "UC_M68K_REG_A" + str(i)) for i in range(2, 7))]

        def checked(fn):
            def callback(*args):
                try:
                    fn(*args)
                except Exception as error:
                    state["errors"].append(str(error)); uc.emu_stop()
            return callback

        def at(address, fn):
            uc.hook_add(UC_HOOK_CODE, checked(fn), begin=address, end=address)

        def returned(_uc, address, _size, _data):
            active = state["active"]
            if active is None or address != active["return"]:
                return
            if uc.reg_read(regs.UC_M68K_REG_A7) != active["stack"] + 4:
                raise AssertionError("machine callback changed caller stack")
            if any(uc.reg_read(key) != value for key, value in active["registers"].items()):
                raise AssertionError("machine callback changed callee registers")
            if active["name"] == "machine":
                if bytes(uc.mem_read(active["voice"], 20)) != active["metadata"]:
                    raise AssertionError("machine callback wrote companion metadata")
                if bytes(uc.mem_read(state["frame"], transport.FRAME_BYTES)) != active["frame"]:
                    raise AssertionError("machine callback wrote native parameter frame")
                state["calls"].append(dict(block=state["block"], slot=active["slot"]))
            state["active"] = None

        def enter(name):
            def callback(_uc, _address, _size, _data):
                if state["active"]:
                    raise AssertionError("nested machine diagnostic callback")
                sp = uc.reg_read(regs.UC_M68K_REG_A7)
                ret = read32(sp)
                if ret not in state["returns"]:
                    at(ret, returned); state["returns"].add(ret)
                active = dict(name=name, stack=sp, **{"return": ret},
                              registers={key: uc.reg_read(key) for key in saved_regs})
                state["active"] = active
                state["order"].append(name)
                if name == "machine":
                    slot, output, voice = read_words(sp + 4, 3)
                    if slot >= 8 or output != names["fw_voices"] + slot * 128:
                        raise AssertionError("companion supplied wrong machine lane/output")
                    active.update(slot=slot, output=output, voice=voice,
                                  metadata=bytes(uc.mem_read(voice, 20)),
                                  readable=read_words(names["probe_frame"], 2) == [state["frame"], 3],
                                  frame=bytes(uc.mem_read(state["frame"], transport.FRAME_BYTES)))
            return callback

        for symbol, label in (("probe_in", "in"), ("probe_pre", "pre"),
                              ("probe_late", "ready"), ("probe_machine_render", "machine"),
                              ("probe_end", "end"), ("probe_out", "out")):
            at(names[symbol], enter(label))

        def extent_for(symbol, size):
            return names[symbol], names[symbol] + size

        def memory(write, address, size):
            active = state["active"]
            if active is None:
                if not write and state["native_reads"] is not None:
                    if not any(first <= address and address + size <= last for first, last in state["native_reads"]):
                        raise AssertionError(f"native control routine read unowned memory {address:#x} at PC {uc.reg_read(regs.UC_M68K_REG_PC):#x}")
                if write and state["setter"] is not None:
                    allowed, writes = state["setter"]
                    if not any(first <= address and address + size <= last for first, last in allowed):
                        raise AssertionError(f"native control routine wrote unowned memory {address:#x}")
                    if not transport.STACK - 2048 <= address or address + size > state["native_stack_end"]:
                        writes.append((address, size))
                return
            owned = [(active["stack"] - 2048, active["stack"] + (0 if write else 16))]
            if active["name"] == "machine":
                slot = active["slot"]
                owned += [(names["probe_status"] + 4 * slot, names["probe_status"] + 4 * (slot + 1))]
                if not write or active["readable"]:
                    owned += [(names["probe_model"] + 4 * slot, names["probe_model"] + 4 * (slot + 1)),
                              (names["probe_seen"] + 40 * slot, names["probe_seen"] + 40 * (slot + 1)),
                              (names["probe_adapter"] + 12 * slot, names["probe_adapter"] + 12 * (slot + 1)),
                              (active["output"], active["output"] + 128)]
                if not write:
                    owned += [extent_for("probe_frame", 8), extent_for("fw_params", 134 * 60),
                              extent_for("probe_mapping", 8), (active["voice"], active["voice"] + 20)]
                    if active["readable"]:
                        owned.append((state["frame"], state["frame"] + transport.FRAME_BYTES))
                    if state["frame"] <= address and address + size <= state["frame"] + transport.FRAME_BYTES:
                        state["reads"] += 1
            else:
                owned += [extent_for("probe_frame", 8), extent_for("probe_count", 20)]
            if not any(first <= address and address + size <= last for first, last in owned):
                raise AssertionError(f"{active['name']} callback {'wrote' if write else 'read'} unowned memory {address:#x}")

        uc.hook_add(UC_HOOK_MEM_READ, checked(lambda _uc, _kind, address, size, _value, _data: memory(False, address, size)))
        uc.hook_add(UC_HOOK_MEM_WRITE, checked(lambda _uc, _kind, address, size, _value, _data: memory(True, address, size)))

        def native(address, args):
            harness.call(machine, address, args, ret_magic=transport.RETURN,
                         stack_top=transport.STACK, limit=transport.LIMIT)
            if state["errors"] or uc.reg_read(regs.UC_M68K_REG_PC) != transport.RETURN:
                raise AssertionError("native machine call stopped: " + str(state["errors"]))

        def execute(first, last, count=transport.LIMIT):
            # An earlier native slice can cache a block beginning at this endpoint.
            stop = uc.hook_add(UC_HOOK_CODE, lambda current, *_: current.emu_stop(), begin=last, end=last)
            try:
                uc.emu_start(first, last, count=count)
            finally:
                uc.hook_del(stop)
            if state["errors"] or uc.reg_read(regs.UC_M68K_REG_PC) != last:
                raise AssertionError("native machine stage stopped: " + str(state["errors"]))

        store = names["SOUND_LIVE"] + 0x5c
        store_bytes = image[store - device.main_load:store - device.main_load + 4]
        if store_bytes != bytes.fromhex("35830812"):
            raise ValueError("native live store differs from reviewed OS 1.44")
        if omit_live_store:
            uc.mem_write(store, bytes.fromhex("4e714e71"))
        lock_apply, lock_restore, lock_store = 0x4009bee8, 0x4009be06, 0x4009bf6a
        for address, expected in ((lock_apply, "4fefffd448d77cfc"),
                                  (lock_restore, "4fefffdc222f0028"),
                                  (lock_store, "3d95ca02"), (0x4009be72, "3396da02")):
            count = len(expected) // 2
            if image[address - device.main_load:address - device.main_load + count] != bytes.fromhex(expected):
                raise ValueError("native lock helper differs from reviewed OS 1.44")
        if omit_lock_store:
            uc.mem_write(lock_store, bytes.fromhex("4e714e71"))
        cc_router, producer_start, producer_end = 0x400edbc2, 0x4009dd92, 0x4009de1a
        cc_records, cc_states = 0x401ab694, 0x40236724
        cc_sources, cc_destinations = (0x80004648, CC_RAW, BREATH_RAW, PRESSURE_RAW), (0x800046a0, CC_TABLE, BREATH_TABLE, PRESSURE_TABLE)
        records = list(struct.unpack(">16I", uc.mem_read(cc_records, 64)))
        expected_records = [word for source, destination, offset in zip(cc_sources, cc_destinations, range(0, 64, 16))
                            for word in (destination, source, 4, cc_states + offset)]
        if (records != expected_records or read32(0x402296f0) & 0x80000 or
            read_words(cc_states, 16) != [0x40000000] * 16 or any(uc.mem_read(CC_TABLE, 8)) or
            any(uc.mem_read(BREATH_TABLE, 8)) or any(uc.mem_read(PRESSURE_TABLE, 8))):
            raise ValueError("native controller records/model/stock initialized Q-states differ from fixture")
        if alias_breath_source:
            uc.mem_write(cc_records + 2 * 16 + 4, struct.pack(">I", CC_RAW))
        if alias_pressure_source:
            uc.mem_write(cc_records + 3 * 16 + 4, struct.pack(">I", BREATH_RAW))
        for address, expected in ((producer_start, "2039402296f0"), (0x4009ddae, "287c03d70000"),
                                  (0x4009ddb4, "2a3c7c290000"), (0x4009de0e, "31823800")):
            count = len(expected) // 2
            if image[address - device.main_load:address - device.main_load + count] != bytes.fromhex(expected):
                raise ValueError("native controller producer differs from reviewed OS 1.44")
        kit, kit_bytes = 0x43000000, 0x2c + 4 * 326
        uc.mem_write(names["fw_kit"], struct.pack(">I", kit))
        uc.mem_write(0x80003f54, struct.pack(">I", kit + 0x14))
        target = names["fw_voice_params"]
        tracks, velocities = [slot % 4 for slot in range(8)], [1 + 18 * slot for slot in range(8)]
        pitches = [(60 + slot) << 16 for slot in range(8)]
        targets = [12345 + slot * 113 for slot in range(8)]
        uc.mem_write(0x80003f5c, struct.pack(">8I", *(kit + 0x2c + 326 * track for track in tracks)))
        event = 0x470D0000
        lock_list = 0x470c0000
        locks = bytearray(0x1c)
        struct.pack_into(">I", locks, 8, 1)
        struct.pack_into(">Hh", locks, 0x14, LOCK_SLOT, LOCK_VALUE)
        uc.mem_write(lock_list, bytes(locks))
        sound = kit + 0x18 + 326 * tracks[LOCK_VOICE]  # Native sound records have a 20-byte header.
        uc.mem_write(sound + 20 + 2 * LOCK_SLOT, struct.pack(">h", RESTORE_VALUE))

        def note(slot):
            uc.mem_write(event, struct.pack(">18I", 0, 0, 0, 0, velocities[slot] << 8, *([0] * 13)))
            native(names["dnm_voice_on"], [slot, tracks[slot], event])

        for slot in range(8):
            uc.mem_write(0x80005444 + 20 * slot, struct.pack(">I", 0x43400000 + 512 * slot))
            voice = target + 18 + 158 * slot
            for parameter, value in ((0, 127 << 8), (27, targets[slot]), (32, 2000 + slot * 1000)):
                uc.mem_write(voice + 2 * parameter, struct.pack(">h", value))
            uc.mem_write(target + 1449 + 148 * slot, struct.pack(">4I", (0x1000 << 16) | 27, 0, 0, 0))
            uc.mem_write(target + 1449 + 148 * slot + 36, struct.pack(">4I", (0x1000 << 16) | 27, 0, 0, 0))
            uc.mem_write(target + 1449 + 148 * slot + 52, struct.pack(">4I", (0x0800 << 16) | 27, 0, 0, 0))
            uc.mem_write(target + 1449 + 148 * slot + 68, struct.pack(">4I", (0x0400 << 16) | 27, 0, 0, 0))
            uc.mem_write(0x431F2928 + 2 * slot, struct.pack(">h", 0x3F80))
            note(slot)
        uc.mem_write(names["fw_voice_pitch"], struct.pack(">8I", *pitches))
        uc.mem_write(names["fw_voice_track"], struct.pack(">8I", *tracks))
        uc.mem_write(names["fw_lfo_state"], bytes(8 * 80))
        # Decoded-router configuration only; raw and settled CC values come from stock code.
        uc.mem_write(0x419f0de0, struct.pack(">I", 1))
        uc.mem_write(0x419a93a4, b"\x01")
        for number, value, raw_address, cache in ((CC_NUMBER, CC_VALUE, CC_RAW, 0x419a93cc),
                                                  (BREATH_NUMBER, BREATH_VALUE, BREATH_RAW, 0x419a93ac)):
            raw_before = bytes(uc.mem_read(0x80004620, 0x30))
            table_before = bytes(uc.mem_read(0x80004650, 0x58))
            state_before = bytes(uc.mem_read(cc_states, 64))
            target_before = bytes(uc.mem_read(target, 0xa40))
            if bytes(uc.mem_read(cache, 1)) != b"\x00":
                raise ValueError("decoded CC fixture requires an untouched zero LSB cache")
            writes = []
            state["setter"] = ([(transport.STACK - 2048, transport.STACK), (transport.STACK + 4, transport.STACK + 24),
                                (raw_address, raw_address + 2), (cache + 1, cache + 2)], writes)
            state["native_stack_end"] = transport.STACK + 24  # Stock tail calls reuse their C argument words.
            state["native_reads"] = [(transport.STACK - 2048, transport.STACK + 24),
                                     (0x419a93a4, 0x419a93a5), (cache, cache + 1),
                                     (0x419f0de0, 0x419f0de4), (names["ev_midi_cc"], names["ev_midi_cc"] + 4)]
            try:
                native(cc_router, [CC_TRACK, number, value, 0, 0])
            finally:
                state["setter"], state["native_reads"] = None, None
                state["native_stack_end"] = transport.STACK
            expected_raw = bytearray(raw_before)
            struct.pack_into(">h", expected_raw, raw_address - 0x80004620, controller_raw(value))
            if (bytes(uc.mem_read(0x80004620, 0x30)) != expected_raw or
                bytes(uc.mem_read(0x80004650, 0x58)) != table_before or
                bytes(uc.mem_read(cc_states, 64)) != state_before or
                bytes(uc.mem_read(target, 0xa40)) != target_before or
                sorted(writes) != sorted(((raw_address, 2), (cache + 1, 1))) or
                bytes(uc.mem_read(cache + 1, 1)) != bytes([value])):
                raise AssertionError(f"decoded native CC{number} did not update only its raw controller/MSB cache")

        pressure_start, pressure_end, pressure_message = 0x400ea1ee, 0x400ea294, 0x470c0100
        for address, expected in ((pressure_start, "4fefffb0700f48d77cfc"),
                                  (0x400ea22c, "45f94009cd96"), (0x400ea266, "203c00008102"),
                                  (0x400ea292, "4e92"), (0x401ce2c8, "400ea1ee")):
            count = len(expected) // 2
            if image[address - device.main_load:address - device.main_load + count] != bytes.fromhex(expected):
                raise ValueError("native channel-pressure slice differs from reviewed OS 1.44")
        # The first channel maps to track0; the auto channel and other tracks do not match.
        uc.mem_write(0x41368d2c, struct.pack(">I", 15))
        uc.mem_write(0x41368d30, struct.pack(">8I", *range(8)))
        message = bytes((0xd0, PRESSURE_VALUE))
        uc.mem_write(pressure_message, message)
        table_before = bytes(uc.mem_read(0x80004650, 0x58))
        state_before = bytes(uc.mem_read(cc_states, 64))
        target_before = bytes(uc.mem_read(target, 0xa40))
        writes = []
        state["setter"] = ([(transport.STACK - 2048, transport.STACK), (PRESSURE_RAW, PRESSURE_RAW + 2)], writes)
        state["native_reads"] = [(transport.STACK - 2048, transport.STACK + 8),
                                 (pressure_message, pressure_message + 2), (0x41368d2c, 0x41368d34)]
        uc.mem_write(transport.STACK, struct.pack(">2I", transport.RETURN, pressure_message))
        uc.reg_write(regs.UC_M68K_REG_SR, 0x2700)
        uc.reg_write(regs.UC_M68K_REG_A7, transport.STACK)
        try:
            execute(pressure_start, pressure_end)
        finally:
            state["setter"], state["native_reads"] = None, None
        struct.pack_into(">h", expected_raw, PRESSURE_RAW - 0x80004620, controller_raw(PRESSURE_VALUE))
        if (uc.reg_read(regs.UC_M68K_REG_A7) != transport.STACK - 88 or
            bytes(uc.mem_read(transport.STACK, 8)) != struct.pack(">2I", transport.RETURN, pressure_message) or
            bytes(uc.mem_read(0x80004620, 0x30)) != expected_raw or
            bytes(uc.mem_read(0x80004650, 0x58)) != table_before or
            bytes(uc.mem_read(cc_states, 64)) != state_before or
            bytes(uc.mem_read(target, 0xa40)) != target_before or
            bytes(uc.mem_read(pressure_message, 2)) != message or writes != [(PRESSURE_RAW, 2)]):
            raise AssertionError("native channel-pressure slice changed unowned state or missed its raw word")

        def produce_controller():
            writes = []
            allowed = [(destination, destination + 8) for destination in cc_destinations]
            allowed.append((cc_states, cc_states + 64))
            state["setter"] = (allowed, writes)
            state["native_reads"] = [(0x402296f0, 0x402296f4), (cc_records, cc_records + 64),
                                     (cc_states, cc_states + 64),
                                     *((source, source + 8) for source in cc_sources)]
            try:
                if not omit_controller_producer:
                    execute(producer_start, producer_end)
            finally:
                state["setter"], state["native_reads"] = None, None
            if (bytes(uc.mem_read(0x80004620, 0x30)) != expected_raw or
                bytes(uc.mem_read(target, 0xa40)) != producer_targets or
                bytes(uc.mem_read(names["fw_voice_track"], 32)) != producer_tracks):
                raise AssertionError("native controller producer changed source/target/voice ownership")
            return writes

        settings = {1: 0x5000, 2: 0, 4: 27 << 8, 5: 2 << 8, 6: 64 << 8,
                    7: 1 << 8, 8: 72 << 8, 12: 0, 16: 64 << 8}
        cases, generations, live_edit, lock_transitions, cc_trace = [], [1] * 8, None, [], []
        expected_cc_state, expected_cc, expected_breath_state, expected_breath = 0x40000000, 0, 0x40000000, 0
        expected_pressure_state, expected_pressure = 0x40000000, 0
        for block in range(7):
            state["block"], state["order"] = block, []
            if block == 1:
                before = bytes(uc.mem_read(target, 0xa40))
                kit_before = bytes(uc.mem_read(kit, kit_bytes))
                cache_before = bytes(uc.mem_read(0x80003f5c, 32))
                smoother_before = bytes(uc.mem_read(0x80005444, 160))
                lanes = [lane for lane, track in enumerate(tracks) if track == LIVE_TRACK]
                kit_word = kit + 0x2c + 326 * LIVE_TRACK + 2 * LIVE_SLOT
                target_words = [target + 18 + 158 * lane + 2 * LIVE_SLOT for lane in lanes]
                writes = []
                state["setter"] = ([(transport.STACK - 2048, transport.STACK),
                                    (kit_word, kit_word + 2),
                                    *((address, address + 2) for address in target_words)], writes)
                try:
                    native(names["core_sound_set"], [LIVE_TRACK, LIVE_SLOT, LIVE_VALUE])
                finally:
                    state["setter"] = None
                validate_live_edit(before, bytes(uc.mem_read(target, 0xa40)), kit_before,
                                   bytes(uc.mem_read(kit, kit_bytes)), tracks)
                if (bytes(uc.mem_read(0x80003f5c, 32)) != cache_before or
                    bytes(uc.mem_read(0x80005444, 160)) != smoother_before or
                    sorted(writes) != sorted((address, 2) for address in [kit_word, *target_words])):
                    raise AssertionError("native live edit changed pointer fixtures or write extents")
                for lane in lanes:
                    targets[lane] = LIVE_VALUE
                live_edit = dict(block=block, track=LIVE_TRACK, sound_slot=LIVE_SLOT,
                                 value=LIVE_VALUE, lanes=lanes, non_stack_writes=len(writes),
                                 sdk_function=hex(names["core_sound_set"]), stock_store=hex(store),
                                 stock_store_bytes=store_bytes.hex())
            if block in (2, 4):
                applying = block == 2
                before = bytes(uc.mem_read(target, 0xa40))
                bits_before = bytes(uc.mem_read(LOCK_BITS, 8 * 12))
                smooth_before = bytes(uc.mem_read(SMOOTHER, 720 * 4))
                kit_before = bytes(uc.mem_read(kit, kit_bytes))
                target_word = target + 18 + 158 * LOCK_VOICE + 2 * LOCK_SLOT
                bit_word = LOCK_BITS + 12 * LOCK_VOICE + 4 * (LOCK_SLOT // 32)
                smooth_word = SMOOTHER + 4 * (9 + 79 * LOCK_VOICE + LOCK_SLOT)
                writes = []
                state["setter"] = ([(transport.STACK - 2048, transport.STACK),
                                    (target_word, target_word + 2),
                                    (bit_word, bit_word + 4), (smooth_word, smooth_word + 4)], writes)
                state["native_reads"] = [(transport.STACK - 2048, transport.STACK + 16),
                                         (LOCK_BITS + 12 * LOCK_VOICE, LOCK_BITS + 12 * (LOCK_VOICE + 1)),
                                         (lock_list, lock_list + len(locks)) if applying else
                                         (sound + 20 + 2 * LOCK_SLOT, sound + 22 + 2 * LOCK_SLOT)]
                try:
                    native(lock_apply if applying else lock_restore,
                           [LOCK_VOICE, lock_list, target] if applying else [LOCK_VOICE, target, sound])
                finally:
                    state["setter"], state["native_reads"] = None, None
                validate_lock_transition(before, bytes(uc.mem_read(target, 0xa40)),
                                         bits_before, bytes(uc.mem_read(LOCK_BITS, 8 * 12)),
                                         smooth_before, bytes(uc.mem_read(SMOOTHER, 720 * 4)),
                                         kit_before, bytes(uc.mem_read(kit, kit_bytes)), applying)
                if sorted(writes) != sorted(((target_word, 2), (bit_word, 4), (smooth_word, 4))):
                    raise AssertionError("native lock helper write extents diverged")
                if bytes(uc.mem_read(lock_list, len(locks))) != locks:
                    raise AssertionError("native lock helper changed its prepared list")
                targets[LOCK_VOICE] = LOCK_VALUE if applying else RESTORE_VALUE
                lock_transitions.append(dict(block=block, kind="apply" if applying else "restore",
                                             voice=LOCK_VOICE, sound_slot=LOCK_SLOT, value=targets[LOCK_VOICE],
                                             native_function=hex(lock_apply if applying else lock_restore),
                                             non_stack_writes=len(writes)))
            if block == 2:
                note(3)  # Same-track retrigger through the actual companion entry.
            if block == 3:
                tracks[4] = 3; generations[4] += 1; note(4)
                uc.mem_write(names["fw_voice_track"], struct.pack(">8I", *tracks))
            uc.mem_write(names["fw_gate_off"], struct.pack(">I", 1 << 5 if block >= 4 else 0))
            uc.mem_write(target + 18 + 158 * 7, struct.pack(">h", 0 if block == 4 else 127 << 8))
            bank = 0x80001FA4 + 0xA90 * (block % 2)
            frame = bank + 80; words = frame + 18
            state["frame"] = words
            uc.reg_write(regs.UC_M68K_REG_A6, 0x470E0000)
            native(names["core_render_in"], [])
            execute(0x4009D1DE, 0x4009D1E4, 1)
            native(0x4009BF86, [frame, target])
            smoothed = [int.from_bytes(uc.mem_read(words + 158 * lane + 54, 2), "big") for lane in range(8)]
            if block >= 2 and smoothed[LOCK_VOICE] != targets[LOCK_VOICE]:
                raise AssertionError("native lock apply/restore did not settle its smoother immediately")
            for slot in range(8):
                for parameter, value in settings.items():
                    uc.mem_write(words + 158 * slot + 2 * parameter, struct.pack(">h", value))
            used_cc = list(struct.unpack(">4h", uc.mem_read(CC_TABLE, 8)))
            if used_cc != [expected_cc, 0, 0, 0]:
                raise AssertionError("native CC controller used the wrong block's settled table")
            used_breath = list(struct.unpack(">4h", uc.mem_read(BREATH_TABLE, 8)))
            if used_breath != [expected_breath, 0, 0, 0]:
                raise AssertionError("native breath controller used the wrong block or source")
            used_pressure = list(struct.unpack(">4h", uc.mem_read(PRESSURE_TABLE, 8)))
            if used_pressure != [expected_pressure, 0, 0, 0]:
                raise AssertionError("native pressure controller used the wrong block or source")
            native(names["core_render_params"], [frame])
            controllers = [int.from_bytes(uc.mem_read(words + 158 * lane + 54, 2), "big") for lane in range(8)]
            expected_controllers = [value + 2032 + (((expected_cc >> 3) + (expected_breath >> 4) + (expected_pressure >> 5)) if track == CC_TRACK else 0)
                                    for value, track in zip(smoothed, tracks)]
            if controllers != expected_controllers:
                raise AssertionError("native CC controller changed the wrong voice or lost its fractional contribution")
            native(0x400FED62, [frame, 14400, 255 if block == 0 else 0, 0, 0xFFFFFFFF, 0xFFFFFFFF])
            producer_targets = bytes(uc.mem_read(target, 0xa40))
            producer_tracks = bytes(uc.mem_read(names["fw_voice_track"], 32))
            producer_writes = produce_controller()
            expected_cc_state, expected_after_cc = controller_step(expected_cc_state, controller_raw(CC_VALUE))
            expected_breath_state, expected_after_breath = controller_step(expected_breath_state, controller_raw(BREATH_VALUE))
            expected_pressure_state, expected_after_pressure = controller_step(expected_pressure_state, controller_raw(PRESSURE_VALUE))
            expected_states = [0x40000000] * 16
            expected_states[4] = expected_cc_state
            expected_states[8] = expected_breath_state
            expected_states[12] = expected_pressure_state
            cc_trace.append(dict(block=block, used=used_cc, produced=list(struct.unpack(">4h", uc.mem_read(CC_TABLE, 8))),
                                 state=read_words(cc_states, 16), expected_states=expected_states,
                                 expected_produced=[expected_after_cc, 0, 0, 0], writes=producer_writes,
                                 breath_used=used_breath, breath_produced=list(struct.unpack(">4h", uc.mem_read(BREATH_TABLE, 8))),
                                 expected_breath_produced=[expected_after_breath, 0, 0, 0],
                                 pressure_used=used_pressure, pressure_produced=list(struct.unpack(">4h", uc.mem_read(PRESSURE_TABLE, 8))),
                                 expected_pressure_produced=[expected_after_pressure, 0, 0, 0],
                                 affected_lanes=[lane for lane, track in enumerate(tracks) if track == CC_TRACK]))
            expected_cc = expected_after_cc
            expected_breath = expected_after_breath
            expected_pressure = expected_after_pressure
            uc.reg_write(regs.UC_M68K_REG_A6, 0x470E0000)
            uc.reg_write(regs.UC_M68K_REG_A2, bank); uc.reg_write(regs.UC_M68K_REG_D6, 0)
            uc.mem_write(0x470E0000 - 108, struct.pack(">I", frame))
            uc.reg_write(regs.UC_M68K_REG_A7, transport.STACK)
            execute(0x4009DE1A, 0x4009DF52)
            expected_frame = bytes(uc.mem_read(words, transport.FRAME_BYTES))
            outputs = [0x10000000 + slot * 0x10000 + sample for slot in range(8) for sample in range(32)]
            uc.mem_write(names["fw_voices"], struct.pack(">256I", *outputs))
            previous_seen = bytes(uc.mem_read(names["probe_seen"], 320))
            previous_adapter = bytes(uc.mem_read(names["probe_adapter"], 96))
            previous_model = bytes(uc.mem_read(names["probe_model"], 32))
            if block == 5:
                uc.mem_write(names["probe_frame"], struct.pack(">2I", 0, 1))
            native(names["core_render_voices"], [frame, 0, 0])
            if bytes(uc.mem_read(words, transport.FRAME_BYTES)) != expected_frame:
                raise AssertionError("companion dispatch changed the parameter frame")
            expected_slots = list(range(7 if block == 4 else 8))
            if state["order"] != ["in", "pre", "ready", *(["machine"] * len(expected_slots)), "end"]:
                raise AssertionError("registered machine did not run between ready/end events")
            if any(uc.mem_read(names["probe_frame"], 8)):
                raise AssertionError("machine frame remained available after companion pass")
            if [row["slot"] for row in state["calls"] if row["block"] == block] != expected_slots:
                raise AssertionError("actual companion dispatched unexpected slots")
            if block == 5:
                if (bytes(uc.mem_read(names["probe_seen"], 320)) != previous_seen or
                    bytes(uc.mem_read(names["probe_adapter"], 96)) != previous_adapter or
                    bytes(uc.mem_read(names["probe_model"], 32)) != previous_model or
                    read_words(names["fw_voices"], 256) != outputs or
                    any(read_words(names["probe_status"], 8))):
                    raise AssertionError("missing production frame changed receiver/state/audio")
            else:
                for slot in expected_slots:
                    level = struct.unpack_from(">h", expected_frame, 158 * slot + 54)[0]
                    model = struct.unpack_from(">h", expected_frame, 158 * slot + 64)[0]
                    fresh = int(block == 0 or block == 2 and slot == 3 or block == 3 and slot == 4)
                    flags = (1 if block == 0 or block == 3 and slot == 4 else 0) | (2 if fresh else 0)
                    case = dict(block=block, slot=slot,
                                expected=[level, level, 32512, slot, tracks[slot], generations[slot], flags,
                                          pitches[slot], velocities[slot], int(not (block >= 4 and slot == 5))],
                                seen=read_words(names["probe_seen"] + 40 * slot, 10),
                                model=read32(names["probe_model"] + 4 * slot), final_model=model,
                                output=read_words(names["fw_voices"] + 128 * slot, 32),
                                target=targets[slot], smoothed=smoothed[slot])
                    if read32(names["probe_status"] + 4 * slot) != 1:
                        raise AssertionError("registered machine rejected a valid final frame")
                    validate_case(case); cases.append(case)
                if block == 4 and read_words(names["fw_voices"] + 7 * 128, 32) != outputs[224:]:
                    raise AssertionError("unselected FM voice changed in companion dispatch")
            uc.reg_write(regs.UC_M68K_REG_A6, 0x470E0000)
            native(names["core_render_out"], [])
            if state["order"][-1] != "out" or any(uc.mem_read(names["probe_frame"], 8)):
                raise AssertionError("machine diagnostic missed render exit invalidation")
        for lane in live_edit["lanes"]:
            ramp = [case["smoothed"] for case in cases if case["slot"] == lane and case["block"] >= 1]
            if (len(ramp) != 5 or any(not 0 < value < LIVE_VALUE for value in ramp) or
                any(a >= b for a, b in zip(ramp, ramp[1:])) or not any(value % 256 for value in ramp)):
                raise AssertionError("native live edit lost its fractional smoothing ramp")
        if len(state["calls"]) != 55 or len(cases) != 47 or state["reads"] != 94:
            raise AssertionError("machine callback/delivery/frame-read counts diverged")
        expected_writes = sorted([(destination + 2 * channel, 2) for destination in cc_destinations for channel in range(4)] +
                                 [(cc_states + 4 * index, 4) for index in range(16)])
        for row in cc_trace:
            if (row["state"] != row["expected_states"] or row["produced"] != row["expected_produced"] or
                row["breath_produced"] != row["expected_breath_produced"] or
                row["pressure_produced"] != row["expected_pressure_produced"] or
                sorted(row["writes"]) != expected_writes):
                raise AssertionError("native CC controller producer Q31/table/write trace diverged")
        return dict(cases=cases, machine_callbacks=len(state["calls"]), guarded_frame_reads=state["reads"],
                    live_edit=live_edit, lock_transitions=lock_transitions,
                    cc_trace=cc_trace, decoded_cc=dict(router=hex(cc_router), track=CC_TRACK, cc=CC_NUMBER,
                                                     value=CC_VALUE, raw=controller_raw(CC_VALUE), non_stack_writes=2,
                                                     initial_q_state="stock image initializes each state to0x40000000"),
                    decoded_breath=dict(router=hex(cc_router), track=CC_TRACK, cc=BREATH_NUMBER,
                                        value=BREATH_VALUE, raw=controller_raw(BREATH_VALUE), non_stack_writes=2,
                                        mapping_amount="0x0800 (1/16)"),
                    decoded_pressure=dict(slice_start=hex(pressure_start), slice_stop=hex(pressure_end),
                                          message=message.hex(), channel=0, pressure=PRESSURE_VALUE,
                                          channel_to_track=list(range(8)), auto_channel=15,
                                          raw=controller_raw(PRESSURE_VALUE), raw_address=hex(PRESSURE_RAW),
                                          settled_address=hex(PRESSURE_TABLE), non_stack_writes=1,
                                          mapping_offset=68, mapping_amount="0x0400 (1/32)", full_handler_completed=False),
                    cc_stage_order=["decoded CC1/CC2 and prepared channel-pressure slice before block0", "controllers consume previous settled tables",
                                    "LFO", "controller producer updates table/Q-state", "final stage", "registered callback"],
                    blocks=7, instructions_per_call_or_stage=transport.LIMIT,
                    event_order=["in", "pre", "ready (40)", "companion/machine (50)", "end (60)", "out"],
                    missing_frame_block=5, unselected_fm_slot=dict(block=4, slot=7))
    finally:
        machine.close()


def verify():
    image, names, stock = transport.build(FOLDER, machine_driver=DRIVER)
    result = bounded(image, names, stock)
    marker = "if (!x0x_dn_frame_read(&probe_frame, slot, 124, &raw, &minimum, &maximum)) return;"
    if DRIVER.count(marker) != 1:
        raise ValueError("machine missing-frame mutation marker is not unique")
    altered = DRIVER.replace(marker, """if (!x0x_dn_frame_read(&probe_frame, slot, 124, &raw, &minimum, &maximum)) {
        volatile int32_t *value = &probe_model[slot];
        int32_t saved = *value;
        *value = 12345; *value = saved;
        return;
    }""")
    bad_image, bad_names, bad_stock = transport.build(FOLDER / "transient-write", machine_driver=altered)
    try:
        bounded(bad_image, bad_names, bad_stock)
    except AssertionError as error:
        if "machine callback wrote unowned memory" not in str(error):
            raise
        rejected = [dict(name="transient MODEL write on missing frame", reason=str(error))]
    else:
        raise AssertionError("machine diagnostic accepted a transient write without a frame")
    try:
        bounded(image, names, stock, omit_live_store=True)
    except AssertionError as error:
        if "omitted the live store" not in str(error):
            raise
        rejected.append(dict(name="stock live target store replaced by NOPs", reason=str(error)))
    else:
        raise AssertionError("machine diagnostic accepted a kit-only edit")
    try:
        bounded(image, names, stock, omit_lock_store=True)
    except AssertionError as error:
        if "native lock transition changed unintended bytes or omitted its target store" not in str(error):
            raise
        rejected.append(dict(name="stock lock target store replaced by NOPs", reason=str(error)))
    else:
        raise AssertionError("machine diagnostic accepted an omitted lock target store")
    try:
        bounded(image, names, stock, omit_controller_producer=True)
    except AssertionError as error:
        if "native CC controller used the wrong block's settled table" not in str(error):
            raise
        rejected.append(dict(name="native controller producer omitted", reason=str(error)))
    else:
        raise AssertionError("machine diagnostic accepted an omitted controller producer")
    try:
        bounded(image, names, stock, alias_breath_source=True)
    except AssertionError as error:
        if "native breath controller used the wrong block or source" not in str(error):
            raise
        rejected.append(dict(name="native breath producer aliases mod-wheel raw source", reason=str(error)))
    else:
        raise AssertionError("machine diagnostic accepted an aliased breath controller source")
    try:
        bounded(image, names, stock, alias_pressure_source=True)
    except AssertionError as error:
        if "native pressure controller used the wrong block or source" not in str(error):
            raise
        rejected.append(dict(name="native pressure producer aliases breath raw source", reason=str(error)))
    else:
        raise AssertionError("machine diagnostic accepted an aliased pressure controller source")
    result.update(rejected_mutations=rejected, kind="registered DN machine / native companion diagnostic", stock=stock,
                  emulator_revision=cpu.revision(ROOT / "vendor/digiemu"), project_revision=cpu.revision(ROOT),
                  elekloader_revision=stock["sdk_revision"],
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  driver_sha256=hashlib.sha256(DRIVER.encode()).hexdigest(),
                  adapter_sha256=hashlib.sha256((ROOT / "machines/digitone/adapter.c").read_bytes()).hexdigest(),
                  adapter_header_sha256=hashlib.sha256((ROOT / "machines/digitone/adapter.h").read_bytes()).hexdigest(),
                  controls_sha256=hashlib.sha256((ROOT / "src/controls.c").read_bytes()).hexdigest(),
                  controls_header_sha256=hashlib.sha256((ROOT / "include/x0x/controls.h").read_bytes()).hexdigest(),
                  firmware_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                  fixture_machine_id=127, production_machine_id_adopted=False,
                  live_edit_source="actual SDK/stock live setter with injected kit and voice ownership; not a UI/MIDI gesture",
                  lock_source="direct stock apply/restore helpers with prepared SDK-format list and sound record; not sequencer/event delivery",
                  cc_source="decoded stock CC1/CC2 router, separate stock Q31 producer states after controllers/LFO, next-block summed controller consumption; receive/mapping configuration injected",
                  pressure_source="prepared2-byte channel-pressure handler slice through real first-channel lookup/scaling/raw setter; stops before UI telemetry and does not complete the handler",
                  injection="initial target sound words, kit/ownership pointers, per-voice controller value and all mappings, receive/initialized flags, prepared pressure message/channel configuration, settled LFO settings, companion note events, pitch/track/gate state",
                  envelope="DNM_OWN_ENV bypasses companion AMP/velocity; these are covered by separate companion tests",
                  note_order="fixture calls dnm_voice_on before dispatch; native core_voice_on runs after core_render_voices, so START/frame alignment is unqualified",
                  unqualified=["MODEL selector ASM and complete mappings", "raw MIDI packets, other controllers, native UI and sequencer lock sources", "native allocator and START/frame ownership",
                               "full-OS dispatcher/audio timing", "physical deadlines and kick fidelity"])
    return result


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    signal.alarm(150)
    try:
        report = dict(status="passed", **verify())
        (FOLDER / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report)); return 0
    except cpu.Unavailable as error:
        print(json.dumps(dict(status="unavailable", reason=str(error)))); return 77
    except (AssertionError, RuntimeError, ValueError, OSError) as error:
        print(json.dumps(dict(status="failed", reason=str(error)))); return 1
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    raise SystemExit(main())
