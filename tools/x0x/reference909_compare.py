"""Bounded five-setting 909 training diagnostic from verified actual CPU renders."""
import csv
import hashlib
import itertools
import json
import math
import re
import statistics
import struct

from . import analysis, body909, cpu
from .reference808_compare import digest, raw_position, residual

ROOT=cpu.ROOT
OUT=ROOT/'out/reference/909-baseline'
CAPTURES=ROOT/'research/reference/909/captures'
COMPONENTS=ROOT/'out/909-shaping'
RATE,FRAMES=48000,24000
CASES={'default':(128,128),'low-tune-short':(0,0),'high-tune-short':(255,0),
       'low-tune-long':(0,255),'high-tune-long':(255,255)}


def names(tune,decay):
    """Construct only the selected training filenames; never discover validation audio."""
    if type(tune) is not int or type(decay) is not int or (tune,decay) not in CASES.values():
        raise ValueError('only the five selected training settings are permitted')
    return [f'grid-u{tune:03}-a128-d{decay:03}-r{r}' for r in (1,2,3)]


def project_gain(text):
    """Invert only the independently audited fixed host attenuation, never fit audio."""
    assert len(re.findall(r'^  <TRACK ',text,re.M))==1
    assert len(re.findall(r'^      <VST ',text,re.M))==1 and 'VST3i: TR-909 (Roland)' in text
    assert len(re.findall(r'^      FXID ',text,re.M))==1
    volume=re.search(r'^    VOLPAN (\S+) (\S+)',text,re.M)
    master=re.search(r'^  MASTER_VOLUME (\S+) (\S+)',text,re.M)
    assert volume and master and tuple(map(float,volume.groups()))==(.25,0)
    assert tuple(map(float,master.groups()))==(1,0)
    assert re.search(r'^  MASTERHWOUT\s*$',text,re.M)
    assert not re.search(r'^\s+HWOUT ',text,re.M) and 'REC 0 -1 0 ' in text
    assert len(re.findall(r'^      BYPASS 0 0 0\s*$',text,re.M))==1
    return 1/(float(volume[1])*float(master[1]))


def source_hashes():
    return {p:digest(ROOT/p) for p in ('targets/coldfire/body909.s','targets/sharc/body808.s',
            'tools/x0x/body909.py','tools/x0x/coldfire_body909.py','tools/x0x/sharc_body808.py',
            'tools/x0x/reference909_compare.py','tools/x0x/reference808_compare.py','tools/x0x/analysis.py','tools/x0x/comparison.py')}


def component_audio(backend):
    """Reuse actual component output, explicitly without Tune/Attack delivery proof."""
    folder=COMPONENTS/('coldfire' if backend=='coldfire' else 'sharc')
    metadata=json.loads((folder/'report.json').read_text())
    proof=json.loads((COMPONENTS/'comparison.json').read_text())
    assert proof['status']=='passed'
    assert proof['component_reports_sha256'][str((folder/'report.json').relative_to(COMPONENTS))]==digest(folder/'report.json')
    assert proof['source_sha256']['tools/x0x/body909.py']==digest(ROOT/'tools/x0x/body909.py')
    proven={row['raw']:row for row in proof['cases']}
    source=ROOT/('targets/coldfire/body909.s' if backend=='coldfire' else 'targets/sharc/body808.s')
    assert metadata['status']=='passed' and metadata['frames']==FRAMES
    assert metadata['source_sha256']==digest(source),'stale actual CPU component proof'
    if backend=='coldfire':
        image=folder/'diagnostic.bin';image_hash=digest(image)
    else:
        code,entry=cpu.sharc_code((folder/'callback.dxe').read_bytes())
        image_hash=hashlib.sha256(code).hexdigest()
    assert image_hash==metadata['image_sha256'],'component executable hash changed'
    result,records={},{}
    for label,(tune,decay) in CASES.items():
        raw=raw_position(decay)
        path=folder/(f'samples_{raw}.json' if backend=='coldfire' else f'samples_909_{raw}.f32')
        assert digest(path)==proven[raw]['coldfire_samples_sha256' if backend=='coldfire' else 'sharc_samples_sha256']
        samples=json.loads(path.read_text()) if backend=='coldfire' else list(struct.unpack('<24000f',path.read_bytes()))
        assert len(samples)==FRAMES and all(math.isfinite(x) for x in samples)
        error=max(abs(a-b) for a,b in zip(samples,body909.reference(FRAMES,raw)))
        assert error<=1e-5,(backend,label,error)
        target=OUT/f'{backend}-{label}.f32'
        target.write_bytes(struct.pack('<24000f',*samples))
        result[label]=samples
        records[label]=dict(path=target.name,sha256=digest(target),actual_component_samples=str(path.relative_to(ROOT)),
            actual_component_samples_sha256=digest(path),requested_reference_tune=tune,reference_attack=128,
            decay_raw=raw,actual_tune_raw=16384 if backend=='sharc' else None,actual_attack_raw=12345 if backend=='sharc' else None,
            actual_pitch_word=15487 if backend=='sharc' else None,
            tune_and_attack_implemented=False,oracle_maximum_error_fs=error)
    report=dict(backend=backend,scope='reused actual guarded component output; not native delivery qualification',
        sample_rate=RATE,frames=FRAMES,source_hashes=source_hashes(),cases=records,
        component_report=str((folder/'report.json').relative_to(ROOT)),component_report_sha256=digest(folder/'report.json'),
        matching_comparison_sha256=digest(COMPONENTS/'comparison.json'),
        executable_sha256=image_hash,project_revision=metadata.get('project_revision'),
        control_limit='Tune and Attack are unimplemented; same Decay reuses identical actual audio, not requested-Tune delivery proof')
    (OUT/f'{backend}.json').write_text(json.dumps(report,indent=2)+'\n')
    return result,report


