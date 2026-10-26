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
DRIVER = r'''
#include <stdint.h>
#include "adapter.h"
struct x0z_dn_frame probe_frame;
struct x0z_dn_adapter probe_adapter;
const struct x0z_dn_frame_mapping probe_mapping[] = {{X0Z_LEVEL, 119}};
int32_t probe_status[8], probe_model[8];
uint32_t probe_seen[8][10], probe_count[5];
extern void x0z_diagnostic(int32_t *, int32_t);
static void receive(void *context, const struct x0z_dn_input *in)
{
    uint32_t *seen = probe_seen[in->slot];
    (void)context;
    seen[0] = in->value[0].raw;
    seen[1] = in->value[0].position.numerator;
    seen[2] = in->value[0].position.denominator;
    seen[3] = in->slot; seen[4] = in->track; seen[5] = in->generation;
    seen[6] = in->flags; seen[7] = in->pitch;
    seen[8] = in->velocity; seen[9] = in->gate;
    x0z_diagnostic(in->output, in->value[0].raw);
}
void probe_machine_render(int32_t slot, int32_t *block, const struct dnm_voice *voice)
{
    int32_t raw, minimum, maximum;
    probe_status[slot] = 0;
    if (!x0z_dn_frame_read(&probe_frame, slot, 124, &raw, &minimum, &maximum)) return;
    if (x0z_dn_render_frame(&probe_adapter, slot, block, voice, X0Z_808,
                            &probe_frame, probe_mapping, 1, receive, 0)) {
        probe_model[slot] = raw;
        probe_status[slot] = 1;
    }
}
static const struct dnm_knob knobs[DNM_KNOBS] = {{0}};
const struct dnm_machine probe_machine = {
    127, "X0Z TEST", 0, knobs, probe_machine_render, DNM_OWN_ENV, 0
};
void probe_in(void) { x0z_dn_frame_begin(&probe_frame); ++probe_count[0]; }
void probe_pre(int16_t *words) { x0z_dn_frame_capture(&probe_frame, words); ++probe_count[1]; }
void probe_late(int32_t *voices) { (void)voices; x0z_dn_frame_ready(&probe_frame); ++probe_count[2]; }
void probe_end(void) { x0z_dn_frame_end(&probe_frame); ++probe_count[3]; }
void probe_out(void) { x0z_dn_frame_end(&probe_frame); ++probe_count[4]; }
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


def bounded(image_path, names, stock, omit_live_store=False):
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
        state = dict(active=None, errors=[], returns=set(), calls=[], order=[], block=-1, frame=None, reads=0, setter=None)
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
                if write and state["setter"] is not None:
                    allowed, writes = state["setter"]
                    if not any(first <= address and address + size <= last for first, last in allowed):
                        raise AssertionError(f"native live setter wrote unowned memory {address:#x}")
                    if address >= transport.STACK or address + size <= transport.STACK - 2048:
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
            uc.emu_start(first, last, count=count)
            if state["errors"] or uc.reg_read(regs.UC_M68K_REG_PC) != last:
                raise AssertionError("native machine stage stopped: " + str(state["errors"]))

        store = names["SOUND_LIVE"] + 0x5c
        store_bytes = image[store - device.main_load:store - device.main_load + 4]
        if store_bytes != bytes.fromhex("35830812"):
            raise ValueError("native live store differs from reviewed OS 1.44")
        if omit_live_store:
            uc.mem_write(store, bytes.fromhex("4e714e71"))
        kit, kit_bytes = 0x43000000, 0x2c + 4 * 326
        uc.mem_write(names["fw_kit"], struct.pack(">I", kit))
        uc.mem_write(0x80003f54, struct.pack(">I", kit + 0x14))
        target = names["fw_voice_params"]
        tracks, velocities = [slot % 4 for slot in range(8)], [1 + 18 * slot for slot in range(8)]
        pitches = [(60 + slot) << 16 for slot in range(8)]
        targets = [12345 + slot * 113 for slot in range(8)]
        uc.mem_write(0x80003f5c, struct.pack(">8I", *(kit + 0x2c + 326 * track for track in tracks)))
        event = 0x470D0000

        def note(slot):
            uc.mem_write(event, struct.pack(">18I", 0, 0, 0, 0, velocities[slot] << 8, *([0] * 13)))
            native(names["dnm_voice_on"], [slot, tracks[slot], event])

        for slot in range(8):
            uc.mem_write(0x80005444 + 20 * slot, struct.pack(">I", 0x43400000 + 512 * slot))
            voice = target + 18 + 158 * slot
            for parameter, value in ((0, 127 << 8), (27, targets[slot]), (32, 2000 + slot * 1000)):
                uc.mem_write(voice + 2 * parameter, struct.pack(">h", value))
            uc.mem_write(target + 1449 + 148 * slot, struct.pack(">4I", (0x1000 << 16) | 27, 0, 0, 0))
            uc.mem_write(0x431F2928 + 2 * slot, struct.pack(">h", 0x3F80))
            note(slot)
        uc.mem_write(names["fw_voice_pitch"], struct.pack(">8I", *pitches))
        uc.mem_write(names["fw_voice_track"], struct.pack(">8I", *tracks))
        uc.mem_write(names["fw_lfo_state"], bytes(8 * 80))
        settings = {1: 0x5000, 2: 0, 4: 27 << 8, 5: 2 << 8, 6: 64 << 8,
                    7: 1 << 8, 8: 72 << 8, 12: 0, 16: 64 << 8}
        cases, generations, live_edit = [], [1] * 8, None
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
            for slot in range(8):
                for parameter, value in settings.items():
                    uc.mem_write(words + 158 * slot + 2 * parameter, struct.pack(">h", value))
            native(names["core_render_params"], [frame])
            native(0x400FED62, [frame, 14400, 255 if block == 0 else 0, 0, 0xFFFFFFFF, 0xFFFFFFFF])
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
        return dict(cases=cases, machine_callbacks=len(state["calls"]), guarded_frame_reads=state["reads"],
                    live_edit=live_edit, blocks=7, instructions_per_call_or_stage=transport.LIMIT,
                    event_order=["in", "pre", "ready (40)", "companion/machine (50)", "end (60)", "out"],
                    missing_frame_block=5, unselected_fm_slot=dict(block=4, slot=7))
    finally:
        machine.close()


def verify():
    image, names, stock = transport.build(FOLDER, machine_driver=DRIVER)
    result = bounded(image, names, stock)
    marker = "if (!x0z_dn_frame_read(&probe_frame, slot, 124, &raw, &minimum, &maximum)) return;"
    if DRIVER.count(marker) != 1:
        raise ValueError("machine missing-frame mutation marker is not unique")
    altered = DRIVER.replace(marker, """if (!x0z_dn_frame_read(&probe_frame, slot, 124, &raw, &minimum, &maximum)) {
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
    result.update(rejected_mutations=rejected, kind="registered DN machine / native companion diagnostic", stock=stock,
                  emulator_revision=cpu.revision(ROOT / "vendor/digiemu"), project_revision=cpu.revision(ROOT),
                  elekloader_revision=stock["sdk_revision"],
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  driver_sha256=hashlib.sha256(DRIVER.encode()).hexdigest(),
                  adapter_sha256=hashlib.sha256((ROOT / "machines/digitone/adapter.c").read_bytes()).hexdigest(),
                  adapter_header_sha256=hashlib.sha256((ROOT / "machines/digitone/adapter.h").read_bytes()).hexdigest(),
                  controls_sha256=hashlib.sha256((ROOT / "src/controls.c").read_bytes()).hexdigest(),
                  controls_header_sha256=hashlib.sha256((ROOT / "include/x0z/controls.h").read_bytes()).hexdigest(),
                  firmware_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                  fixture_machine_id=127, production_machine_id_adopted=False,
                  live_edit_source="actual SDK/stock live setter with injected kit and voice ownership; not a UI/MIDI gesture",
                  injection="initial target sound words, kit/ownership pointers, controller mapping/value, settled LFO settings, companion note events, pitch/track/gate state",
                  envelope="DNM_OWN_ENV bypasses companion AMP/velocity; these are covered by separate companion tests",
                  note_order="fixture calls dnm_voice_on before dispatch; native core_voice_on runs after core_render_voices, so START/frame alignment is unqualified",
                  unqualified=["MODEL selector ASM and complete mappings", "native UI/MIDI/lock sources", "native allocator and START/frame ownership",
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
