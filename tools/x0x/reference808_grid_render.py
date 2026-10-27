"""Actual 808 grid rendering; invoked with archived x0x modules first."""
import array
import hashlib
import json
from pathlib import Path
import struct
import time

from x0x import body808, coupling808, cpu, tone808

RATE, FRAMES = 48000, 576000


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw(displayed):
    return round(displayed * 127 / 255) * 256


def render(backend, output, captures, frozen_metadata):
    assert cpu.ROOT == Path(frozen_metadata['frozen_source_root'])
    import csv
    with (captures/'recordings.csv').open() as stream:
        rows = [r for r in csv.DictReader(stream) if r['split'] == 'grid']
    settings = sorted({(int(r['tone_displayed']), int(r['decay_displayed'])) for r in rows}, key=lambda k:(k[1], k[0]))
    assert len(rows) == 243 and len(settings) == 81
    folder = output/backend; folder.mkdir(parents=True, exist_ok=True)
    kernels = {}; proofs = {}; bodies = {}; started = time.monotonic()
    if backend == 'coldfire':
        from x0x import coldfire_body808, coldfire_tone808, coldfire_coupling808
        modules = [coldfire_body808, coldfire_tone808, coldfire_coupling808]
        for name, module in zip(('body808','tone808','coupling808'), modules):
            target = folder/'kernels'/name
            canonical = cpu.ROOT/'out/coldfire'/name
            module.run(canonical)
            import shutil
            shutil.copytree(canonical,target,dirs_exist_ok=True)
            receipt = json.loads((target/'report.json').read_text())
            image = target/'diagnostic.bin'
            assert receipt['status']=='passed' and receipt['source_sha256']==digest(cpu.ROOT/f'targets/coldfire/{name}.s')
            assert receipt['image_sha256']==digest(image)
            kernels[name] = image.read_bytes()
            proofs[name] = dict(source_sha256=receipt['source_sha256'], image_sha256=digest(image),
                                component_report_sha256=digest(target/'report.json'))
    else:
        try:
            from .reference_grid_sharc import FastRunner, prepare
        except ImportError:
            from reference_grid_sharc import FastRunner, prepare
        support = output/'native-support'
        proofs = prepare(frozen_metadata, support)
        machine = FastRunner(support)
    records = []; previous_decay = None
    for tone, decay in settings:
        case_start = time.monotonic(); tr, dr = raw(tone), raw(decay)
        if decay != previous_decay:
            oracle_body = body808.reference(FRAMES, dr); previous_decay = decay
            if backend == 'coldfire':
                body = modules[0].Runner(kernels['body808'], state_words=5)
                words = array.array('i')
                for n in range(0, FRAMES, 32):
                    words.extend(body.render(start=int(n==0), decay_raw=dr))
                body_path = folder/f'body-d{decay:03}.i32'
                body_path.write_bytes(struct.pack(f'<{FRAMES}i', *words))
                error = max(abs(x/2**31-y) for x,y in zip(words, oracle_body))
                bodies[str(decay)] = dict(path=body_path.name, sha256=digest(body_path),
                    oracle_maximum_error_fs=error, numeric_status='passed' if error<=1e-5 else 'failed')
        expected = coupling808.filter_reference(tone808.filter_reference(oracle_body, tr))
        if backend == 'coldfire':
            t = modules[1].Runner(kernels['tone808']); c = modules[2].Runner(kernels['coupling808'])
            samples = array.array('f')
            for n in range(0, FRAMES, 32):
                samples.extend(v/2**31 for v in c.render(t.render(words[n:n+32], tr)))
            blob = struct.pack(f'<{FRAMES}f', *samples)
        else:
            blob = machine.render(808, tr, dr, FRAMES, attack_raw=16384)
        actual = struct.unpack(f'<{FRAMES}f', blob)
        import math
        assert all(math.isfinite(v) for v in actual)
        error = max(abs(x-y) for x,y in zip(actual, expected))
        path = folder/f'grid-t{tone:03}-d{decay:03}.f32'; path.write_bytes(blob)
        records.append(dict(tone_displayed=tone,decay_displayed=decay,tone_raw=tr,decay_raw=dr,
            path=path.name,sha256=digest(path),frames=FRAMES,sample_rate=RATE,
            oracle_maximum_error_fs=error,numeric_limit_fs=1e-5,
            numeric_status='passed' if error<=1e-5 else 'failed',wall_seconds=time.monotonic()-case_start))
        (folder/'progress.json').write_text(json.dumps(dict(completed=len(records),total=81,cases=records),indent=2)+'\n')
        print(json.dumps(dict(event='rendered',backend=backend,completed=len(records),total=81,**records[-1])),flush=True)
    report = dict(commit=frozen_metadata['commit'],sample_rate=RATE,frames=FRAMES,cases=records,
        status='passed' if all(r['numeric_status']=='passed' for r in records) and
                          all(r['numeric_status']=='passed' for r in bodies.values()) else 'numeric_failures',
        scope='actual isolated808 CPU components; no nativeOS or physical claim',kernel_proofs=proofs,
        frozen_source=frozen_metadata,driver_sha256=digest(Path(__file__)),
        body_cache=bodies,body_reuse='actual body has START/Decay ABI only; actual words feed independent Tone/C47 stages',
        guards='ColdFire normal accepted per-call/context/write guards; SHARC NativeCore per-call return/trap/boundary guards plus separate architectural preflight; full-tail independentoracle1e-5',
        wall_seconds=time.monotonic()-started,normalization=False,alignment_samples=0,fitted_gain=False)
    (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    render_histories(backend,output,captures,kernels if backend=='coldfire' else support,frozen_metadata['commit'])


def render_histories(backend, output, captures, images_or_support, commit):
    import math
    protocol = json.loads((captures/'protocol.json').read_text())
    tests = [t for t in protocol['tests'] if t['split']=='history']; assert len(tests)==7
    folder = output/'history'/f'{backend}-current'; folder.mkdir(parents=True,exist_ok=True)
    if backend == 'coldfire':
        from x0x.coldfire_body808 import Runner as Body
        from x0x.coldfire_tone808 import Runner as Tone
        from x0x.coldfire_coupling808 import Runner as Coupling
        images = images_or_support
    else:
        try:
            from .reference_grid_sharc import FastRunner
        except ImportError:
            from reference_grid_sharc import FastRunner
        from x0x import sharc_selector
    records = []
    for test in tests:
        tone,decay = round(test['tone']*255),round(test['decay']*255)
        assert all(n['pitch']==36 and n['velocity']==100 for n in test['notes'])
        schedule = [dict(reference_midi_sample=round((n['start']-1)*RATE),
                         component_start_sample=math.ceil(round((n['start']-1)*RATE)/32)*32,
                         note_finish_sample=round((n['finish']-1)*RATE)) for n in test['notes']]
        starts = {s['component_start_sample'] for s in schedule}
        frames = round((test['duration']-1)*RATE); assert frames%32==0
        if backend == 'coldfire':
            body = Body(images['body808'],state_words=5)
        else:
            machine = FastRunner(images_or_support); row = sharc_selector.case(test['name'],model=0)
            row['params'][0:3] = [raw(tone),raw(decay),16384]
        blob = bytearray()
        for n in range(0,frames,32):
            if backend == 'coldfire':
                if n in starts:
                    t=Tone(images['tone808']);c=Coupling(images['coupling808'])
                samples = [v/2**31 for v in c.render(t.render(body.render(start=int(n in starts),decay_raw=raw(decay)),raw(tone)))]
                blob.extend(struct.pack('<32f',*samples))
            else:
                row['flags']=int(n in starts);blob.extend(struct.pack('<32I',*machine.call_raw(row)))
        path=folder/(test['name']+'.f32');path.write_bytes(blob)
        records.append(dict(name=test['name'],tone_displayed=tone,decay_displayed=decay,
            tone_raw=raw(tone),decay_raw=raw(decay),frames=frames,sample_rate=RATE,
            path=path.name,sha256=digest(path),schedule=schedule))
    (folder/'report.json').write_text(json.dumps(dict(commit=commit,
        sample_rate=RATE,cases=records,declared_test_voice='one explicit componentvoice; no nativeallocatoridentity',
        START_policy='body,Tone,C47 clear; NOTE-OFF inert',scheduling='ceil32 from scheduledMIDI, noalignment',
        driver_sha256=digest(Path(__file__))),indent=2)+'\n')
