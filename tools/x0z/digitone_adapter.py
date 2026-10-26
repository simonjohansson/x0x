"""Compile the DN adapter and test its C-to-ASM boundary in pinned digiemu."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

from . import cpu

ROOT = cpu.ROOT
BASE, STACK, STOP = 0x40000400, 0x40030000, 0x40040000
DRIVER = r'''
#include "machines/digitone/adapter.h"
int32_t probe_raw[8][32], probe_min[32], probe_max[32];
int32_t probe_slot, probe_output[32], probe_status;
uint32_t probe_seen[24], probe_calls;
struct dnm_voice probe_voice;
struct x0z_dn_adapter probe_adapter;
const uint8_t fw_params[134 * 60] = {0};
extern void x0z_diagnostic(int32_t *, int32_t);
int32_t dnm_knob(int32_t voice, int32_t knob) { return probe_raw[voice][knob]; }
void dnm_knob_range(int32_t knob, int32_t *minimum, int32_t *maximum)
{ *minimum = probe_min[knob]; *maximum = probe_max[knob]; }
static void receive(void *context, const struct x0z_dn_input *in)
{
    uint32_t i;
    (void)context;
    ++probe_calls;
    probe_seen[0] = in->slot; probe_seen[1] = in->track;
    probe_seen[2] = in->generation; probe_seen[3] = in->flags;
    probe_seen[4] = in->pitch; probe_seen[5] = in->velocity;
    probe_seen[6] = in->gate; probe_seen[7] = in->count;
    for (i = 0; i < 3; ++i) {
        probe_seen[8 + i * 5] = in->value[i].raw;
        probe_seen[9 + i * 5] = in->value[i].minimum;
        probe_seen[10 + i * 5] = in->value[i].maximum;
        probe_seen[11 + i * 5] = in->value[i].position.numerator;
        probe_seen[12 + i * 5] = in->value[i].position.denominator;
    }
    x0z_diagnostic(in->output, in->value[0].raw);
}
void probe_run(void)
{
    static const struct x0z_dn_mapping map[] = {{X0Z_LEVEL,8},{X0Z_TONE,4},{X0Z_DECAY,9}};
    probe_status = x0z_dn_render(&probe_adapter, probe_slot, probe_output,
                                &probe_voice, X0Z_808, map, 3, receive, 0);
}
void probe_forget(void) { probe_status = x0z_dn_forget(&probe_adapter, probe_slot); }
'''


def build(folder, altered=None, companion=False, exports=None, base=BASE):
    folder.mkdir(parents=True, exist_ok=True)
    driver, linker = folder / "driver.c", folder / "probe.ld"
    text=DRIVER
    if exports is not None:
        text=text.replace("const uint8_t fw_params[134 * 60] = {0};", "")
        text=text.replace('int32_t dnm_knob(int32_t voice, int32_t knob) { return probe_raw[voice][knob]; }\nvoid dnm_knob_range(int32_t knob, int32_t *minimum, int32_t *maximum)\n{ *minimum = probe_min[knob]; *maximum = probe_max[knob]; }','')
        # Isolated native-probe observer, never a production machine descriptor.
        text += '''
uint32_t probe_frame_pointer, probe_frame_calls;
int32_t probe_frame_raw;
void probe_render_params(const int16_t *words)
{
    probe_frame_pointer = (uint32_t)words;
    probe_frame_raw = words[79 * probe_slot + 27];
    ++probe_frame_calls;
    probe_run();
}
'''
    if companion:
        text=text.replace("const uint8_t fw_params[134 * 60] = {0};", "")
        text=text.replace('int32_t dnm_knob(int32_t voice, int32_t knob) { return probe_raw[voice][knob]; }\nvoid dnm_knob_range(int32_t knob, int32_t *minimum, int32_t *maximum)\n{ *minimum = probe_min[knob]; *maximum = probe_max[knob]; }',
            'volatile int16_t fw_voice_params[641];\nvolatile uint32_t fw_voice_pitch[8], fw_gate_off;\nint32_t probe_track, probe_event[18], probe_action;\nint32_t probe_buffers[8 * 32];\nuint32_t probe_sample_word = 0x20000000;\nvoid dnm_voice_on(int32_t, int32_t, void *);\nvoid dnm_render(int32_t *);')
        text=text.replace('x0z_diagnostic(in->output, in->value[0].raw);','x0z_diagnostic(in->output, (int32_t)probe_sample_word);')
        start=text.index('void probe_run(void)')
        end=text.index('void probe_forget(void)')
        text=text[:start]+'''static void native_render(int32_t slot, int32_t *block, const struct dnm_voice *voice)
{
    static const struct x0z_dn_mapping map[] = {{X0Z_LEVEL,8},{X0Z_TONE,4},{X0Z_DECAY,9}};
    probe_status = x0z_dn_render(&probe_adapter, slot, block, voice, X0Z_808, map, 3, receive, 0);
}
struct dnm_machine probe_machine = {127, "X0Z TEST", 0, 0, native_render, 0, 0};
const struct dnm_machine *const dn_machines[] = {&probe_machine, 0};
void probe_run(void)
{
    if (probe_action) dnm_voice_on(probe_slot, probe_track, probe_event);
    dnm_render(probe_buffers);
}
'''+text[end:]
    driver.write_text(text)
    linker.write_text(f'SECTIONS {{ . = {base}; .text : {{ *(.text*) *(.rodata*) }} '
                      '. = ALIGN(4); .data : { *(.data*) } . = ALIGN(4); '
                      '__bss_start = .; .bss (NOLOAD) : { *(.bss*) *(COMMON) } __bss_end = .; }')
    prefix = os.environ.get("ELEKLOADER_CROSS", "m68k-elf-")
    source = altered or ROOT / "machines/digitone/adapter.c"
    objects = []
    sources=[source,ROOT/"src/controls.c",driver]
    if companion:
        sources.append(ROOT/"vendor/elekloader/mods/machines-dn1/machines.c")
    for index, path in enumerate(sources):
        obj = folder / f"part-{index}.o"
        cpu.command([cpu.require_program(prefix + "gcc"), "-mcpu=54455", "-std=c99", "-O2",
                     "-ffreestanding", "-fno-builtin", "-fno-pic", "-fno-pie", "-ffunction-sections", "-fdata-sections", "-Wall", "-Wextra", "-Werror",
                     "-I", ROOT, "-I", ROOT / "include", "-I", ROOT / "machines/digitone",
                     "-I", ROOT / "vendor/elekloader/elekloader/sdk/include", "-c", path, "-o", obj])
        objects.append(obj)
    assembly = folder / "diagnostic.o"
    cpu.command([cpu.require_program(prefix + "as"), "-mcpu=54455", ROOT / "targets/coldfire/diagnostic.s", "-o", assembly])
    executable, binary = folder / "probe.elf", folder / "probe.bin"
    if companion:
        parameter_source=folder/"parameters.s"
        parameter_source.write_text('.section .rodata\n.global fw_params\nfw_params:\n.incbin "'+str((folder/"parameters.bin").resolve())+'"\n')
        parameter_object=folder/"parameters.o"
        cpu.command([cpu.require_program(prefix+"as"),"-mcpu=54455",parameter_source,"-o",parameter_object])
        objects.append(parameter_object)
    definitions=[]
    if exports is not None:
        for name in ('dnm_knob','dnm_knob_range','fw_params'):
            definitions += ['--defsym',f'{name}={exports[name]}']
    cpu.command([cpu.require_program(prefix + "ld"), "-T", linker, "-e", "probe_run", *( ["--gc-sections"] if companion else []),*definitions,
                 *objects, assembly, "-o", executable])
    cpu.command([cpu.require_program(prefix + "objcopy"), "-O", "binary", executable, binary])
    names = {}
    for line in cpu.command([cpu.require_program(prefix + "nm"), "-S", "--defined-only", executable]).splitlines():
        fields = line.split()
        if len(fields) in (3, 4):
            names[fields[-1]] = int(fields[0], 16)
    return binary.read_bytes(), names


class Runner:
    def __init__(self, image, names):
        harness = cpu.require_module("emu.harness", "digiemu")
        from unicorn import UC_HOOK_MEM_WRITE
        from unicorn import m68k_const as regs
        self.regs, self.names = regs, names
        self.machine = harness.Machine()
        self.uc = self.machine.uc
        self.machine.ensure(0x40000000)
        self.uc.mem_write(BASE, image)
        self.uc.mem_write(names["__bss_start"], bytes(names["__bss_end"] - names["__bss_start"]))
        self.companion = "probe_buffers" in names
        self.writes = []
        self.uc.hook_add(UC_HOOK_MEM_WRITE, lambda _u,_a,address,size,_v,_d: self.writes.append((address,size)))
        if not self.companion:
            self.put("probe_min", [0] * 32)
            self.put("probe_max", [32512] * 32)
            self.uc.mem_write(names["probe_min"] + 4 * 4, struct.pack(">i", -6656))
            self.uc.mem_write(names["probe_max"] + 4 * 4, struct.pack(">i", 6656))

    def put(self, name, words):
        self.uc.mem_write(self.names[name], struct.pack(">" + "I" * len(words), *(word & 0xFFFFFFFF for word in words)))

    def get(self, name, count=1):
        return list(struct.unpack(">" + "I" * count, self.uc.mem_read(self.names[name], 4 * count)))

    def call(self, name="probe_run"):
        from unicorn import UcError
        saved = {getattr(self.regs, "UC_M68K_REG_" + n): 0x10203040 + i for i,n in enumerate(
            [*(f"D{i}" for i in range(2,8)), *(f"A{i}" for i in range(2,7))])}
        for reg,value in saved.items(): self.uc.reg_write(reg,value)
        self.uc.mem_write(STACK - 1024, b"\xa5" * 1040)
        self.uc.mem_write(STACK, struct.pack(">I", STOP))
        self.uc.reg_write(self.regs.UC_M68K_REG_SR, 0x2700)
        self.uc.reg_write(self.regs.UC_M68K_REG_A7, STACK)
        self.writes = []
        try:
            self.uc.emu_start(self.names[name], STOP, count=20000)
        except UcError as error:
            raise RuntimeError(f"compiled DN adapter execution failed: {error}") from error
        if self.uc.reg_read(self.regs.UC_M68K_REG_PC) != STOP:
            raise AssertionError("DN C adapter did not return within its instruction bound")
        if self.uc.reg_read(self.regs.UC_M68K_REG_A7) != STACK + 4:
            raise AssertionError("DN C adapter corrupted its caller stack")
        if any(self.uc.reg_read(reg) != value for reg,value in saved.items()):
            raise AssertionError("DN C adapter corrupted a preserved register")
        if bytes(self.uc.mem_read(STACK - 1024, 32)) != b"\xa5" * 32:
            raise AssertionError("DN C adapter exceeded its guarded test stack")
        objects=[("probe_adapter",96),("probe_status",4),("probe_seen",96),("probe_calls",4)]
        objects += [("probe_buffers",1024),("vs",224)] if self.companion else [("probe_output",128)]
        allowed=[(self.names[name],self.names[name]+size) for name,size in objects]
        allowed.append((STACK-992,STACK))
        if any(not any(first<=at and at+width<=last for first,last in allowed) for at,width in self.writes):
            raise AssertionError("DN C adapter wrote outside test-owned state/output/stack")
        return self.get("probe_status")[0], self.get("probe_seen", 23), self.get("probe_buffers",256) if self.companion else self.get("probe_output",32)

    def configure(self, slot=3, track=2, fresh=1, velocity=37, gate=1, value=12345, tone=-1):
        self.put("probe_slot", [slot])
        self.put("probe_voice", [60 << 16,velocity,fresh,track,gate])
        at = self.names["probe_raw"] + (slot * 32 + 8) * 4
        self.uc.mem_write(at, struct.pack(">i", value))
        self.uc.mem_write(self.names["probe_raw"] + (slot * 32 + 4) * 4, struct.pack(">i",tone))
        self.uc.mem_write(self.names["probe_raw"] + (slot * 32 + 9) * 4, struct.pack(">i",16256))


def check(image, names):
    runner = Runner(image,names)
    cases=[]
    for slot in range(8):
        for fresh,velocity,gate,value in ((1,37,1,12345),(0,127,0,1),(1,1,1,32512)):
            runner.configure(slot=slot,track=slot % 4,fresh=fresh,velocity=velocity,gate=gate,value=value)
            status,seen,output=runner.call()
            expected_flags=3 if len([x for x in cases if x["slot"]==slot])==0 else (2 if fresh else 0)
            if (status!=1 or seen[:8]!=[slot,slot%4,1,expected_flags,60<<16,velocity,gate,3]
                    or seen[8:13]!=[value,0,32512,value,32512]
                    or seen[13:18]!=[0xFFFFFFFF,(-6656)&0xFFFFFFFF,6656,6655,13312]
                    or output!=[value]*32):
                raise AssertionError("compiled DN adapter control/event/ASM output mismatch")
            cases.append(dict(slot=slot,fresh=fresh,velocity=velocity,gate=gate,raw=value))
    runner.configure(slot=3,track=0)
    _,seen,_=runner.call()
    if seen[2:4]!=[2,3]: raise AssertionError("track reassignment did not change generation")
    runner.call("probe_forget")
    _,seen,_=runner.call()
    if seen[2:4]!=[3,3]: raise AssertionError("forgotten slot did not start a new assignment")
    before=runner.get("probe_calls")[0]
    runner.configure(slot=3,tone=6657)
    status,_,_=runner.call()
    if status or runner.get("probe_calls")[0]!=before:
        raise AssertionError("invalid native value reached the DSP receiver")
    return dict(cases=cases,checked=["all eight slots", "exact native signed/fractional ranges",
        "observed fresh/track/gate/velocity", "reassignment and explicit forget", "unscaled ASM output",
        "invalid input rejection", "callee registers/stack and test memory bounds"])


def verify():
    folder=ROOT/"out/dn-adapter/component"
    image,names=build(folder)
    result=cpu.provenance("coldfire",image,ROOT/"machines/digitone/adapter.c","digiemu")
    result.update(check(image,names))
    mutations=[]
    original=(ROOT/"machines/digitone/adapter.c").read_text()
    for name,old,new in (
        ("fraction-lost","(uint32_t)raw - (uint32_t)minimum","0"),
        ("fresh-reset-all","if (!adapter->slot[slot].active || adapter->slot[slot].track != input->track)","if (1)"),
        ("velocity-scaled","input->velocity = (uint32_t)voice->velocity;","input->velocity = 127;")):
        if original.count(old)!=1: raise ValueError("mutation marker is not unique")
        mutant=folder/name
        mutant.mkdir(exist_ok=True)
        path=mutant/"adapter.c"
        path.write_text(original.replace(old,new))
        altered,symbols=build(mutant,path)
        try: check(altered,symbols)
        except AssertionError as error: mutations.append(dict(name=name,reason=str(error)))
        else: raise AssertionError("DN adapter accepted defective "+name)
    result.update(kind="digitone-compiled-adapter-component",passed=True,
                  rejected_mutations=mutations,
                  unqualified=["native firmware UI/lock delivery", "native allocator identity beyond observed track/fresh",
                               "companion AMP/velocity end-to-end", "physical timing and kick fidelity"])
    return result


def verify_companion():
    from elekloader import formats
    from .firmware import baseline, verify_entry
    entries,sdk_revision=baseline()
    stock_report=verify_entry(entries["digitone-mk1"],ROOT/"firmware",sdk_revision)
    stock,device,release=formats.load(Path(stock_report["image"]))
    main=formats.main_image(stock,device)
    core=json.loads((ROOT/"vendor/elekloader/mods/core-dn1/mod.json").read_text())
    symbols=core["defsym"]|core["ports"][release.version].get("defsym",{})
    offset=int(symbols["PARAMS"],0)-device.main_load
    records=main[offset:offset+134*60]
    if len(records)!=134*60: raise ValueError("native parameter table extent is invalid")
    folder=ROOT/"out/dn-adapter/companion"
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"parameters.bin").write_bytes(records)
    image,names=build(folder,companion=True)
    def fresh(velocity,own_env):
        runner=Runner(image,names)
        runner.put("probe_slot",[3]);runner.put("probe_track",[2]);runner.put("probe_action",[1])
        runner.put("probe_event",[0,0,0,0,velocity<<8]+[0]*13)
        runner.put("probe_buffers",[0x11111111]*256)
        runner.put("fw_voice_pitch",[0,0,0,60<<16,0,0,0,0])
        frame=[0]*641
        frame[9+79*3]=127<<8
        for parameter,raw in ((119,12345),(111,16001),(120,16256)):
            _,slot,minimum,maximum,_=struct.unpack_from(">5i",records,parameter*60)
            if not minimum<=raw<=maximum: raise AssertionError("native fixture control is outside its stock range")
            frame[9+79*3+slot]=raw
        for slot,value in ((66,0),(67,0),(68,127<<8),(69,0)):
            frame[9+79*3+slot]=value
        runner.uc.mem_write(names["fw_voice_params"],struct.pack(">641H",*(x&0xFFFF for x in frame)))
        runner.uc.mem_write(names["probe_machine"]+20,struct.pack(">I",own_env))
        first=runner.call()
        runner.put("probe_action",[0])
        settled=runner.call()
        return runner,first,settled
    reports=[]
    for velocity in (1,37,127):
        runner,first,settled=fresh(velocity,0)
        status,seen,buffers=settled
        expected=((0x20000000>>16)*(32767*velocity//127))<<1
        if (status!=1 or seen[:8]!=[3,2,1,0,60<<16,velocity,1,3]
                or seen[8:13]!=[12345,0,32512,12345,32512]
                or seen[13:18]!=[16001,9472,22784,6529,13312]
                or buffers[96:128]!=[expected]*32
                or any(x!=0x11111111 for x in buffers[:96]+buffers[128:])):
            raise AssertionError("actual pinned companion control/AMP/velocity path diverged")
        if first[1][3]!=3 or first[1][2]!=1:
            raise AssertionError("native note callback did not deliver fresh assignment")
        runner.put("fw_gate_off",[1<<3])
        _,released,_=runner.call()
        if released[6]!=0: raise AssertionError("native companion release did not clear the gate")
        reports.append(dict(velocity=velocity,post_amp_word=expected,native_raw=seen[8:23]))
    for velocity in (1,127):
        _,_,settled=fresh(velocity,1)
        if settled[2][96:128]!=[0x20000000]*32:
            raise AssertionError("DNM_OWN_ENV did not bypass companion AMP and velocity together")
    report=cpu.provenance("coldfire",image,ROOT/"machines/digitone/adapter.c","digiemu")
    report.update(kind="digitone-pinned-companion-component",stock=stock_report,
                  parameter_table_sha256=hashlib.sha256(records).hexdigest(),
                  sdk_companion_sha256=hashlib.sha256((ROOT/"vendor/elekloader/mods/machines-dn1/machines.c").read_bytes()).hexdigest(),
                  cases=reports,checked=["actual dnm_knob and native stock ranges","actual companion fresh/gate handling",
                    "default companion AMP and velocity applied once","DNM_OWN_ENV bypasses both AMP and velocity",
                    "unrelated FM buffers unchanged"],
                  unqualified=["full firmware UI/encoder/MIDI/parameter-lock delivery","native allocator identity","physical timing and kick fidelity"])
    return report


def verify_native():
    """Check the actual linked setter/accessor contract before claiming delivery."""
    from elekloader import formats
    from .firmware import baseline, verify_entry
    harness=cpu.require_module("emu.harness","digiemu")
    from unicorn.m68k_const import UC_M68K_REG_PC, UC_M68K_REG_SR
    entries,revision=baseline()
    stock_report=verify_entry(entries["digitone-mk1"],ROOT/"firmware",revision)
    if stock_report["version"]!="1.44": raise ValueError("native DN probe needs the latest 1.44 profile")
    image_path=ROOT/"out/dn/x0z-baseline.syx"
    if not image_path.is_file(): raise cpu.Unavailable("build latest baseline with mise run firmware:dn")
    report=json.loads((ROOT/"out/dn/baseline-build.json").read_text())
    if hashlib.sha256(image_path.read_bytes()).hexdigest()!=report["baseline_sha256"]:
        raise ValueError("DN baseline differs from its recorded identity")
    _,device,_=formats.load(Path(stock_report["image"]))
    image=formats.main_image(formats.parse(image_path,device),device)
    symbols={name:int(value,0) for name,value in json.loads(image_path.with_suffix('.syx.map.json').read_text()).items()}
    machine=harness.Machine(); machine.load(image,device.main_load)
    machine.install_isa_patches_scoped(image,device.main_load)
    for region in (0x43000000,0x47000000,0x80000000,symbols['__run_start'],symbols['fw_kit']): machine.ensure(region)
    start=symbols['__run_load']-device.main_load
    machine.uc.mem_write(symbols['__run_start'],image[start:start+symbols['__run_words']*4])
    machine.uc.mem_write(symbols['__bss_start'],bytes(symbols['__bss_words']*4))
    uc=machine.uc; uc.reg_write(UC_M68K_REG_SR,0x2700)
    def native(function,args):
        result=harness.call(machine,function,args,ret_magic=0xDEADBEE0,stack_top=0x470F0000,limit=200000)
        if uc.reg_read(UC_M68K_REG_PC)!=0xDEADBEE0: raise AssertionError("native DN routine exceeded its bound")
        return result
    kit=0x43000000; track=2; voice=3
    uc.mem_write(symbols['fw_kit'],struct.pack('>I',kit))
    uc.mem_write(0x80003F54,struct.pack('>I',kit+0x14))
    uc.mem_write(symbols['fw_voice_track'],struct.pack('>8I',1,1,1,track,1,1,1,1))
    setter_instruction=symbols['SOUND_LIVE']+0x5C
    opcode=image[setter_instruction-device.main_load:setter_instruction-device.main_load+4]
    if opcode!=bytes.fromhex('35830812'): raise ValueError("native target-store encoding differs from pinned 1.44")
    observations=[]
    native(symbols['core_sound_set'],[track,21,16001])
    native(symbols['core_sound_set'],[track,28,16256])
    for slot,value in ((27,12345),(30,23456)):
        native(symbols['core_sound_set'],[track,slot,value])
        observed=native(symbols['dnm_knob'],[voice,8])
        target=symbols['fw_voice_params']+18+158*voice+2*slot
        api=symbols['fw_voice_params']+18+158*voice+2*27
        observations.append(dict(edited_sound_slot=slot,value=value,knob=8,
            setter_target_address=hex(target),setter_target_word=int.from_bytes(uc.mem_read(target,2),'big'),
            accessor_address=hex(api),accessor_word=observed,
            kit_word=int.from_bytes(uc.mem_read(kit+0x2C+326*track+2*slot,2),'big')))
    good=observations[0]['accessor_word']==12345 and observations[1]['accessor_word']==12345
    folder=ROOT/'out/dn-adapter/native'; folder.mkdir(parents=True,exist_ok=True)
    code,probe=build(folder,exports=symbols,base=0x47000000)
    uc.mem_write(0x47000000,code)
    uc.mem_write(probe['__bss_start'],bytes(probe['__bss_end']-probe['__bss_start']))
    uc.mem_write(probe['probe_slot'],struct.pack('>I',voice))
    uc.mem_write(probe['probe_voice'],struct.pack('>5I',60<<16,37,1,track,1))
    native(probe['probe_run'],[])
    captured=list(struct.unpack('>23I',uc.mem_read(probe['probe_seen'],92)))
    output=list(struct.unpack('>32i',uc.mem_read(probe['probe_output'],128)))
    if captured[:8]!=[voice,track,1,3,60<<16,37,1,3] or captured[8:13]!=[12345,0,32512,12345,32512] or output!=[12345]*32:
        raise AssertionError('actual native live target did not reach compiled C adapter and ASM')

    # These two stock sites are probe fixtures for exactly 1.44, not mod exports.
    # The actual render sets fractional MACSR before calling the smoother.
    mode_site, smooth_call = 0x4009D1DE, 0x4009DB96
    if image[mode_site-device.main_load:mode_site-device.main_load+6]!=bytes.fromhex('a93c00000020'):
        raise ValueError('native render MACSR instruction differs from pinned 1.44')
    call_bytes=image[smooth_call-device.main_load:smooth_call-device.main_load+6]
    if call_bytes!=bytes.fromhex('4eb94009bf86'):
        raise ValueError('native smoother call differs from pinned 1.44')
    smooth=int.from_bytes(call_bytes[2:],'big')
    frame=0x43100100
    machine.ensure(frame)
    uc.mem_write(frame-256,bytes(4096))
    uc.mem_write(probe['probe_voice']+8,bytes(4))  # later blocks, no fixture START
    table=symbols['ev_render_params']
    saved_table=bytes(uc.mem_read(table,8))
    target_snapshot=bytes(uc.mem_read(symbols['fw_voice_params'],0xA40))
    ramp=[]
    try:
        # The baseline has no parameter handlers. Borrow the next table word
        # only inside this isolated machine, then restore both words in finally.
        if saved_table[:4]!=bytes(4): raise ValueError('native baseline already has a parameter observer')
        uc.mem_write(table,struct.pack('>2I',probe['probe_render_params'],0))
        for block in range(8):
            uc.emu_start(mode_site,mode_site+6,count=1)
            if uc.reg_read(UC_M68K_REG_PC)!=mode_site+6:
                raise AssertionError('native MACSR setup did not execute')
            native(smooth,[frame,symbols['fw_voice_params']])
            before=int.from_bytes(uc.mem_read(frame+18+158*voice+54,2),'big')
            native(symbols['core_render_params'],[frame])
            def word(name): return int.from_bytes(uc.mem_read(probe[name],4),'big')
            delivered=int.from_bytes(uc.mem_read(probe['probe_seen']+32,4),'big')
            rendered=list(struct.unpack('>32i',uc.mem_read(probe['probe_output'],128)))
            if (word('probe_frame_pointer')!=frame+18 or word('probe_frame_raw')!=before
                    or word('probe_frame_calls')!=block+1 or delivered!=12345 or rendered!=[12345]*32):
                raise AssertionError('native parameter observer/adapter target trace diverged')
            ramp.append(dict(block=block,pre_controller_frame=before,adapter_target=delivered))
    finally:
        uc.mem_write(table,saved_table)
    # An independent exact stock ramp prevents calling targets smoothed values,
    # or accepting a substituted observer/accessor that silently skips smoothing.
    expected_ramp=[370,730,1078,1416,1744,2062,2370,2670]
    if [block['pre_controller_frame'] for block in ramp]!=expected_ramp:
        raise AssertionError('stock DN 1.44 smoothing ramp differs from the independently observed trace')
    if bytes(uc.mem_read(symbols['fw_voice_params'],0xA40))!=target_snapshot:
        raise AssertionError('native smoother/controller probe changed the target buffer')
    return dict(kind='digitone-native-setter-accessor-contract',passed=good,stock=stock_report,
        elekloader_revision=revision,emulator_revision=cpu.revision(ROOT/'vendor/digiemu'),
        baseline_sha256=report['baseline_sha256'],observations=observations,
        native_calls={name:hex(symbols[name]) for name in ('core_sound_set','dnm_knob','fw_voice_params')},
        native_target_store=dict(address=hex(setter_instruction),opcode=opcode.hex(),displacement_bytes=18),
        compiled_adapter_trace=captured,asm_output_q31=output,
        smoothing_diagnostic=dict(kind='observed-sdk-transport-limitation',render_frame_delivered=False,
            smoother=hex(smooth),smoother_call_site=hex(smooth_call),macsr_site=hex(mode_site),
            parameter_event=hex(symbols['core_render_params']),observer_pointer=hex(frame+18),
            expected_stock_ramp=expected_ramp,trace=ramp,
            fixture='isolated eight-block call sequence and temporary parameter observer; event table restored',
            reason='Core exposes the pre-controller smoothed frame, but dnm_knob reads the unchanged target buffer; the compiled adapter therefore renders target 12345 for every block'),
        expected='Editing slot27 should reach SYN2 A; editing unrelated slot30 must not replace that knob',
        reason=None if good else 'native setter/accessor target-value contract diverged; delivered render-frame transport remains unproven',
        unqualified=['full OS boot/panel/MIDI','smoothing/locks/modulation render-frame delivery','physical timing and kick fidelity'])


def verify_host():
    folder=ROOT/"out/host"
    folder.mkdir(parents=True,exist_ok=True)
    executable=folder/"test_digitone_adapter"
    cpu.command([cpu.require_program(os.environ.get("CC","clang")),"-std=c99","-O2","-Wall","-Wextra","-Werror",
                 "-I",ROOT/"include","-I",ROOT/"vendor/elekloader/elekloader/sdk/include",
                 ROOT/"machines/digitone/adapter.c",ROOT/"src/controls.c",ROOT/"tests/ui/test_digitone_adapter.c",
                 "-o",executable])
    cpu.command([executable])
    return dict(kind="digitone-host-adapter",native_firmware_transport=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument("--host", action="store_true")
    mode.add_argument("--companion", action="store_true")
    mode.add_argument("--native", action="store_true")
    args=parser.parse_args(argv)
    try: result=verify_host() if args.host else verify_companion() if args.companion else verify_native() if args.native else verify()
    except cpu.Unavailable as error:
        print(json.dumps(dict(status="unavailable",reason=str(error))))
        return 77
    except (AssertionError,RuntimeError,ValueError,OSError) as error:
        print(json.dumps(dict(status="failed",reason=str(error))))
        return 1
    passed=result.get('passed',True)
    print(json.dumps(dict(status="passed" if passed else "failed",**result)))
    return 0 if passed else 1


if __name__=="__main__": sys.exit(main())
