"""Private DN2 1.12 three-stage capture build and frozen DSP-peek readback."""
from pathlib import Path
import argparse
from dataclasses import replace
import hashlib
import importlib
import json
import struct
import sys

from . import cpu, firmware

CAPTURE, RESERVE, RECORD = 0x2009f800, 1024, 704
MAGIC, VERSION = 0x31304458, 'XD01'
SOURCE = cpu.ROOT / 'targets/sharc/capture.s'


def symbols(raw):
    start = struct.unpack_from('<I', raw, 32)[0]
    count = struct.unpack_from('<H', raw, 48)[0]
    sections = [struct.unpack_from('<10I', raw, start + 40*i) for i in range(count)]
    table, = [s for s in sections if s[1] == 2]
    names = sections[table[6]]
    result = {}
    for at in range(table[4], table[4] + table[5], 16):
        name, value = struct.unpack_from('<II', raw, at)
        begin = names[4] + name
        label = raw[begin:raw.index(b'\0', begin)].decode()
        if label:
            result[label] = value
    return result


def instrument(folder):
    """Keep coefficients, state addresses and the qualified adapter unchanged."""
    from . import sharc_field808 as engine
    from elekloader import sharc
    from elekloader.devices.digitone_mk2 import DEVICE
    from .sharc_layout import voice_artifact
    folder = Path(folder)
    receipt, original = engine.build(folder)
    profile = DEVICE.releases['1.12'].sharc
    state_end = receipt['state_base'] + 16*engine.STATE_BYTES
    if not state_end <= CAPTURE or CAPTURE + RESERVE != 0x2009fc00:
        raise ValueError('diagnostic capture does not fit before adapter state')
    programs = cpu.selache()/'target/release'
    staged = []
    for source, entry, finish, name in [
        (engine.SOURCE, 'sharc_voice_render.:', 'finish:', 'engine'),
        (cpu.ROOT/'targets/sharc/field909.s', None, 'finish909:', '909'),
    ]:
        text = source.read_text()
        if text.count('\n'+finish+'\n') != 1:
            raise ValueError('normal kernel exit changed')
        text = '.EXTERN x0x_capture_voice_exit;\n' + text
        text = text.replace('\n'+finish+'\n', '\n'+finish+'\n    JUMP x0x_capture_voice_exit;\n')
        if entry:
            if text.count('\n'+entry+'\n') != 1:
                raise ValueError('normal kernel entry changed')
            text = text.replace('\n'+entry+'\n', '\n'+entry+'\n    DM(0x2009fac8)=R4;\n')
        path = folder/(name+'-capture.s'); path.write_text(text)
        obj = folder/(name+'-capture.doj')
        cpu.command([programs/'selas', '-proc', 'ADSP-21569', '-o', obj, path])
        staged.append(obj)
    observer = folder/'capture.doj'
    cpu.command([programs/'selas', '-proc', 'ADSP-21569', '-o', observer, SOURCE])
    executable = folder/'capture.dxe'
    cpu.command([programs/'seld', '-proc', 'ADSP-21569', '-T', folder/'layout.ldf',
                 '-entry', 'sharc_voice_render.', '-Map', folder/'capture.map', '-o', executable,
                 *staged, folder/'choke.doj', folder/'tables.doj', observer])
    raw = executable.read_bytes()
    code, data, _ = engine.read_executable(raw, receipt['layout'])
    if data != bytes.fromhex(original['segments'][2]['hex']):
        raise ValueError('diagnostic changed the model tables')
    doc = voice_artifact(code, data, 0, 20, 0, code_bytes=engine.CODE_BYTES,
                         voice_bytes=engine.STATE_BYTES)
    if doc['voice_state'] != original['voice_state']:
        raise ValueError('diagnostic moved voice state')
    begin = CAPTURE - profile['voice_range'][0]
    zero, = [z for z in doc['zero'] if z['offset_bytes'] <= begin < z['offset_bytes']+z['size_bytes']]
    end = zero['offset_bytes'] + zero['size_bytes']
    if begin + RESERVE > end:
        raise ValueError('diagnostic overlaps initialized data')
    doc['zero'].remove(zero)
    doc['zero'] += [dict(offset_bytes=zero['offset_bytes'], size_bytes=begin-zero['offset_bytes']),
                    dict(offset_bytes=begin+RESERVE, size_bytes=end-begin-RESERVE)]
    doc['zero'] = [z for z in doc['zero'] if z['size_bytes']]
    doc['zero'].sort(key=lambda z: z['offset_bytes'])
    doc['segments'].append(dict(offset_bytes=begin, kind='data',
                                hex=(struct.pack('<I', MAGIC)+bytes(RESERVE-4)).hex()))
    sharc.module_payload(doc, profile)
    if sharc.suspect_shifts(code):
        raise ValueError('diagnostic contains an unsafe immediate shift encoding')
    (folder/'voice.sharc.json').write_text(json.dumps(doc, indent=2)+'\n')
    names = symbols(raw)
    hook = names['x0x_capture_frame']
    if not receipt['entry'] <= hook < receipt['entry'] + len(code)//2:
        raise ValueError('capture hook is outside the author code')
    receipt.update(code_bytes=len(code), capture_address=CAPTURE, capture_bytes=RECORD,
                   capture_reservation=RESERVE, capture_hook_pc=hook,
                   capture_source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                   instrumented_sources_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (folder/'engine-capture.s', folder/'909-capture.s')},
                   artifact_sha256=hashlib.sha256((folder/'voice.sharc.json').read_bytes()).hexdigest())
    (folder/'capture-build.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt, doc


def build(folder, digihealth):
    from . import build as normal
    from elekloader import formats, link, elemod
    from elekloader.sdk import build as sdk
    folder = Path(folder).resolve()
    if folder == (cpu.ROOT/'out/dn2').resolve() or folder.exists() and any(folder.iterdir()):
        raise ValueError('use a new, separate diagnostic output directory')
    folder.mkdir(parents=True, exist_ok=True)
    digihealth = Path(digihealth).resolve()
    if cpu.command(['git', 'status', '--porcelain'], cwd=digihealth).strip():
        raise ValueError('use a clean DigiHealth checkout for firmware provenance')
    health_revision = cpu.revision(digihealth)
    cpu.command(['git', 'merge-base', '--is-ancestor',
                 '85ff7fb7d999c38ad2fedae35977f14b1e3a87de', 'HEAD'], cwd=digihealth)
    entries, revision = firmware.baseline()
    stock = firmware.verify_entry(entries['digitone-mk2'], cpu.ROOT/'firmware', revision)
    normal.stage('dn2', folder/'mod')
    receipt, _ = instrument(folder/'mod')
    mods = [sdk.build(str(cpu.ROOT/'vendor/elekloader/mods'/name), stock['image'], str(folder/'deps'))[0]
            for name in normal.DEVICES['dn2'][2]]
    mods.append(sdk.build(str(folder/'mod'), stock['image'], str(folder/'deps'))[0])
    cpu.command([sys.executable, digihealth/'build.py', '--stock', stock['image'],
                 '--out', folder/'health'])
    health, = (folder/'health').glob('digihealth-*.elemod')
    mods.append(health)
    parsed, device, release = formats.load(stock['image'])
    main = formats.main_image(parsed, device)
    # Only retarget the existing qualified peek hook; keep its site, original bytes,
    # ownership, adapter pins and every linker check. The normal profile stays untouched.
    from tools.sharc_dev.sharc_asm import Asm
    asm = Asm(0); asm.jump_abs(receipt['capture_hook_pc'])
    branch = b''.join(struct.pack('<H', word) for _, words in asm.words() for word in words)
    site, old, usual = release.sharc['peek_hook']
    profile = dict(release.sharc, peek_hook=(site, old, branch.hex()))
    loaded = [elemod.load_any(path) for path in mods]
    standard = link.link(loaded, main, sharc_stream=parsed.section(profile['section']))
    diagnostic_release = replace(release, sharc=profile)
    for mod in loaded:
        mod.rel = diagnostic_release
    linked = link.link(loaded, main, sharc_stream=parsed.section(profile['section']))
    if linked.image != standard.image:
        raise ValueError('diagnostic hook changed the ColdFire main image')
    outputs = formats.write(parsed, formats.pack_main(linked.image, device), device, VERSION,
                            stored_sharc=linked.sharc_stored)
    verification = formats.verify(outputs, parsed, linked.image, device, VERSION,
                                  want_sharc=linked.sharc_stream)
    image = folder/'x0x-diagnostic.syx'; image.write_bytes(outputs['syx'])
    (folder/'link-map.json').write_text(json.dumps(linked.map, indent=2)+'\n')
    (folder/'verification.json').write_text(json.dumps(verification, indent=2)+'\n')
    report = dict(status='build-and-container-checks-passed', version=VERSION,
                  scope='Diagnostic build only; component and physical evidence reported separately',
                  stock=stock, capture=receipt, firmware=str(image),
                  firmware_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                  peek_hook=dict(address=site, stock=old, normal=usual, diagnostic=branch.hex()),
                  coldfire_main_matches_standard_link=True,
                  digihealth_revision=health_revision, digihealth_source=str(digihealth),
                  digihealth_artifact_sha256=hashlib.sha256(health.read_bytes()).hexdigest(),
                  physical_tested=False, flashed=False)
    (folder/'build.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def decode(data):
    if len(data) != RECORD:
        raise ValueError('capture must contain exactly 704 bytes')
    header = struct.unpack_from('<16I', data)
    magic, status, epoch, slot, model, raw_frame, master_frame, pcm_frame, age, blocks, remaining, raw_ptr, master_ptr, pcm_ptr, bank, end_epoch = header
    if (magic != MAGIC or status != 3 or not epoch or epoch != end_epoch
            or slot >= 16 or model not in (1, 2) or not raw_frame
            or len({raw_frame, master_frame, pcm_frame}) != 1
            or blocks != 150 or remaining or age != 4800 or master_ptr != 0x268438
            or raw_ptr % 4 or not any(lo <= raw_ptr and raw_ptr+128 <= hi for lo, hi in
                [(0x240000, 0x270000), (0x2c0000, 0x2ec000),
                 (0x20000000, 0x200fa000), (0x80000000, 0xa0000000)])
            or bank not in (0, 1) or pcm_ptr != 0x2c0478 + bank*256):
        raise ValueError('capture is incomplete, stale, or has mismatched frame/source markers')
    floats = struct.unpack_from('<96f', data, 64)
    import math
    if not all(math.isfinite(v) for v in floats):
        raise ValueError('capture contains non-finite voice/master samples')
    return dict(epoch=epoch, slot=slot, model=model, frame=raw_frame, age=age,
                raw_pointer=raw_ptr, master_pointer=master_ptr, pcm_pointer=pcm_ptr, bank=bank,
                raw=list(floats[:32]), master_left=list(floats[32:64]),
                master_right=list(floats[64:]), pcm=list(struct.unpack_from('<64i', data, 448)))


def client_modules(digihealth):
    checkout = Path(digihealth).resolve()
    if cpu.command(['git', 'status', '--porcelain'], cwd=checkout).strip():
        raise ValueError('use a clean DigiHealth checkout for readback')
    cpu.command(['git', 'merge-base', '--is-ancestor',
                 'afc751d67b1b1575f7a5fc40f104c11451fc3ea5', 'HEAD'], cwd=checkout)
    tools = checkout/'tools'
    sys.path.insert(0, str(tools))
    try:
        modules = [importlib.import_module(name) for name in ('keymap', 'digiusb', 'midimido')]
        if any(Path(module.__file__).resolve().parent != tools for module in modules):
            raise ValueError('DigiHealth module loaded from a different checkout; restart the client')
        return modules[1:]
    finally:
        sys.path.pop(0)


def read(folder, digihealth):
    """No MIDI triggers or firmware writes; call after a hit has frozen its record."""
    health, midimido = client_modules(digihealth)
    port = midimido.Port()
    try:
        diag = health.Diag(port)
        if health.RemoteKeys(diag).product != 3:
            raise ValueError('DN2 OS 1.12 revision-3 helper required')
        before = health.dsp_peek(diag, CAPTURE, 64)
        data = health.dsp_peek(diag, CAPTURE, RECORD)
        after = health.dsp_peek(diag, CAPTURE, 64)
        if before != after or data[:64] != before:
            raise ValueError('capture changed during readback; leave six seconds between hits')
        result = decode(data)
    finally:
        port.close()
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder/f"capture-{result['epoch']:06d}"
    for path, payload in [(destination.with_suffix('.bin'), data),
                          (destination.with_suffix('.json'), (json.dumps(result, indent=2)+'\n').encode())]:
        with path.open('xb') as output:
            output.write(payload)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'read'])
    parser.add_argument('folder', type=Path)
    parser.add_argument('--digihealth', type=Path, required=True, help='clean matched DN2 DigiHealth source checkout')
    args = parser.parse_args()
    print(json.dumps(build(args.folder, args.digihealth) if args.action == 'build' else read(args.folder, args.digihealth), indent=2))


if __name__ == '__main__':
    main()