def references():
    import numpy as np
    import soundfile as sf
    protocol=json.loads((CAPTURES/'protocol.json').read_text())
    assert protocol['kind']=='matrix' and protocol['route']=='main' and protocol['channels']==2
    selected={name for t,d in CASES.values() for name in names(t,d)}
    tests={r['name']:r for r in protocol['tests'] if r['name'] in selected}
    with (CAPTURES/'recordings.csv').open() as stream:
        records={r['name']:r for r in csv.DictReader(stream) if r['name'] in selected}
    assert set(tests)==set(records)==selected
    settings={name+suffix:{} for name in selected for suffix in (':before',':after')}
    with (CAPTURES/'settings.tsv').open() as stream:
        for row in csv.DictReader(stream,delimiter='\t'):
            if row['capture'] in settings:settings[row['capture']][int(row['index'])]=row
    results,provenance={},{}
    frozen=None
    for label,(tune,decay) in CASES.items():
        takes,full,files=[],[],[]
        for name in names(tune,decay):
            test,record=tests[name],records[name]
            assert test['split']==record['split']=='grid' and test['duration']==17
            assert test['notes']==[dict(start=1,finish=1.01,pitch=36,velocity=100)]
            assert (int(record['tune_displayed']),int(record['attack_displayed']),int(record['decay_displayed']))==(tune,128,decay)
            before,after=settings[name+':before'],settings[name+':after']
            assert set(before)==set(after)==set(range(197))
            assert all(before[i]['normalized']==after[i]['normalized'] for i in before)
            assert (int(before[1]['displayed']),int(before[3]['displayed']),int(before[2]['displayed']))==(tune,128,decay)
            fixed={i:(r['parameter'],r['displayed'],r['normalized']) for i,r in before.items() if i not in (1,2)}
            if frozen is None:frozen=fixed
            assert fixed==frozen,'fixed reference controls changed'
            assert before[0]['displayed']=='220' and all(before[i]['displayed']=='128' for i in (3,4,5))
            assert before[49]['displayed']=='108' and before[50]['displayed']==before[51]['displayed']=='0'
            assert [float(before[i]['normalized']) for i in (194,195,196)]==[0,1,0]
            assert all(r['displayed']=='0' for i,r in before.items() if r['parameter'].endswith(' LEVEL') and i not in (0,50))
            project=CAPTURES/(name+'.RPP');gain=project_gain(project.read_text())
            path=CAPTURES/(name+'.wav');assert digest(path)==record['sha256'],name
            info=sf.info(path);data,rate=sf.read(path,always_2d=True,dtype='float64')
            assert rate==RATE and info.subtype=='FLOAT' and data.shape==(17*RATE,2)
            assert np.isfinite(data).all() and np.array_equal(data[:,0],data[:,1])
            assert np.max(abs(data))<1 and np.max(abs(data[:RATE]))<1e-7 and np.max(abs(data[-9600:]))<1e-7
            mono=data[RATE:,0]
            takes.append(mono[:FRAMES].tolist());full.append(mono.copy())
            files.append(dict(name=name,sha256=record['sha256'],project_sha256=digest(project),reference_gain=gain,
                onset_after_scheduled_midi_samples=int(record['onset_sample'])-RATE))
        pairs=[]
        for a,b in itertools.combinations(full,2):
            assert np.array_equal(a[2400:],b[2400:]),'fresh references differ beyond documented first50ms'
            pairs.append(dict(maximum_difference_fs=float(np.max(abs(a-b))),first_50ms_rms_difference_fs=float(np.sqrt(np.mean((a[:2400]-b[:2400])**2)))))
        results[label]=takes
        provenance[label]=dict(files=files,repeat_pairs=pairs,repeats=3,all_repeats_preserved=True,
            scheduled_crop_sample=RATE,onset_alignment_samples=0,channels='verified identical; left used',
            reference_tune=tune,reference_attack=128,reference_decay=decay)
    return results,dict(identity='Roland TR-909 VST3 1.1.3 build22072; REAPER7.82 macOS-arm64',cases=provenance,
        fixed_source_controls=frozen,metadata_sha256={f:digest(CAPTURES/f) for f in ('protocol.json','recordings.csv','settings.tsv')},
        held_out_audio_read=False)


