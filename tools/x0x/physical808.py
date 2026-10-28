"""Build the instrumented physical-DN2 candidate with the requested DigiHealth branch."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

from . import cpu, firmware, sharc_field808 as dsp
from .sharc_layout import voice_artifact

OUT=cpu.ROOT/'out/808-model/sharc/device-physical'
STATE_BYTES=1232
WRAPPER=cpu.ROOT/'targets/sharc/field808_device.s'



def instrument(folder=OUT):
    folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=True)
    base,artifact=dsp.build(folder/'baseline')
    source=dsp.SOURCE.read_text()
    if source.count('R0=1060;')!=1:
        raise ValueError('Unexpected source state-stride declaration')
    source=source.replace('sharc_voice_render.','field808_render.').replace('R0=1060;','R0=1232;')
    (folder/'kernel.s').write_text(source)
    table=(folder/'baseline/tables.s').read_text()
    old='.VAR sharc_voice_state_bytes. = 1060;'
    if table.count(old)!=1:raise ValueError('Unexpected generated state-size declaration')
    (folder/'tables.s').write_text(table.replace(old,'.VAR sharc_voice_state_bytes. = 1232;'))
    programs=cpu.ROOT/'vendor/digikit/out/tools/selache/target/release'
    for path,name in ((WRAPPER,'wrapper'),(folder/'kernel.s','kernel'),(folder/'tables.s','tables')):
        cpu.command([programs/'selas','-proc','ADSP-21569','-o',folder/(name+'.doj'),path])
    executable=folder/'device.dxe'
    cpu.command([programs/'seld','-proc','ADSP-21569','-T',folder/'baseline/layout.ldf',
                 '-entry','sharc_voice_render.','-Map',folder/'device.map','-o',executable,
                 folder/'wrapper.doj',folder/'kernel.doj',folder/'tables.doj'])
    code,data,entry=dsp.read_executable(executable.read_bytes(),base['layout'])
    artifact=voice_artifact(code,data,0,20,64,code_bytes=dsp.CODE_BYTES,voice_bytes=STATE_BYTES)
    (folder/'voice.sharc.json').write_text(json.dumps(artifact,indent=2)+'\n')
    return base,artifact,code,data,entry

def build(health,folder=OUT):
    from elekloader import elemod,formats,link,patch,sharc
    from elekloader.sdk import build as sdk
    health=Path(health).resolve();folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=True)
    branch=cpu.command(['git','branch','--show-current'],cwd=health).strip()
    if branch!='codex/dn2-support' or cpu.command(['git','status','--porcelain'],cwd=health).strip():
        raise ValueError('Use a clean DigiHealth codex/dn2-support worktree')
    revision=cpu.revision(health)
    base,artifact,code,data,entry=instrument(folder)
    entries,sdk_revision=firmware.baseline()
    stock=firmware.verify_entry(entries['digitone-mk2'],cpu.ROOT/'firmware',sdk_revision)
    health_log=cpu.command([sys.executable,health/'build.py','--stock',stock['image'],'--out',folder/'health-build'])
    (folder/'health-build.log').write_text(health_log)
    health_artifacts=list((folder/'health-build').glob('*.elemod'))
    if len(health_artifacts)!=1:raise ValueError('Unexpected/stale DigiHealth artifacts')
    source_dir=cpu.ROOT/'machines/digitone2'
    manifest=json.loads((source_dir/'mod.json').read_text())
    manifest['sources']=[str(source_dir/p) for p in manifest['sources']]
    manifest['description']='Instrumented SHARC 808 device test; Tone/Decay latched, 909 silent'
    (folder/'mod.json').write_text(json.dumps(manifest,indent=2)+'\n')
    artifacts=[sdk.build(str(p),stock['image'],str(folder/'deps'))[0] for p in
               (cpu.ROOT/'vendor/elekloader/mods/core-dn2',cpu.ROOT/'vendor/elekloader/mods/machines-dn2',folder)]
    artifacts+=health_artifacts
    mods=[elemod.load_any(p) for p in artifacts]
    image,device,release=formats.load(stock['image']);main=formats.main_image(image,device)
    errors=link.check(mods,main)
    if errors:raise ValueError('; '.join(errors))
    linked=link.link(mods,main,sharc_stream=image.section(7))
    (folder/'link-map.json').write_text(json.dumps(linked.map,indent=2)+'\n')
    address=release.sharc['voice_range'][0]+release.sharc['voice_binding_offset']
    records=sharc.parse(linked.sharc_stream,release.sharc)
    binding=next(r for r in records if r.target==address)
    states=next(r for r in records if r.target==address+0x20)
    if binding.raw[16:24]!=struct.pack('<II',entry,20) or states.raw[16:24]!=struct.pack('<II',base['state_base'],STATE_BYTES):
        raise ValueError('Device callback/state binding mismatch')
    outputs,_=patch.build(stock['image'],artifacts,'X8D1',log=lambda *_:None)
    output=folder/'x0x-sharc808-digihealth.syx';output.write_bytes(outputs['syx'])
    receipt=dict(status='built-not-installed',scope='Instrumented physical-test image; not production timing',
        firmware=str(output),firmware_sha256=dsp.fit808.digest(output),version='X8D1',
        digihealth_root=str(health),digihealth_branch=branch,digihealth_revision=revision,
        elekloader_revision=sdk_revision,stock=stock,baseline=base,code_bytes=len(code),
        data_bytes=len(data),state_bytes=STATE_BYTES,state_base=base['state_base'],entry=entry,
        artifact_sha256=dsp.fit808.digest(folder/'voice.sharc.json'),wrapper_sha256=dsp.fit808.digest(WRAPPER),
        witness=dict(age=1024,ready_offset=1080,age_offset=1084,tone_offset=1088,decay_offset=1092,
                     output_offset=1096,span_offset=1224,period_offset=1228),
        timing_note='Raw EMUCLK span includes the nested call/return and interrupts; observer outside that interval. Period is between starts for the same voice; no idle-busy headroom inference.')
    (folder/'build.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

def compare_witness(blob,model):
    import numpy as np
    if len(blob)!=152:raise ValueError('Invalid frozen-witness length')
    ready,age,tone,decay=struct.unpack_from('<4I',blob)
    if ready!=1 or age!=1024 or max(tone,decay)>32767:
        raise ValueError('Invalid/unready frozen witness')
    actual=np.asarray(struct.unpack_from('<32f',blob,16))
    if not np.isfinite(actual).all():raise ValueError('Nonfinite physical output')
    expected=4*dsp.field808.render(model,tone,decay,frames=age+32)[age:]
    span,period=struct.unpack_from('<2I',blob,144)
    return dict(age=age,tone=tone,decay=decay,max_error_dsp_fs=float(abs(actual-expected).max()),
                span_ticks=span,period_ticks=period)



if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--digihealth',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(build(args.digihealth)))
