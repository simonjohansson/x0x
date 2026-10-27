"""Five-setting diagnostic: actual current ASM versus captured 808 software audio."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import struct

from . import analysis, body808, coupling808, cpu, tone808
from .comparison import _waveform

ROOT = cpu.ROOT
OUT = ROOT / "out/reference/808-baseline"
CAPTURES = ROOT / "research/reference/808/captures"
RATE, FRAMES = 48000, 96000
CASES = {"default": (128,128), "dark-short": (0,0), "bright-short": (255,0),
         "dark-long": (0,255), "bright-long": (255,255)}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_position(displayed):
    """Nearest native UI position: captured midpoint 128 maps to approved default64."""
    if type(displayed) is not int or not 0 <= displayed <= 255:
        raise ValueError("reference position must be an integer in 0..255")
    return round(displayed * 127 / 255) * 256


def source_hashes():
    paths = ["targets/coldfire/body808.s", "targets/coldfire/tone808.s",
             "targets/coldfire/coupling808.s", "targets/sharc/body808.s",
             "tools/x0x/body808.py", "tools/x0x/retrigger808.py", "tools/x0x/pulse808.py",
             "tools/x0x/tone808.py", "tools/x0x/coupling808.py"]
    return {name:digest(ROOT/name) for name in paths}


def checked_kernel(name):
    folder = ROOT / "out/coldfire" / name
    report = json.loads((folder/"report.json").read_text())
    image = folder/"diagnostic.bin"
    source = ROOT/"targets/coldfire"/(name+".s")
    if report["status"] != "passed" or digest(source) != report["source_sha256"]:
        raise RuntimeError("stale kernel proof; run mise run test:808:body")
    if digest(image) != report["image_sha256"]:
        raise ValueError("compiled kernel hash mismatch: "+name)
    return image.read_bytes(), dict(source_sha256=digest(source),image_sha256=digest(image),
                                    component_report_sha256=digest(folder/"report.json"))


def render(backend):
    OUT.mkdir(parents=True,exist_ok=True)
    if backend == "coldfire":
        from .coldfire_body808 import Runner as Body
        from .coldfire_tone808 import Runner as Tone
        from .coldfire_coupling808 import Runner as Coupling
        images = [checked_kernel(name) for name in ("body808","tone808","coupling808")]
        provenance = [row[1] for row in images]
    else:
        from . import sharc_callback, sharc_selector
        from .sharc_body808 import STATE_BYTES
        folder = ROOT/"out/sharc/body808"
        report=json.loads((folder/"report.json").read_text())
        code,entry=cpu.sharc_code((folder/"callback.dxe").read_bytes())
        if report['status']!='passed' or digest(ROOT/'targets/sharc/body808.s')!=report['source_sha256']:
            raise RuntimeError("stale SHARC proof; run mise run test:808:body")
        if hashlib.sha256(code).hexdigest()!=report['image_sha256']:
            raise ValueError("SHARC executable does not match its component proof")
        sharc_callback.decoded_instructions(code,entry)
        provenance=dict(source_sha256=report['source_sha256'],image_sha256=report['image_sha256'],
                        component_report_sha256=digest(folder/'report.json'),entry=entry)
    records={}
    for label,(tone,decay) in CASES.items():
        print(f"Rendering {backend} {label}: {FRAMES/RATE:g} seconds",flush=True)
        tr,dr=raw_position(tone),raw_position(decay)
        if backend=='coldfire':
            b,t,c=Body(images[0][0],state_words=5),Tone(images[1][0]),Coupling(images[2][0])
        else:
            machine=sharc_selector.SelectorRunner(code,entry,state_bytes=STATE_BYTES,
                extra_slot_state_offset=128,tone_state_offset=256,coupling_state_offset=320,pulse_state_offset=448, companion_state_offset=512, main_state_offset=576, coefficient_state_offset=640)
        samples=[]
        for n in range(0,FRAMES,32):
            if backend=='coldfire':
                words=b.render(start=int(n==0),decay_raw=dr)
                samples.extend(v/2**31 for v in c.render(t.render(words,tr)))
            else:
                row=sharc_selector.case(label,flags=int(n==0),model=0,pitch=36<<8)
                row['params']=[0]*40
                row['params'][0],row['params'][1],row['params'][2]=tr,dr,16384
                block,_=machine.call_raw(row,True)
                samples.extend(block)
        expected=coupling808.filter_reference(tone808.filter_reference(body808.reference(FRAMES,dr),tr))
        error=max(abs(a-b) for a,b in zip(samples,expected))
        assert error<=1e-5,(backend,label,error)
        path=OUT/f'{backend}-{label}.f32'
        path.write_bytes(struct.pack(f'<{FRAMES}f',*samples))
        records[label]=dict(tone_raw=tr,decay_raw=dr,path=path.name,sha256=digest(path),
                            oracle_maximum_error_fs=error)
    result=dict(backend=backend,scope='actual ASM; isolated raw output, no native AMP/filter/FX',
        project_revision=cpu.revision(ROOT),source_hashes=source_hashes(),kernels=provenance,
        sample_rate=RATE,frames=FRAMES,cases=records,
        sdk_input=dict(pitch=36<<8,attack=16384,model=0,other_words=0) if backend=='sharc' else None,
        trigger_policy='START at0; prototype has fixed intrinsic excitation and ignores pitch/strength; no native AMP',
        emulator_revision=cpu.revision(ROOT/'vendor'/('digiemu' if backend=='coldfire' else 'digikit')))
    (OUT/f'{backend}.json').write_text(json.dumps(result,indent=2)+'\n')


def load_backend(backend):
    metadata=json.loads((OUT/f'{backend}.json').read_text())
    assert metadata['source_hashes']==source_hashes(),'ASM render belongs to different sources'
    assert metadata['backend']==backend and metadata['frames']==FRAMES and metadata['sample_rate']==RATE
    assert set(metadata['cases'])==set(CASES)
    if backend=='sharc':assert metadata['sdk_input']==dict(pitch=36<<8,attack=16384,model=0,other_words=0)
    result={}
    for label,row in metadata['cases'].items():
        assert (row['tone_raw'],row['decay_raw'])==tuple(raw_position(x) for x in CASES[label])
        path=OUT/row['path']
        assert digest(path)==row['sha256'],path
        result[label]=list(struct.unpack(f'<{FRAMES}f',path.read_bytes()))
    return result,metadata


def references():
    import numpy as np
    import soundfile as sf
    protocol=json.loads((CAPTURES/'protocol.json').read_text())
    tests={row['name']:row for row in protocol['tests']}
    wanted={f'grid-t{t:03}-d{d:03}-r{r}' for t,d in CASES.values() for r in (1,2,3)}
    with (CAPTURES/'recordings.csv').open() as stream:
        records={r['name']:r for r in csv.DictReader(stream) if r['name'] in wanted}
    assert len(records)==15
    readbacks={name+suffix:{} for name in wanted for suffix in (':before',':after')}
    with (CAPTURES/'settings.tsv').open() as stream:
        for row in csv.DictReader(stream,delimiter='\t'):
            if row['capture'] in readbacks:
                readbacks[row['capture']][int(row['index'])]=row
    result,provenance={},{}
    frozen=None
    for label,(t,d) in CASES.items():
        previous=None; hashes=[]
        for repeat in (1,2,3):
            name=f'grid-t{t:03}-d{d:03}-r{repeat}'
            test=tests[name];record=records[name];path=CAPTURES/(name+'.wav')
            assert test['split']=='grid' and len(test['notes'])==1
            note=test['notes'][0]
            assert note==dict(start=1,finish=1.01,pitch=36,velocity=100),note
            assert (int(record['tone_displayed']),int(record['decay_displayed']))==(t,d)
            assert digest(path)==record['sha256'],path
            before,after=readbacks[name+':before'],readbacks[name+':after']
            assert set(before)==set(after)==set(range(193)),name
            assert all(before[i]['normalized']==after[i]['normalized'] for i in range(59)),name
            assert (int(before[3]['displayed']),int(before[2]['displayed']))==(t,d),name
            fixed={i:(before[i]['parameter'],before[i]['displayed']) for i in range(59) if i not in (2,3)}
            if frozen is None:frozen=fixed
            assert fixed==frozen,'fixed source controls changed'
            assert before[0]['displayed']=='204' and all(before[i]['displayed']=='128' for i in (1,4,5))
            project=path.with_suffix('.RPP')
            import re
            state=project.read_text()
            assert float(re.search(r'^\s+VOLPAN (\S+)',state,re.M)[1])==.25
            assert float(re.search(r'^\s+MASTER_VOLUME (\S+)',state,re.M)[1])==1
            assert not re.search(r'^\s+HWOUT ',state,re.M) and 'REC 0 -1 0 ' in state
            info=sf.info(path)
            data,rate=sf.read(path,always_2d=True,dtype='float64')
            assert rate==RATE and info.subtype=='FLOAT' and data.shape==(13*RATE,2)
            assert np.isfinite(data).all() and np.array_equal(data[:,0],data[:,1])
            assert np.max(abs(data))<1 and np.max(abs(data[:RATE]))<1e-7
            assert np.max(abs(data[-9600:]))<1e-7
            mono=data[RATE:,0]
            if previous is not None:assert np.array_equal(previous,mono),'fresh repeat changed'
            previous=mono
            hashes.append(dict(name=name,sha256=record['sha256'],project_sha256=digest(project)))
        result[label]=mono.tolist()
        provenance[label]=dict(files=hashes,repeats=3,maximum_repeat_difference_fs=0,
            reference_tone=t,reference_decay=d,tone_raw=raw_position(t),decay_raw=raw_position(d),
            midi_on_sample=RATE,crop='scheduled MIDI, no onset trimming',channels='verified identical; left used')
    return result,dict(cases=provenance,
        identity='Roland TR-808 VST3 1.1.4 build22074; REAPER7.82 macOS-arm64',
        fixed_source_controls=frozen,metadata_sha256={f:digest(CAPTURES/f)
        for f in ('protocol.json','recordings.csv','settings.tsv')},held_out_audio_read=False)


def metrics(samples):
    a=analysis.analyze(samples,RATE)
    cycles=a['frequency']['cycles']
    periods={}
    for label,lo,hi in [('early',.01,.05),('body',.05,.2),('late',.2,.5)]:
        selected=[c['frequency_hz'] for c in cycles if c['valid'] and lo<=(c['start_sample']+c['end_sample'])/2/RATE<hi]
        periods[label]=dict(valid_cycles=len(selected),median_hz=statistics.median(selected) if selected else None)
    envelope=[]
    for n in range(0,len(samples),480):
        chunk=samples[n:n+480]
        envelope.append(math.sqrt(math.fsum(x*x for x in chunk)/len(chunk)))
    return dict(analysis=a,pitch_windows=periods,envelope_rms_10ms=envelope,
                energy_after_1s_fraction=sum(x*x for x in samples[RATE:])/sum(x*x for x in samples))


def residual(actual,expected,lag=0):
    if lag>=0:a,e=actual[lag:],expected[:len(expected)-lag]
    else:a,e=actual[:len(actual)+lag],expected[-lag:]
    return _waveform(a,e)


def common_lag(actual,expected,limit=480):
    """One default-only positive-correlation lag; supplemental, not a latency claim."""
    import numpy as np
    a=np.asarray(actual[:9600]);e=np.asarray(expected[:9600])
    scores=[]
    for lag in range(-limit,limit+1):
        av,ev=(a[lag:],e[:len(e)-lag]) if lag>=0 else (a[:len(a)+lag],e[-lag:])
        scores.append(float(np.dot(av,ev)/math.sqrt(np.dot(av,av)*np.dot(ev,ev))))
    offset=int(np.argmax(scores))-limit
    return dict(samples=offset,seconds=offset/RATE,correlation=max(scores),search_limit_samples=limit,
        window_samples=[0,9600],fit_case='default only',affects_primary_metrics=False,
        at_search_boundary=abs(offset)==limit,
        interpretation='includes phase/pitch/attack differences; not measured device latency')


def report():
    OUT.mkdir(parents=True,exist_ok=True)
    refs,reference_provenance=references()
    cf,cfmeta=load_backend('coldfire');sh,shmeta=load_backend('sharc')
    rows={};corrected={label:[x*4 for x in samples[:FRAMES]] for label,samples in refs.items()}
    probe=[0.]*20+[1.,.5,-.2]+[0.]*2000
    assert common_lag([0.]*7+probe,probe+[0.]*7,20)['samples']==7
    assert common_lag(probe+[0.]*7,[0.]*7+probe,20)['samples']==-7
    lag=common_lag(cf['default'],corrected['default'])
    for label in CASES:
        rows[label]=dict(reference_recorded=metrics(refs[label][:FRAMES]),
            reference_host_gain_removed=metrics(corrected[label]),reference_full_12s=metrics(refs[label]),
            reference_energy_after_2s_fraction=sum(x*x for x in refs[label][FRAMES:])/sum(x*x for x in refs[label]),
            coldfire=metrics(cf[label]),sharc=metrics(sh[label]),
            coldfire_vs_reference_raw=residual(cf[label],refs[label][:FRAMES]),
            coldfire_vs_reference_host_gain_removed=residual(cf[label],corrected[label]),
            supplemental_common_lag_residual=residual(cf[label],corrected[label],lag['samples']),
            cpu_maximum_difference_fs=max(abs(x-y) for x,y in zip(cf[label],sh[label])))
        assert rows[label]['cpu_maximum_difference_fs']<=1e-5,(label,rows[label]['cpu_maximum_difference_fs'])
    result=dict(status='diagnostic_complete',fidelity_verdict='not qualified; no fidelity limits frozen or tuning performed',
        project_revision=cpu.revision(ROOT),reference_provenance=reference_provenance,
        comparison_harness_sha256=digest(Path(__file__)),
        analyzer_sha256=digest(ROOT/'tools/x0x/analysis.py'),comparator_sha256=digest(ROOT/'tools/x0x/comparison.py'),
        renders=dict(coldfire=cfmeta,sharc=shmeta),common_lag=lag,cases=rows,
        sample_rate=RATE,comparison_frames=FRAMES,window_seconds=FRAMES/RATE,
        reference_gain=4,gain_reason='remove only documented fixed host track attenuation0.25',
        fitted_gain=False,primary_alignment_samples=0,common_lag_is_supplemental=True,
        scope='raw current ASM versus software-reference recordings; no native OS or hardware proof',
        control_mapping='nearest native UI step; midpoint reference128/255 versus approved x0x64/127',
        held_out_audio_read=False)
    (OUT/'report.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    from .reference808_html import write_report
    write_report(result,corrected,cf,sh,OUT)
    print('Diagnostic report:',OUT/'index.html',flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['all','coldfire','sharc','report'],default='all')
    phase=parser.parse_args().phase
    if phase in ('all','coldfire'):render('coldfire')
    if phase in ('all','sharc'):render('sharc')
    if phase in ('all','report'):report()


if __name__=='__main__':main()
