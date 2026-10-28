"""Stage the ColdFire 808 development package and perform a bounded DT1 OS smoke."""
from pathlib import Path
import contextlib
import ctypes
import hashlib
import json
import os
import shutil
import struct
import sys
import time
import wave
from . import cpu,firmware,coldfire_field808 as dsp

OUT=dsp.OUT/'dt'


def package(folder=OUT):
    from elekloader.sdk import build as sdk
    from elekloader import patch
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    tables=folder/'model';receipt=dsp.write_tables(tables)
    entries,revision=firmware.baseline()
    stock=firmware.verify_entry(entries['digitakt-mk1'],cpu.ROOT/'firmware',revision)
    original=cpu.ROOT/'machines/digitakt';source=(original/'machine.c').read_text()
    marker='#define CONTROL';assert source.count(marker)==1
    glue='''#include "digitakt-mk1/core3.h"
#define X0X_ID 80
static int32_t field_state[8][352];
extern void x0x_field808(int32_t*,int32_t*,uint32_t,uint32_t,uint32_t,uint32_t);
void x0x_dt_render(int32_t *blocks) {
    for(uint32_t track=0;track<8;++track) {
        if(fw_render_machine[track]!=X0X_ID) { field_state[track][6]=0;continue; }
        x0x_field808(field_state[track],blocks+32*track,(fw_voice_start>>track)&1,
            (uint32_t)cm_src_value(track,0),(uint32_t)cm_src_value(track,1),
            (uint32_t)cm_src_value(track,5));
    }
}
'''+marker+source.split(marker,1)[1]
    stage=folder/'mod';stage.mkdir(exist_ok=True);(stage/'machine.c').write_text(glue)
    manifest=json.loads((original/'mod.json').read_text())
    manifest['sources']=[str(stage/'machine.c'),str(dsp.SOURCE),str(tables/'tables.s')]
    manifest['description']='Frozen fixed-point 808 ASM development candidate; START-latched controls, MODEL909 silent'
    (stage/'mod.json').write_text(json.dumps(manifest,indent=2)+'\n')
    # Reuse the already approved x0x-only legacy-default correction, without editing the SDK.
    companion=folder/'machine-pages'
    shutil.copytree(cpu.ROOT/'vendor/elekloader/mods/machine-pages',companion,dirs_exist_ok=True)
    correction=original/'legacy-defaults.patch'
    cpu.command(['patch','-p1','--batch','--forward','--fuzz=0','-i',correction],cwd=companion)
    artifacts=[]
    for path in (cpu.ROOT/'vendor/elekloader/mods/core',companion,stage):
        artifacts.append(sdk.build(str(path),stock['image'],str(folder/'deps'))[0])
    outputs,manifest_result=patch.build(stock['image'],artifacts,'X8C1',log=lambda *_:None)
    image=folder/'x0x-coldfire808.syx';image.write_bytes(outputs['syx'])
    mapping=manifest_result['_map']
    (folder/'link-map.json').write_text(json.dumps(mapping,indent=2)+'\n')
    result=dict(status='built',scope='Staged DT1 808 development package; existing saved ID/page declarations unchanged',
        firmware=str(image),firmware_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),version='X8C1',
        stock=stock,elekloader_revision=revision,model=receipt,linked_layout=manifest_result['link']['layout'],
        defaults_patch_sha256=hashlib.sha256(correction.read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256(dsp.SOURCE.read_bytes()).hexdigest(),
        glue_sha256=hashlib.sha256(glue.encode()).hexdigest(),
        note='No host integer-reference C or floating-point sample loop is linked; standalone MODEL909 is silent.')
    (folder/'package.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def smoke(folder=OUT):
    cpu.require_module('emu.session','digiemu')
    from emu.bootstrap import first_run
    from emu.fwcheck import prepare
    from emu.longrun import never_fake_set_posts
    from emu.session import Session
    from emu import panel
    from unicorn.m68k_const import UC_M68K_REG_A7,UC_M68K_REG_PC
    folder=Path(folder);built=package(folder);session=None
    report=dict(status='failed',scope='DT1 full-OS emulator wiring smoke; no physical device or platform-wide qualification',
                trigger_source='native panel trig 1',package=built,emulator_revision=cpu.revision(cpu.ROOT/'vendor/digiemu'),hle=False)
    try:
        with (folder/'boot.log').open('w') as log,contextlib.redirect_stdout(log):
            paths,device=prepare(built['firmware'],str(folder/'cache'));assert device.short=='dt1'
            os.environ.update(paths.env());began=time.monotonic()
            snap=first_run(paths,cancel=lambda:time.monotonic()-began>120)
            session=Session(snap,paths.syx,hle=False)
            never_fake_set_posts(session.m,session.ev,session.profile.set_post)
        names=json.loads((folder/'link-map.json').read_text());uc=session.m.uc
        names={k:int(v,0) if isinstance(v,str) else v for k,v in names.items()}
        reference=dsp.Reference(folder/'integer-reference')
        references=[(ctypes.c_int32*dsp.WORDS)() for _ in range(8)]
        active=None;returns=set();checks=dict(callbacks=0,starts=0,nonzero_blocks=0,render_notifications=0);failures=[]
        report['checks']=checks;report['failures']=failures
        def checked(fn):
            def hook(*args):
                try:fn(*args)
                except Exception as e:failures.append(repr(e));session.halted='mod smoke: '+repr(e);uc.emu_stop()
            return hook
        def returned(*_):
            nonlocal active
            if active is None:return
            owner,out,slot,expected=active
            actual=list(struct.unpack('>32i',uc.mem_read(out,128)))
            assert actual==expected,'Native callback output differs from integer reference'
            assert bytes(uc.mem_read(owner,dsp.WORDS*4))==struct.pack('>352i',*references[slot]),'Native callback state differs'
            checks['callbacks']+=1;checks['nonzero_blocks']+=int(any(actual));active=None
        def entered(*_):
            nonlocal active
            assert active is None,'Nested mod callback'
            sp=uc.reg_read(UC_M68K_REG_A7);ret=int.from_bytes(uc.mem_read(sp,4),'big')
            owner,out,start,tone,decay,model=struct.unpack('>6I',uc.mem_read(sp+4,24))
            slot,offset=divmod(owner-names['field_state'],dsp.WORDS*4)
            assert offset==0 and 0<=slot<8 and out==names['fw_track_blocks']+128*slot
            if ret not in returns:session.at(ret,checked(returned));returns.add(ret)
            reference.state=references[slot];expected=reference.call(tone,decay,start,model=model)
            checks['starts']+=int(bool(start))
            if start:checks['start_controls']=dict(tone=tone,decay=decay,model=model)
            active=(owner,out,slot,expected)
        session.at(names['x0x_field808'],checked(entered))
        def notified(*_):checks['render_notifications']+=1
        session.at(names['x0x_dt_render'],notified)
        def wait(ms=80):
            session.run_ms(ms);assert not session.halted and not failures,(session.halted,failures)
        def tap(key):session.tap(session.code(key),hold_ms=40,after_ms=80);assert not session.halted
        # Existing verified DT menu sequence, sent as one bounded script.
        wait();session.press(session.code('FUNC'));wait(40);tap('SRC');session.release(session.code('FUNC'));wait(40)
        for _ in range(4):tap('DOWN')
        tap('YES')
        sound=int.from_bytes(uc.mem_read(names['fw_kit'],4),'big')+0x20
        assert bytes(uc.mem_read(sound+126,1))==bytes([80]),'X0X machine not selected'
        pcm_start=len(session.pcm);tap('1');wait(250)
        # A time budget may stop inside the callback; finish that observation.
        for _ in range(20):
            if active is None:break
            wait(.05)
        pcm=bytes(session.pcm[pcm_start:]);peak=max(abs(x) for x in struct.unpack('<'+'h'*(len(pcm)//2),pcm))
        report['pcm_peak_int16']=peak
        report['render_machine_bytes']=bytes(uc.mem_read(names['fw_render_machine'],8)).hex()
        assert checks['starts'] and checks['nonzero_blocks'] and peak>0 and active is None,checks
        with wave.open(str(folder/'native-808.wav'),'wb') as f:
            f.setparams((2,2,session.audio_cfg['rate'],0,'NONE','not compressed'));f.writeframes(pcm)
        if session.frames:panel.write_png(session.frames[-1][1],str(folder/'selected.png'),scale=4)
        report.update(status='passed',machine_id=80,checks=checks,pcm_peak_int16=peak,
                      pcm_frames=len(pcm)//4,sample_rate=session.audio_cfg['rate'],failures=failures)
    finally:
        if session is not None:
            if session.frames:panel.write_png(session.frames[-1][1],str(folder/'last-screen.png'),scale=4)
            session.close()
        (folder/'smoke.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('package','smoke'))
    print(json.dumps((smoke if p.parse_args().command=='smoke' else package)()))