def measurements(samples):
    report=analysis.analyze(samples,RATE)
    windows={}
    for name,lo,hi in [('early',.01,.05),('body',.05,.2),('late',.2,.5)]:
        cycles=[r for r in report['frequency']['cycles'] if r['valid'] and lo<=(r['start_sample']+r['end_sample'])/(2*RATE)<hi]
        windows[name]=dict(valid_cycles=len(cycles),reliable=len(cycles)>=3,
            median_hz=statistics.median(r['frequency_hz'] for r in cycles) if len(cycles)>=3 else None)
    return dict(analysis=report,pitch_windows=windows,envelope_rms_10ms=[math.sqrt(math.fsum(v*v for v in samples[i:i+480])/len(samples[i:i+480])) for i in range(0,len(samples),480)])


def report():
    OUT.mkdir(parents=True,exist_ok=True)
    frozen=source_hashes()
    refs,provenance=references()
    cf,cm=component_audio('coldfire');sh,sm=component_audio('sharc')
    rows={}
    for label,takes in refs.items():
        repeats=[]
        for take in takes:
            corrected=[4*x for x in take]
            repeats.append(dict(reference_as_recorded=measurements(take),reference=measurements(corrected),
                coldfire_residual=residual(cf[label],corrected),sharc_residual=residual(sh[label],corrected),
                coldfire_as_recorded_residual=residual(cf[label],take),sharc_as_recorded_residual=residual(sh[label],take),
                early_residuals={name:dict(coldfire=residual(cf[label][:n],corrected[:n]),sharc=residual(sh[label][:n],corrected[:n]))
                    for name,n in [('first_25ms',1200),('first_50ms',2400),('first_150ms',7200)]}))
        cross=max(abs(a-b) for a,b in zip(cf[label],sh[label]));assert cross<=1e-5
        rows[label]=dict(coldfire=measurements(cf[label]),sharc=measurements(sh[label]),repeats=repeats,cpu_maximum_error_fs=cross)
    assert frozen==source_hashes(),'source changed during comparison'
    result=dict(scope='first0–500ms training-only actual CPU diagnostic; no native or full-tail/fidelity acceptance',
        project_revision=cpu.revision(ROOT),
        sample_rate=RATE,frames=FRAMES,reference_gain=4,gain_reason='independently verified909projecttrack.25/master1; as-recorded errors retained',
        normalization=False,fitted_gain=False,alignment_samples=0,held_out_audio_read=False,source_hashes=frozen,
        reference_provenance=provenance,renders=dict(coldfire=cm,sharc=sm),cases=rows,
        control_limit='Tune/Attack unimplemented; equal-Decay corner rows reuse the same actual component audio, not delivery proof',
        fidelity_verdict='unqualified')
    (OUT/'measurements.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result


if __name__=='__main__':
    report()
    print('Bounded909diagnostic:',OUT/'measurements.json')
