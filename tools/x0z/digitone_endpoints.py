"""DN-only native endpoint delivery and canonical MODEL through existing ASM.

Generated ID127 firmware stays ignored. The first two blocks execute stock
control stages; subsequent MODEL words are explicitly synthetic callback inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import signal
import struct
from pathlib import Path

from . import cpu, digitone_transport as transport
from .coldfire_selector import APPLY, reference_step

ROOT = cpu.ROOT
FOLDER = ROOT / "out/dn/endpoints"
DRIVER = r'''
#include <stdint.h>
#include "adapter.h"
struct x0z_dn_frame probe_frame;
struct x0z_dn_adapter probe_adapter;
uint32_t probe_bank[8][3], probe_seen[8][12], probe_calls[8], probe_received[8];
uint32_t probe_ready;
int32_t probe_status[8];
const struct x0z_dn_frame_mapping probe_mapping[] = {{X0Z_LEVEL, 119}};
extern int x0z_selector(uint32_t *, uint32_t *, const uint32_t *);
struct model { int32_t raw; uint32_t canonical; };
static void receive(void *context, const struct x0z_dn_input *in)
{
    const struct model *model = context;
    uint32_t input[4] = {in->slot, model->canonical, !!(in->flags & X0Z_DN_NATIVE_START), 1};
    uint32_t notice[4] = {0xa5a5a5a5, 0xa5a5a5a5, 0xa5a5a5a5, 0xa5a5a5a5};
    uint32_t *seen = probe_seen[in->slot];
    uint32_t status = x0z_selector(probe_bank[0], notice, input), i;
    seen[0] = in->value[0].raw; seen[1] = in->value[0].minimum; seen[2] = in->value[0].maximum;
    seen[3] = in->value[0].position.numerator; seen[4] = in->value[0].position.denominator;
    seen[5] = model->raw; seen[6] = model->canonical; seen[7] = status;
    for (i = 0; i < 4; ++i) seen[8 + i] = notice[i];
    ++probe_received[in->slot];
    /* Only a C marker: the ASM selector is exercised, no kick audio is rendered. */
    if (status == 1)
        for (i = 0; i < 32; ++i)
            in->output[i] = notice[0] ? -in->value[0].raw : in->value[0].raw;
}
void probe_machine_render(int32_t slot, int32_t *block, const struct dnm_voice *voice)
{
    struct model model;
    ++probe_calls[slot];
    probe_status[slot] = 0;
    if (x0z_dn_frame_model(&probe_frame, slot, 124, &model.raw, &model.canonical))
        probe_status[slot] = x0z_dn_render_frame(&probe_adapter, slot, block, voice, X0Z_808,
                                               &probe_frame, probe_mapping, 1, receive, &model);
}
static const struct dnm_knob knobs[DNM_KNOBS] = {{0}};
const struct dnm_machine probe_machine = {
    127, "ENDPOINT TEST", 0, knobs, probe_machine_render, DNM_OWN_ENV, 0
};
void probe_in(void) { x0z_dn_frame_begin(&probe_frame); }
void probe_pre(int16_t *words) { x0z_dn_frame_capture(&probe_frame, words); }
void probe_late(int32_t *voices) { (void)voices; x0z_dn_frame_ready(&probe_frame); ++probe_ready; }
void probe_end(void) { x0z_dn_frame_end(&probe_frame); }
void probe_out(void) { x0z_dn_frame_end(&probe_frame); }
'''


def validate_delivery(words, level, model, status, notice):
    """Raw data and UI endpoints are independent of the clamped position."""
    expected_notice = list(notice) if notice is not None else [0xa5a5a5a5] * 4
    expected = [level, 0, 32512, min(level, 32512), 32512, model, min(model, 32512), status, *expected_notice]
    if words != expected or any(type(value) is not int for value in words):
        raise AssertionError("DN raw/UI bounds/position/canonical MODEL/ASM notice diverged")


def bounded(image_path, names, stock):
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
        for address in (0x47000000, 0x80000000, 0x43400000, 0x431f2928, 0x419f0de0,
                        names["fw_voice_pitch"], names["fw_lfo_state"], names["__run_start"]):
            machine.ensure(address)
        uc = machine.uc
        start, length = names["__run_load"] - device.main_load, 4 * names["__run_words"]
        if start < 0 or start + length > len(image):
            raise ValueError("DN endpoint run image exceeds firmware")
        uc.mem_write(names["__run_start"], image[start:start + length])
        uc.mem_write(names["__bss_start"], bytes(4 * names["__bss_words"]))
        uc.reg_write(regs.UC_M68K_REG_SR, 0x2700)
        word = lambda address: int.from_bytes(uc.mem_read(address, 4), "big")
        words = lambda address, count: list(struct.unpack(">" + "I" * count, uc.mem_read(address, 4 * count)))
        bank = lambda: [tuple(words(names["probe_bank"] + 12 * lane, 3)) for lane in range(8)]
        state = dict(active=None, current=None, errors=[], returns=set(), callbacks=0)
        preserved = [*(getattr(regs, "UC_M68K_REG_D" + str(i)) for i in range(2, 8)),
                     *(getattr(regs, "UC_M68K_REG_A" + str(i)) for i in range(2, 7))]

        def checked(fn):
            def callback(*args):
                try:
                    fn(*args)
                except Exception as error:
                    state["errors"].append(str(error)); uc.emu_stop()
            return callback

        def at(address, fn):
            return uc.hook_add(UC_HOOK_CODE, checked(fn), begin=address, end=address)

        def returned(_uc, address, _size, _data):
            active = state["active"]
            if active is None or address != active["return"]:
                return
            if uc.reg_read(regs.UC_M68K_REG_A7) != active["stack"] + 4 or any(
                uc.reg_read(key) != value for key, value in active["registers"].items()):
                raise AssertionError("DN endpoint callback changed callee registers/stack")
            if active["name"] == "machine":
                if bytes(uc.mem_read(active["voice"], 20)) != active["metadata"]:
                    raise AssertionError("DN endpoint callback wrote native metadata")
                if bytes(uc.mem_read(state["current"]["pointer"], transport.FRAME_BYTES)) != active["frame"]:
                    raise AssertionError("DN endpoint callback wrote native frame")
            state["active"] = None

        def entered(name):
            def callback(_uc, _address, _size, _data):
                if state["active"]:
                    raise AssertionError("nested DN endpoint callback")
                sp = uc.reg_read(regs.UC_M68K_REG_A7); ret = word(sp)
                if ret not in state["returns"]:
                    at(ret, returned); state["returns"].add(ret)
                active = state["active"] = dict(name=name, stack=sp, **{"return": ret},
                                               registers={key: uc.reg_read(key) for key in preserved})
                if name == "machine":
                    lane, output, voice = words(sp + 4, 3)
                    if lane != state["current"]["lane"] or output != names["fw_voices"] + 128 * lane:
                        raise AssertionError("DN endpoint companion selected the wrong lane")
                    state["callbacks"] += 1
                    active.update(lane=lane, output=output, voice=voice,
                                  metadata=bytes(uc.mem_read(voice, 20)),
                                  frame=bytes(uc.mem_read(state["current"]["pointer"], transport.FRAME_BYTES)))
            return callback

        for symbol, name in (("probe_in", "in"), ("probe_pre", "pre"), ("probe_late", "ready"),
                             ("probe_machine_render", "machine"), ("probe_end", "end"), ("probe_out", "out")):
            at(names[symbol], entered(name))

        def memory(write, address, size):
            active = state["active"]
            if active is None:
                return
            allowed = [(active["stack"] - 2048, active["stack"] + (0 if write else 16))]
            if active["name"] != "machine":
                allowed += [(names["probe_frame"], names["probe_frame"] + 8),
                            (names["probe_ready"], names["probe_ready"] + 4)]
            else:
                row = state["current"]; lane = active["lane"]
                allowed += [(names[key] + 4 * lane, names[key] + 4 * (lane + 1)) for key in ("probe_calls", "probe_status")]
                if not write or row["valid"]:
                    allowed += [(names["probe_adapter"] + 12 * lane, names["probe_adapter"] + 12 * (lane + 1)),
                                (names["probe_seen"] + 48 * lane, names["probe_seen"] + 48 * (lane + 1)),
                                (names["probe_received"] + 4 * lane, names["probe_received"] + 4 * (lane + 1))]
                if not write:
                    allowed += [(names["probe_frame"], names["probe_frame"] + 8),
                                (names["fw_params"], names["fw_params"] + 134 * 60),
                                (names["probe_mapping"], names["probe_mapping"] + 8),
                                (active["voice"], active["voice"] + 20),
                                (names["probe_bank"], names["probe_bank"] + 96)]
                    if row["captured"]:
                        allowed.append((row["pointer"], row["pointer"] + transport.FRAME_BYTES))
                if row["valid"] and row["status"] == APPLY:
                    allowed += [(names["probe_bank"] + 12 * lane, names["probe_bank"] + 12 * (lane + 1)),
                                (active["output"], active["output"] + 128)]
            if not any(first <= address and address + size <= last for first, last in allowed):
                raise AssertionError(f"DN endpoint {active['name']} callback {'wrote' if write else 'read'} unowned memory {address:#x}")

        uc.hook_add(UC_HOOK_MEM_READ, checked(lambda _uc, _kind, address, size, _value, _data: memory(False, address, size)))
        uc.hook_add(UC_HOOK_MEM_WRITE, checked(lambda _uc, _kind, address, size, _value, _data: memory(True, address, size)))

        def native(address, args):
            harness.call(machine, address, args, ret_magic=transport.RETURN, stack_top=transport.STACK, limit=transport.LIMIT)
            if state["errors"] or uc.reg_read(regs.UC_M68K_REG_PC) != transport.RETURN:
                raise AssertionError("DN endpoint native call stopped: " + str(state["errors"]))

        def execute(first, last, count=transport.LIMIT):
            stop = uc.hook_add(UC_HOOK_CODE, lambda current, *_: current.emu_stop(), begin=last, end=last)
            try:
                uc.emu_start(first, last, count=count)
            finally:
                uc.hook_del(stop)
            if state["errors"] or uc.reg_read(regs.UC_M68K_REG_PC) != last:
                raise AssertionError("DN endpoint native stage stopped: " + str(state["errors"]))

        target = names["fw_voice_params"]
        event = 0x470d0000
        uc.mem_write(event, struct.pack(">18I", 0, 0, 0, 0, 100 << 8, *([0] * 13)))
        uc.mem_write(names["fw_voice_track"], struct.pack(">8I", *(lane % 4 for lane in range(8))))
        uc.mem_write(names["fw_voice_pitch"], struct.pack(">8I", *([60 << 16] * 8)))
        for lane in range(8):
            uc.mem_write(0x80005444 + 20 * lane, struct.pack(">I", 0x43400000 + 512 * lane))

        def select(lane):
            for other in range(8):
                uc.mem_write(target + 18 + 158 * other, struct.pack(">h", 127 << 8 if other == lane else 0))

        def note(lane):
            native(names["dnm_voice_on"], [lane, lane % 4, event])

        def render(frame, lane, level, model, trigger, captured=True, kind="synthetic MODEL"):
            valid = captured and level >= 0 and model >= 0
            status, expected_bank, notice = reference_step(bank(), lane, min(model, 32512), trigger, 1) if valid else (None, bank(), None)
            state["current"] = dict(lane=lane, pointer=frame + 18, captured=captured, valid=valid, status=status)
            sentinel = [0x12340000 + index for index in range(256)]
            uc.mem_write(names["fw_voices"], struct.pack(">256I", *sentinel))
            previous_seen = bytes(uc.mem_read(names["probe_seen"], 384))
            previous_adapter = bytes(uc.mem_read(names["probe_adapter"], 96))
            received = words(names["probe_received"], 8)
            native(names["core_render_voices"], [frame, 0, 0])
            if bank() != expected_bank or any(uc.mem_read(names["probe_frame"], 8)):
                raise AssertionError("DN endpoint selector changed another lane or frame survived its pass")
            if valid:
                actual = words(names["probe_seen"] + 48 * lane, 12)
                validate_delivery(actual, level, model, status, notice)
                received[lane] += 1
            elif (bytes(uc.mem_read(names["probe_seen"], 384)) != previous_seen or
                  bytes(uc.mem_read(names["probe_adapter"], 96)) != previous_adapter):
                raise AssertionError("DN invalid endpoint delivery changed receiver/adapter state")
            if words(names["probe_received"], 8) != received or word(names["probe_status"] + 4 * lane) != int(valid):
                raise AssertionError("DN endpoint receiver status/count diverged")
            expected_output = list(sentinel)
            if valid and status == APPLY:
                expected_output[32 * lane:32 * (lane + 1)] = [level if notice[0] == 0 else -level] * 32
            if bytes(uc.mem_read(names["fw_voices"], 1024)) != struct.pack(">256i", *expected_output):
                raise AssertionError("DN endpoint marker or unrelated voice changed")
            uc.reg_write(regs.UC_M68K_REG_A6, 0x470e0000)
            native(names["core_render_out"], [])
            result = dict(kind=kind, lane=lane, level_raw=level, model_raw=model, canonical=min(model, 32512) if valid else None,
                          trigger=trigger, status=status, notice=notice)
            if valid:
                result["observed"] = dict(raw=actual[0], minimum=actual[1], maximum=actual[2],
                                          numerator=actual[3], denominator=actual[4],
                                          model_raw=actual[5], canonical=actual[6], selector_status=actual[7])
            return result

        # Native endpoint: stock stages retain Level overshoot when the LFO targets another word.
        select(0); note(0)
        uc.mem_write(target + 18 + 54, struct.pack(">h", 32512))
        uc.mem_write(0x800046b0 + 4 * (9 + 27), struct.pack(">I", 32512 << 16))
        uc.mem_write(target + 1449 + 36, struct.pack(">4I", (0x1000 << 16) | 27, 0, 0, 0))
        uc.mem_write(0x419f0de0, struct.pack(">I", 1)); uc.mem_write(0x419a93a4, b"\x01")
        native(0x400edbc2, [0, 1, 127, 0, 0])
        settings = {1: 0x5000, 2: 0, 4: 28 << 8, 5: 2 << 8, 6: 64 << 8,
                    7: 1 << 8, 8: 72 << 8, 12: 0, 16: 64 << 8}
        native_rows = []
        for block in range(2):
            frame = 0x80001fa4 + 0xa90 * block + 80
            uc.reg_write(regs.UC_M68K_REG_A6, 0x470e0000)
            native(names["core_render_in"], [])
            execute(0x4009d1de, 0x4009d1e4, 1)
            native(0x4009bf86, [frame, target])
            for parameter, value in settings.items():
                uc.mem_write(frame + 18 + 2 * parameter, struct.pack(">h", value))
            used = struct.unpack(">h", uc.mem_read(0x80004690, 2))[0]
            native(names["core_render_params"], [frame])
            native(0x400fed62, [frame, 14400, 1 if block == 0 else 0, 0, 0xffffffff, 0xffffffff])
            execute(0x4009dd92, 0x4009de1a)
            uc.reg_write(regs.UC_M68K_REG_A6, 0x470e0000); uc.reg_write(regs.UC_M68K_REG_A2, frame - 80)
            uc.reg_write(regs.UC_M68K_REG_D6, 0); uc.mem_write(0x470e0000 - 108, struct.pack(">I", frame))
            uc.reg_write(regs.UC_M68K_REG_A7, transport.STACK)
            execute(0x4009de1a, 0x4009df52)
            level = struct.unpack(">h", uc.mem_read(frame + 18 + 54, 2))[0]
            if used != (0 if block == 0 else 983) or level != (32512 if block == 0 else 32634):
                raise AssertionError("native DN endpoint fixture did not retain observed modulation overshoot")
            native_rows.append(render(frame, 0, level, 0, int(block == 0), kind="native final endpoint"))

        # Synthetic words test production canonicalization and unchanged ASM policy, independently of a source route.
        uc.mem_write(names["probe_bank"], bytes(96)); uc.mem_write(names["probe_adapter"], bytes(96))
        model_rows, step = [], 0

        def synthetic(lane, level, model, trigger, captured=True):
            nonlocal step
            frame = 0x80001fa4 + 0xa90 * (step % 2) + 80; step += 1
            select(lane)
            if trigger:
                note(lane)
            uc.reg_write(regs.UC_M68K_REG_A6, 0x470e0000)
            native(names["core_render_in"], [])
            uc.mem_write(frame, bytes(0xa40))
            uc.mem_write(frame + 18 + 158 * lane + 54, struct.pack(">h", level))
            uc.mem_write(frame + 18 + 158 * lane + 64, struct.pack(">h", model))
            if captured:
                native(names["core_render_params"], [frame])
            return render(frame, lane, level, model, int(trigger), captured)

        levels = (0, 1, 32511, 32512, 32513, 32634, 32767, 128)
        for lane in range(8):
            model_rows.append(synthetic(lane, 32634, 32767, True, captured=False))
            model_rows.append(synthetic(lane, 32634, 32767, False))
            initial = 16383 if lane % 2 == 0 else 16384
            model_rows.append(synthetic(lane, levels[lane], initial, True))
            uc.mem_write(names["probe_bank"] + 12 * lane + 8, struct.pack(">I", 0x12340000 + lane))
            model_rows.append(synthetic(lane, 32634, 32767 if lane % 2 == 0 else 0, False))
            model_rows.append(synthetic(lane, 32634, initial, True))
            model_rows.append(synthetic(lane, 32634, 16384 if lane % 2 == 0 else 16383, True))
        for raw in (32513, 32634, 32767):
            model_rows.append(synthetic(3, 32767, raw, True))
        model_rows.append(synthetic(3, 32634, -1, True))
        if word(names["probe_ready"]) != state["callbacks"]:
            raise AssertionError("DN endpoint callback count differs from its ready passes")
        return dict(native_cases=native_rows, synthetic_cases=model_rows, callbacks=state["callbacks"],
                    synthetic_scope="controlled frame words and companion note events, not native MODEL modulation/allocator timing",
                    fixture_machine_id=127, selector_bank=bank(), audio_frames_rendered=0)
    finally:
        machine.close()


def build(folder, adapter_source=None):
    return transport.build(folder, adapter_source=adapter_source, machine_driver=DRIVER,
                           assembly_source=ROOT / "targets/coldfire/selector.s")


def reject_mutations():
    original = (ROOT / "machines/digitone/adapter.c").read_text()
    mutations = [
        ("normalized clamp removed", "raw > maximum ? maximum : raw, minimum, maximum", "raw, minimum, maximum"),
        ("raw observation clipped", "input.value[i].raw = raw;", "/* Observation lost. */"),
        ("denominator rescaled to32634", "(uint32_t)maximum - (uint32_t)minimum,", "(uint32_t)32634 - (uint32_t)minimum,"),
        ("denominator rescaled to32767", "(uint32_t)maximum - (uint32_t)minimum,", "(uint32_t)32767 - (uint32_t)minimum,"),
        ("MODEL canonicalization bypassed", "*canonical = (uint32_t)(observed > maximum ? maximum : observed);", "*canonical = (uint32_t)observed;"),
    ]
    rejected = []
    for index, (name, old, new) in enumerate(mutations):
        if original.count(old) != 1:
            raise ValueError("DN endpoint mutation marker is not unique: " + name)
        folder = FOLDER / f"mutation-{index}"
        folder.mkdir(parents=True, exist_ok=True)
        source = folder / "adapter.c"
        source.write_text(original.replace(old, new))
        image, names, stock = build(folder, source)
        try:
            bounded(image, names, stock)
        except AssertionError as error:
            if "DN raw/UI bounds/position/canonical MODEL/ASM notice diverged" not in str(error):
                raise
            rejected.append(dict(name=name, reason=str(error), adapter_sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
        else:
            raise AssertionError("DN endpoint test accepted " + name)
    return rejected


def verify():
    image, names, stock = build(FOLDER)
    result = bounded(image, names, stock)
    result.update(rejected_mutations=reject_mutations(), kind="DN native overshoot / canonical MODEL selector diagnostic", stock=stock,
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  driver_sha256=hashlib.sha256(DRIVER.encode()).hexdigest(),
                  adapter_sha256=hashlib.sha256((ROOT / "machines/digitone/adapter.c").read_bytes()).hexdigest(),
                  adapter_header_sha256=hashlib.sha256((ROOT / "machines/digitone/adapter.h").read_bytes()).hexdigest(),
                  selector_sha256=hashlib.sha256((ROOT / "targets/coldfire/selector.s").read_bytes()).hexdigest(),
                  firmware_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                  emulator_revision=cpu.revision(ROOT / "vendor/digiemu"), project_revision=cpu.revision(ROOT),
                  unqualified=["DT/DN2 policies", "native MODEL source and START alignment", "full-OS timing", "kick audio/fidelity"])
    return result


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    signal.alarm(180)
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
