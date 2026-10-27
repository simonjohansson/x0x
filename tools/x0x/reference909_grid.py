"""Full training-grid diagnostic of frozen accepted909 CPU renders, no fitting.

Run this file directly so the frozen accepted tool package can be first on
PYTHONPATH. Rendering receipts are separate from reference/corpus measurements.
Grid stages read only split=grid audio; separate component stages replay seven
histories. Held-out audio and native/history acceptance remain untouched.
"""
import argparse
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import subprocess

RATE=48000
FRAMES=16*RATE
POSITIONS=(0,32,64,96,128,159,191,223,255)
WINDOWS={'first6ms':(0,288),'first25ms':(0,1200),'first50ms':(0,2400),
         'first150ms':(0,7200),'first500ms':(0,24000),'halfTo2s':(24000,96000),
         'tail2to16s':(96000,FRAMES),'full16s':(0,FRAMES)}
COMMIT='65aeaf7a76a55248903f2eec2b464752711defd7'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_word(displayed):
    return round(displayed*127/255)*256


def dump(path,data):
    path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def grid_records(captures):
    """Select complete training metadata before any audio path is opened."""
    expected={f'grid-u{t:03}-a{a:03}-d{d:03}-r{r}' for t,a,d in itertools.product(POSITIONS,repeat=3) for r in (1,2,3)}
    with (captures/'recordings.csv').open() as stream:
        rows=[r for r in csv.DictReader(stream) if r['split']=='grid']
    assert len(rows)==2187 and {r['name'] for r in rows}==expected
    for row in rows:
        tune,attack,decay=map(int,(row['tune_displayed'],row['attack_displayed'],row['decay_displayed']))
        repeat=int(row['name'].rsplit('-r',1)[1])
        assert tune in POSITIONS and attack in POSITIONS and decay in POSITIONS and repeat in (1,2,3)
        assert row['name']==f'grid-u{tune:03}-a{attack:03}-d{decay:03}-r{repeat}'
    return rows


def audit(root,out):
    captures=root/'research/reference/909/captures'
    protocol=json.loads((captures/'protocol.json').read_text())
    selected=[r for r in protocol['tests'] if r['split']=='grid']
    names={f'grid-u{t:03}-a{a:03}-d{d:03}-r{r}' for t,a,d in itertools.product(POSITIONS,repeat=3) for r in (1,2,3)}
    assert len(selected)==2187 and {r['name'] for r in selected}==names
    for row in selected:
        assert row['duration']==17 and row['notes']==[dict(start=1,finish=1.01,pitch=36,velocity=100)]
    records={r['name']:r for r in grid_records(captures)}
    assert set(records)==names and all(r['split']=='grid' for r in records.values())
    groups={name+suffix:dict(count=0,hash=hashlib.sha256(),varying={},fixed_checks={}) for name in names for suffix in (':before',':after')}
    with (captures/'settings.tsv').open() as stream:
        for row in csv.DictReader(stream,delimiter='\t'):
            if row['capture'] not in groups:continue
            group=groups[row['capture']];index=int(row['index'])
            assert index==group['count'];group['count']+=1
            if index in (1,2,3):group['varying'][index]=(row['displayed'],row['normalized'])
            else:group['hash'].update(json.dumps([index,row['parameter'],row['displayed'],row['normalized']],separators=(',',':')).encode()+b'\n')
            if index in (0,4,5,49,50,51,194,195,196):group['fixed_checks'][index]=(row['displayed'],row['normalized'])
    baseline=None
    for name,row in records.items():
        before,after=groups[name+':before'],groups[name+':after']
        assert before['count']==after['count']==197 and before['varying']==after['varying']
        h=before['hash'].hexdigest();assert h==after['hash'].hexdigest()
        if baseline is None:baseline=h
        assert h==baseline,'fixed source controls changed'
        t,a,d=map(int,(row['tune_displayed'],row['attack_displayed'],row['decay_displayed']))
        assert (t,a,d) in itertools.product(POSITIONS,repeat=3)
        assert [int(before['varying'][k][0]) for k in (1,3,2)]==[t,a,d]
        checks=before['fixed_checks'];assert checks[0][0]=='220' and checks[4][0]==checks[5][0]=='128'
        assert checks[49][0]=='108' and checks[50][0]==checks[51][0]=='0'
        assert [float(checks[k][1]) for k in (194,195,196)]==[0,1,0]
    histories=[r for r in protocol['tests'] if r['split']=='history']
    assert len(histories)==7
    manifest=dict(scope='729training settings, three fresh takes each; metadata only for held-out/history/support',
        settings=729,takes=2187,posttrigger_frames=FRAMES,posttrigger_seconds=16,scheduled_crop_sample=RATE,
        controls=list(POSITIONS),native_word_map={str(v):native_word(v) for v in POSITIONS},fixed_controls_sha256=baseline,
        metadata_sha256={f:digest(captures/f) for f in ('protocol.json','recordings.csv','settings.tsv')},
        validation_reserved=dict(settings=64,takes=192,audio_read=False),history_support=histories,
        history_acceptance='separate explicit logical-test-voice replay only; no inferred native allocation',support_files='44capture integrity controls, not grid fidelity cases')
    dump(out/'corpus.json',manifest)
    return captures,records,manifest


def spectral(values):
    import numpy as np
    n=len(values);length=1<<(n-1).bit_length();w=np.hanning(n);transformed=np.fft.rfft(values*w,n=length)
    power=np.abs(transformed)**2/(length*np.sum(w*w));power[1:-1]*=2;freq=np.fft.rfftfreq(length,1/RATE)
    return {f'{low}-{high}Hz':float(np.sum(power[(freq>=low)&(freq<high)])) for low,high in ((0,30),(30,150),(150,1000),(1000,24000))}


def pitch(values,peak):
    """Same bounded positive-crossing/peak-period check as the accepted analyzer."""
    import numpy as np
    y=values[:min(len(values),2*RATE)];indices=np.flatnonzero((y[:-1]<=0)&(y[1:]>0))+1
    crossings=indices-1-y[indices-1]/(y[indices]-y[indices-1]);cycles=[];floor=max(1e-9,peak*1e-4)
    for first,last in zip(crossings,crossings[1:]):
        lo,hi=math.ceil(first),math.floor(last)+1
        if hi<=lo:continue
        segment=y[lo:hi];amplitude=float((np.max(segment)-np.min(segment))/2);hz=RATE/(last-first)
        if first<.01*RATE or amplitude<floor or not 10<=hz<=2000:continue
        at=lo+int(np.argmax(segment));position=float(at)
        if 0<at<len(y)-1:
            left,mid,right=map(float,y[at-1:at+2]);curve=left-2*mid+right
            if curve:position+=(left-right)/(2*curve)
        cycles.append((first,last,hz,position))
    result={}
    for name,lo,hi in [('early',.01,.05),('body',.05,.2),('late',.2,.5),('tail',.5,2.)]:
        reliable=[]
        for a,b in zip(cycles,cycles[1:]):
            distance=b[3]-a[3]
            if lo<=(a[0]+a[1])/(2*RATE)<hi and distance>0 and abs((RATE/distance)/a[2]-1)<=.02:reliable.append(a[2])
        result[name]=dict(reliable_cycles=len(reliable),median_hz=float(np.median(reliable)) if len(reliable)>=3 else None)
    return result


def measure(values):
    import numpy as np
    peak=float(np.max(np.abs(values)));energy=values*values;threshold=max(1e-12,peak*1e-6);onsets=np.flatnonzero(np.abs(values)>threshold)
    envelope=np.sqrt(np.mean(energy.reshape(-1,480),axis=1));total=float(np.sum(energy));cumulative=np.cumsum(energy)
    selected=np.flatnonzero((np.arange(len(envelope))*.01>=.02)&(np.arange(len(envelope))*.01<=4)&(envelope>=max(1e-9,peak*1e-4)))
    decay=None
    if len(selected)>=3 and (selected[-1]-selected[0])*.01>=.03:
        x=selected*.01;y=np.log(envelope[selected]);slope,intercept=np.polyfit(x,y,1)
        decay=dict(time_constant_s=float(-1/slope) if slope< -1e-9 else None,log_slope_per_s=float(slope),points=len(selected),window_s=[float(x[0]),float(x[-1])],method='descriptive10msRMSlogfit; no fidelity threshold')
    result=dict(peak_fs=peak,rms_fs=float(np.sqrt(np.mean(energy))),dc_fs=float(np.mean(values)),energy_fs2_s=total/RATE,
        minimum_fs=float(np.min(values)),maximum_fs=float(np.max(values)),full_scale_samples=int(np.count_nonzero(np.abs(values)>=1)),
        onset_sample=int(onsets[0]) if len(onsets) else None,onset_polarity=int(np.sign(values[onsets[0]])) if len(onsets) else None,onset_threshold_fs=threshold,
        pitch=pitch(values,peak),decay_rms_fit=decay,
        energy_duration_s={str(v):float(np.searchsorted(cumulative,v*total)/RATE) if total else None for v in (.5,.9,.99)},
        spectra=dict(first20ms=spectral(values[:960]),body20to200ms=spectral(values[960:9600]),last200ms=spectral(values[-9600:])),
        windows={name:dict(rms_fs=float(np.sqrt(np.mean(energy[lo:hi]))),dc_fs=float(np.mean(values[lo:hi])),peak_fs=float(np.max(np.abs(values[lo:hi])))) for name,(lo,hi) in WINDOWS.items()})
    return result,envelope


def read_capture(captures,name,row,project_gain):
    import numpy as np
    import soundfile as sf
    path=captures/(name+'.wav');assert digest(path)==row['sha256'],name
    data,rate=sf.read(path,dtype='float32',always_2d=True);assert rate==RATE and data.shape==(17*RATE,2)
    assert sf.info(path).subtype=='FLOAT' and np.isfinite(data).all() and np.array_equal(data[:,0],data[:,1])
    assert float(np.max(np.abs(data[:RATE])))<1e-7,'nonquiet scheduled preroll'
    project=captures/(name+'.RPP');gain=project_gain(project.read_text());assert gain==4
    return data[RATE:,0].astype(np.float64),dict(wav_sha256=row['sha256'],project_sha256=digest(project),reference_gain=gain,captured_onset_sample=int(row['onset_sample'])-RATE)


def references(root,out,project_gain):
    import numpy as np
    captures,records,manifest=audit(root,out);envelopes=[];names=[]
    with (out/'reference-metrics.jsonl').open('w') as stream:
        for index,(name,row) in enumerate(sorted(records.items())):
            values,source=read_capture(captures,name,row,project_gain);metrics,env=measure(values*4)
            record=dict(name=name,tune=int(row['tune_displayed']),attack=int(row['attack_displayed']),decay=int(row['decay_displayed']),source=source,reference=metrics,
                as_recorded=dict(peak_fs=metrics['peak_fs']/4,rms_fs=metrics['rms_fs']/4,dc_fs=metrics['dc_fs']/4,energy_fs2_s=metrics['energy_fs2_s']/16),envelope_row=index)
            stream.write(json.dumps(record,allow_nan=False)+'\n');envelopes.append(env.astype(np.float32));names.append(name)
            if (index+1)%81==0:print('reference metrics',index+1,'/2187',flush=True)
    np.savez_compressed(out/'reference-envelopes.npz',names=np.asarray(names),rms_10ms=np.asarray(envelopes))
    dump(out/'reference-status.json',dict(status='passed',takes=2187,frames_per_take=FRAMES,metadata=manifest['metadata_sha256'],metrics_sha256=digest(out/'reference-metrics.jsonl'),envelopes_sha256=digest(out/'reference-envelopes.npz'),held_out_audio_read=False,history_audio_read=False))


def residual(actual,expected):
    import numpy as np
    delta=actual-expected;aa=float(np.dot(actual,actual));ee=float(np.dot(expected,expected))
    return dict(rms_fs=float(np.sqrt(np.mean(delta*delta))),maximum_fs=float(np.max(np.abs(delta))),dc_fs=float(np.mean(delta)),
        correlation=float(np.dot(actual,expected)/math.sqrt(aa*ee)) if aa>0 and ee>0 else None,
        normalized_rms=float(math.sqrt(np.dot(delta,delta)/ee)) if ee>0 else None)


def repeat_pairs(takes):
    import numpy as np
    pairs=[]
    for first,second in itertools.combinations(range(3),2):
        delta=(takes[first]-takes[second])*4;where=np.flatnonzero(delta)
        pairs.append(dict(takes=[first+1,second+1],differing_samples=len(where),first_sample=int(where[0]) if len(where) else None,last_sample=int(where[-1]) if len(where) else None,
            maximum_difference_fs=float(np.max(np.abs(delta))),full16s_rms_difference_fs=float(np.sqrt(np.mean(delta*delta))),first150ms_rms_difference_fs=float(np.sqrt(np.mean(delta[:7200]**2))),late2to16s_rms_difference_fs=float(np.sqrt(np.mean(delta[96000:]**2)))))
    return pairs


def repeat_summary(cases):
    pairs=[p for r in cases for p in r['pairs']];last=[p['last_sample'] for p in pairs if p['last_sample'] is not None]
    return dict(settings=len(cases),pairs=len(pairs),sample_identical_settings=sum(all(p['differing_samples']==0 for p in r['pairs']) for r in cases),
        maximum_last_differing_sample=max(last) if last else None,maximum_pair_difference_fs=max(p['maximum_difference_fs'] for p in pairs),
        maximum_pair_full16s_rms_fs=max(p['full16s_rms_difference_fs'] for p in pairs),scope='sample-exact repetitions, no noise phase inference or collapsed takes')


def repeats(root,out,project_gain):
    captures,records,manifest=audit(root,out);cases=[]
    for tune,attack,decay in itertools.product(POSITIONS,repeat=3):
        takes=[read_capture(captures,f'grid-u{tune:03}-a{attack:03}-d{decay:03}-r{r}',records[f'grid-u{tune:03}-a{attack:03}-d{decay:03}-r{r}'],project_gain)[0] for r in (1,2,3)]
        cases.append(dict(tune=tune,attack=attack,decay=decay,pairs=repeat_pairs(takes)))
    dump(out/'repeat-variation.json',dict(status='complete',summary=repeat_summary(cases),cases=cases,reference_gain=4,held_out_audio_read=False,alignment_samples=0,metadata=manifest['metadata_sha256']))


def mean_optional(values):
    finite=[float(v) for v in values if v is not None and math.isfinite(v)]
    return statistics.mean(finite) if finite else None


def compare(root,out,project_gain):
    import numpy as np
    captures,records,manifest=audit(root,out)
    metrics={r['name']:r for r in map(json.loads,(out/'reference-metrics.jsonl').read_text().splitlines())};assert set(metrics)==set(records)
    reports={backend:json.loads((out/backend/'report.json').read_text()) for backend in ('coldfire','sharc')}
    assert all(r['status']=='passed' and r['commit']==COMMIT and r['frames']==FRAMES and len(r['cases'])==81 for r in reports.values())
    by_backend={b:{(r['tune_displayed'],r['decay_displayed']):r for r in report['cases']} for b,report in reports.items()}
    repeat_cases=[]
    summaries=[];surfaces={b:{control:{str(v):[] for v in POSITIONS} for control in ('tune','attack','decay')} for b in reports};model_metrics={};peer=[]
    with (out/'comparisons.jsonl').open('w') as stream:
        for tune,decay in itertools.product(POSITIONS,repeat=2):
            actual={}
            for backend in reports:
                artifact=by_backend[backend][tune,decay];path=out/backend/artifact['path'];assert digest(path)==artifact['sha256']
                actual[backend]=np.fromfile(path,dtype='<f4').astype(np.float64);assert len(actual[backend])==FRAMES and np.isfinite(actual[backend]).all()
                measured,_=measure(actual[backend]);model_metrics[f'{backend}:u{tune}:d{decay}']=measured
            difference=float(np.max(np.abs(actual['coldfire']-actual['sharc'])));assert difference<=1e-5,(tune,decay,difference);peer.append(difference)
            for attack in POSITIONS:
                rows=[];fresh_takes=[]
                for repeat in (1,2,3):
                    name=f'grid-u{tune:03}-a{attack:03}-d{decay:03}-r{repeat}';raw,source=read_capture(captures,name,records[name],project_gain);expected=raw*4;fresh_takes.append(raw)
                    record=dict(name=name,tune=tune,attack=attack,decay=decay,repeat=repeat,source=source,reference_metrics_row=name,models={})
                    for backend in actual:
                        windows={window:residual(actual[backend][lo:hi],expected[lo:hi]) for window,(lo,hi) in WINDOWS.items()}
                        record['models'][backend]=dict(artifact_key=f'u{tune}:d{decay}',actual_attack_raw=16384 if backend=='sharc' else None,attack_implemented=False,windows=windows,as_recorded_full16s=residual(actual[backend],raw))
                        full=windows['full16s']['rms_fs']
                        for control,value in [('tune',tune),('attack',attack),('decay',decay)]:surfaces[backend][control][str(value)].append(full)
                    stream.write(json.dumps(record,allow_nan=False)+'\n');rows.append(record)
                repeat_cases.append(dict(tune=tune,attack=attack,decay=decay,pairs=repeat_pairs(fresh_takes)))
                summaries.append(dict(tune=tune,attack=attack,decay=decay,
                    reference_peak_mean_fs=statistics.mean(metrics[r['name']]['reference']['peak_fs'] for r in rows),
                    reference_first50ms_energy_mean=statistics.mean(metrics[r['name']]['reference']['windows']['first50ms']['rms_fs']**2*.05 for r in rows),
                    reference_body_hz_mean=mean_optional(metrics[r['name']]['reference']['pitch']['body']['median_hz'] for r in rows),
                    reference_decay_tau_mean_s=mean_optional((metrics[r['name']]['reference']['decay_rms_fit'] or {}).get('time_constant_s') for r in rows),
                    reference_t99_mean_s=mean_optional(metrics[r['name']]['reference']['energy_duration_s']['0.99'] for r in rows),
                    models={b:{window:statistics.mean(r['models'][b]['windows'][window]['rms_fs'] for r in rows) for window in WINDOWS} for b in actual}))
            print('compared Tune/Decay',tune,decay,flush=True)
    trends={b:{control:{v:dict(mean_rms_fs=statistics.mean(values),median_rms_fs=statistics.median(values),worst_rms_fs=max(values)) for v,values in points.items()} for control,points in controls.items()} for b,controls in surfaces.items()}
    dump(out/'repeat-variation.json',dict(status='complete',summary=repeat_summary(repeat_cases),cases=repeat_cases,reference_gain=4,held_out_audio_read=False,alignment_samples=0))
    attacks=[]
    indexed={(r['tune'],r['attack'],r['decay']):r for r in summaries}
    for tune,decay in itertools.product(POSITIONS,repeat=2):
        low,high=indexed[tune,0,decay],indexed[tune,255,decay]
        attacks.append(dict(tune=tune,decay=decay,reference_peak_change_fs=high['reference_peak_mean_fs']-low['reference_peak_mean_fs'],reference_first50ms_energy_change=high['reference_first50ms_energy_mean']-low['reference_first50ms_energy_mean'],actual_audio_change_fs=0,actual_implemented=False))
    report=dict(status='diagnostic_complete',fidelity_status='unqualified',accepted_commit=COMMIT,settings=729,takes=2187,actual_unique_renders_per_backend=81,
        sample_rate=RATE,posttrigger_frames=FRAMES,posttrigger_seconds=16,scheduled_preroll_excluded_samples=RATE,alignment_samples=0,normalization=False,fitted_gain=False,reference_gain=4,
        raw_gain_reason='audited reference project track.25/master1; as-recorded errors retained',held_out_audio_read=False,
        attack_reuse='accepted909doesnotimplementATTK;81actualTune/Decayrenders transparently cover9referenceATTACKpositions; actualinvariance proof separate',
        backend_reports={b:dict(path=str((out/b/'report.json').relative_to(root)),sha256=digest(out/b/'report.json')) for b in reports},
        metadata=manifest,model_metrics=model_metrics,control_surface_trends=trends,cases=summaries,
        ranked_gaps={b:{window:sorted(summaries,key=lambda r:r['models'][b][window],reverse=True)[:25] for window in ('full16s','first50ms','tail2to16s')} for b in reports},
        attack_surface_gaps=attacks,repeat_variation_summary=repeat_summary(repeat_cases),repeat_variation_sha256=digest(out/'repeat-variation.json'),
        metric_scope='rawcomponentbody before native AMP/filter/mixer; onset notaligned; pitch reliable only with >=3crossing/peak-checked cycles; descriptive RMSdecay fits are not fidelitylimits',
        producer=dict(comparison_driver_sha256=digest(Path(__file__)),reference_status_sha256=digest(out/'reference-status.json'),accepted_freeze_sha256=digest(out/'frozen.json') if (out/'frozen.json').exists() else digest(root/'out/reference/808-grid/frozen.json')),
        maximum_cpu_peer_error_fs=max(peer),peer_limit_fs=1e-5,
        missing=['ATTACKpulse/noise','full circuit loading/transistor/potcalibration','native modulation/allocatorhistory fidelity','held-out acceptance','physical qualification'])
    dump(out/'report.json',report)


def model_oracle(decay_raw,tune_raw,frames):
    """Independent model; only its provably silent tail is evaluated analytically."""
    import numpy as np
    from x0x import body909,vca909
    expected=np.zeros(frames,dtype=np.float64);state=body909.INITIAL_STATE;stop=0
    for start in range(0,frames,32):
        values,state=body909.continue_reference(state,decay_raw,tune_raw,32)
        expected[start:start+32]=values;stop=start+32
        if state[2]==0 and state[3]<=vca909.BASE_V*vca909.STATE_SCALE:break
    return expected,dict(evaluated_samples=stop,analytic_zero_samples=frames-stop,c8_encoded=state[3],remaining=state[2],
        reason='constantcontrols; passive C8 below baseknee aftertriggeroff staysinaudible; actualCPUexecutes everyrequested sample')


def build_coldfire(folder):
    """Mirror the existing accepted909 component wrapper and assembly boundary."""
    from x0x import cpu
    source=cpu.ROOT/'targets/coldfire/body909.s'
    for caller in ('digitakt','digitone'):
        if 'x0x_909_attack' in (cpu.ROOT/f'machines/{caller}/machine.c').read_text():
            raise ValueError('909 render chain now contains Attack; update actualstage chain and remove ignoredATTACK reuse before comparing')
    wrapper=(cpu.ROOT/'targets/coldfire/selector.s').read_text().split('    .globl x0x_selector\n')[0]
    first=wrapper.index('    lea -12(%sp), %sp');last=wrapper.index('    move.l %d0, 32(%a0)')
    wrapper=wrapper[:first]+'''    lea -20(%sp), %sp
    move.l 24(%sp), %d0
    move.l %d0, 0(%sp)
    move.l 28(%sp), %d0
    move.l %d0, 4(%sp)
    move.l 32(%sp), %d0
    move.l %d0, 8(%sp)
    move.l 36(%sp), %d0
    move.l %d0, 12(%sp)
    move.l 40(%sp), %d0
    move.l %d0, 16(%sp)
    bsr x0x_909_body
    lea 20(%sp), %sp
    movea.l 24(%sp), %a0
'''+wrapper[last:]
    folder.mkdir(parents=True,exist_ok=True);probe=folder/'probe.s';probe.write_text(wrapper+'\n'+source.read_text())
    return cpu.build_coldfire(folder,probe)[0]


def render_coldfire(root,out,frozen,frames):
    import array
    import struct
    import time
    import numpy as np
    from x0x import cpu
    from x0x.coldfire_body909 import TuneRunner
    from reference_grid_common import runner_class
    folder=out/'coldfire';folder.mkdir(parents=True,exist_ok=True);image=build_coldfire(folder/'kernel')
    Fast=runner_class(TuneRunner,state_words=4);preflight=[]
    for tune,decay in ((0,0),(32512,0),(0,32512),(32512,32512),(16384,16384),(4096,28416),(24320,12288)):
        guarded,fast=TuneRunner(image),Fast(image)
        for block in range(128):
            assert guarded.render(start=int(block==0),decay_raw=decay,tune_raw=tune)==fast.render(start=int(block==0),decay_raw=decay,tune_raw=tune)
            assert bytes(guarded.uc.mem_read(guarded.STATES-4,guarded.extent))==bytes(fast.uc.mem_read(fast.STATES-4,fast.extent))
            assert bytes(guarded.uc.mem_read(guarded.SNAPSHOT-4,44))==bytes(fast.uc.mem_read(fast.SNAPSHOT-4,44))
        preflight.append(dict(tune_raw=tune,decay_raw=decay,frames=4096,output_state_context_byte_identical=True))
    dump(folder/'fastpath-proof.json',dict(status='passed',cases=preflight,image_sha256=hashlib.sha256(image).hexdigest(),
        scope='only diagnostic globalcount/storeloggers omitted; originalrender/post-callguards unchanged',helper_sha256=digest(Path(__file__).parent/'reference_grid_common.py')))
    cases=[];begin=time.monotonic()
    for tune,decay in itertools.product(POSITIONS,repeat=2):
        started=time.monotonic();tr,dr=native_word(tune),native_word(decay);machine=Fast(image);values=array.array('f')
        for start in range(0,frames,32):values.extend(v/2**31 for v in machine.render(start=int(start==0),decay_raw=dr,tune_raw=tr))
        assert values.itemsize==4
        actual=np.asarray(values,dtype=np.float32);assert np.isfinite(actual).all();expected,oracle=model_oracle(dr,tr,frames)
        error=float(np.max(np.abs(actual-expected)));assert error<=1e-5,(tune,decay,error)
        path=folder/f'grid-u{tune:03}-d{decay:03}.f32';actual.astype('<f4').tofile(path)
        cases.append(dict(tune_displayed=tune,decay_displayed=decay,tune_raw=tr,decay_raw=dr,path=path.name,sha256=digest(path),
            frames=frames,actual_executed_cpu_samples=frames,oracle_maximum_error_fs=error,numeric_limit_fs=1e-5,numeric_status='passed',oracle_scope=oracle,
            final_state_words=struct.unpack('>4I',machine.uc.mem_read(machine.STATES,16)),wall_s=time.monotonic()-started))
        dump(folder/'progress.json',dict(completed=len(cases),total=81,cases=cases));print('ColdFire render',len(cases),'/81',flush=True)
    report=dict(status='passed',commit=frozen['commit'],frozen_source_root=frozen['frozen_source_root'],frames=frames,sample_rate=RATE,posttrigger_window_s=frames/RATE,cases=cases,
        image_sha256=hashlib.sha256(image).hexdigest(),source_sha256=digest(cpu.ROOT/'targets/coldfire/body909.s'),
        caller_source_sha256={str(p.relative_to(cpu.ROOT)):digest(p) for p in (cpu.ROOT/'machines/digitakt/machine.c',cpu.ROOT/'machines/digitone/machine.c')},
        fastpath_proof_sha256=digest(folder/'fastpath-proof.json'),driver_sha256=digest(Path(__file__)),wall_s=time.monotonic()-begin,
        attack_reuse='acceptedbody has no ATTACKargument;81Tune/Decayrenders reused over9validreferenceATTACKpositions; no Attackfunctionality claimed',
        scope='actualColdFire instructions, unchanged per-call postguards; no per-instruction writewatching/nativeOS/physicalclaim')
    dump(folder/'report.json',report)


def render_sharc(root,out,frozen,frames):
    import time
    import numpy as np
    from reference_grid_sharc import prepare,FastRunner
    support=out/'native-support';prepared=prepare(frozen,support);runner=FastRunner(support)
    folder=out/'sharc';folder.mkdir(parents=True,exist_ok=True);cases=[];invariance=[];begin=time.monotonic()
    for tune,decay in ((0,0),(16384,16384),(32512,32512)):
        baseline=runner.render(909,tune,decay,4096,attack_raw=16384)
        for attack in POSITIONS:
            result=runner.render(909,tune,decay,4096,attack_raw=native_word(attack));assert result==baseline,(tune,decay,attack)
            invariance.append(dict(tune_raw=tune,decay_raw=decay,actual_attack_raw=native_word(attack),frames=4096,byte_identical=True))
    dump(folder/'attack-invariance.json',dict(status='passed',cases=invariance,scope='actualvalidATTACKwords affect validation only; functionality notimplemented'))
    for tune,decay in itertools.product(POSITIONS,repeat=2):
        started=time.monotonic();tr,dr=native_word(tune),native_word(decay);blob=runner.render(909,tr,dr,frames,attack_raw=16384);actual=np.frombuffer(blob,dtype='<f4')
        assert len(actual)==frames and np.isfinite(actual).all();expected,oracle=model_oracle(dr,tr,frames);error=float(np.max(np.abs(actual-expected)));assert error<=1e-5,(tune,decay,error)
        path=folder/f'grid-u{tune:03}-d{decay:03}.f32';path.write_bytes(blob)
        cases.append(dict(tune_displayed=tune,decay_displayed=decay,tune_raw=tr,decay_raw=dr,actual_attack_raw=16384,path=path.name,sha256=digest(path),frames=frames,
            actual_executed_cpu_samples=frames,oracle_maximum_error_fs=error,numeric_limit_fs=1e-5,numeric_status='passed',oracle_scope=oracle,wall_s=time.monotonic()-started))
        dump(folder/'progress.json',dict(completed=len(cases),total=81,cases=cases));print('SHARC render',len(cases),'/81',flush=True)
    dump(folder/'report.json',dict(status='passed',commit=frozen['commit'],frozen_source_root=frozen['frozen_source_root'],frames=frames,sample_rate=RATE,posttrigger_window_s=frames/RATE,cases=cases,
        source_sha256=runner.manifest['source_sha256'],image_sha256=hashlib.sha256(runner.code).hexdigest(),nativecore=prepared,runtime=runner.runtime,
        attack_invariance_proof_sha256=digest(folder/'attack-invariance.json'),driver_sha256=digest(Path(__file__)),wall_s=time.monotonic()-begin,
        actual_native_calls=runner.calls,attack_reuse='81Tune/Decayrenders atATTK16384 reused over9referenceATTACKpositions; actualvalidword invariance separate',
        scope='actualSHARCNativeCore instructions, independently guardedfixtureverified; no installedOS/physicalclaim'))


def render_history(root,out,frozen,backend,project_gain):
    """Explicit single test voice; START clearing is not a native ownership claim."""
    import struct
    from fractions import Fraction
    import numpy as np
    import soundfile as sf
    captures=root/'research/reference/909/captures';protocol=json.loads((captures/'protocol.json').read_text())
    tests=[r for r in protocol['tests'] if r['split']=='history'];assert len(tests)==7;names={r['name'] for r in tests}
    with (captures/'recordings.csv').open() as stream:records={r['name']:r for r in csv.DictReader(stream) if r['name'] in names}
    settings={n+s:{} for n in names for s in (':before',':after')}
    with (captures/'settings.tsv').open() as stream:
        for row in csv.DictReader(stream,delimiter='\t'):
            if row['capture'] in settings:settings[row['capture']][int(row['index'])]=(row['displayed'],row['normalized'])
    folder=out/'history'/backend;folder.mkdir(parents=True,exist_ok=True)
    if backend=='coldfire':
        from x0x.coldfire_body909 import TuneRunner
        from reference_grid_common import runner_class
        Fast=runner_class(TuneRunner,state_words=4);code=build_coldfire(folder/'kernel')
    else:
        from reference_grid_sharc import prepare,FastRunner
        from x0x import sharc_selector as selector
        support=out/'native-support';prepare(frozen,support);code=FastRunner(support).code
    results=[]
    summary=lambda a:dict(peak_fs=float(np.max(np.abs(a))),rms_fs=float(np.sqrt(np.mean(a*a))),dc_fs=float(np.mean(a)),energy_fs2_s=float(np.sum(a*a)/RATE))
    for test in tests:
        name=test['name'];row=records[name];before,after=settings[name+':before'],settings[name+':after'];assert before==after and set(before)==set(range(197))
        tune,decay,attack=[int(before[k][0]) for k in (1,2,3)];assert (tune,decay,attack)==tuple(int(row[k]) for k in ('tune_displayed','decay_displayed','attack_displayed'))
        timeline=[]
        for note in test['notes']:
            assert note['pitch']==36 and note['velocity']==100 and Fraction(str(note['finish']))-Fraction(str(note['start']))==Fraction(1,100)
            sample=(Fraction(str(note['start']))-1)*RATE;assert sample.denominator==1;sample=int(sample);block=(sample+31)//32
            timeline.append(dict(scheduled_sample=sample,delivered_start_sample=block*32,quantization_delay_samples=block*32-sample,start_block=block))
        starts={r['start_block'] for r in timeline};assert len(starts)==len(timeline);frames=int((test['duration']-1)*RATE);data=bytearray()
        if backend=='coldfire':machine=Fast(code)
        else:
            machine=FastRunner(support);frame=selector.case('history',model=32512,pitch=36<<8);frame['params'][:3]=[native_word(tune),native_word(decay),native_word(attack)]
        for block in range((frames+31)//32):
            start=int(block in starts)
            if backend=='coldfire':data.extend(struct.pack('<32f',*[v/2**31 for v in machine.render(start=start,decay_raw=native_word(decay),tune_raw=native_word(tune))]))
            else:frame['flags']=start;data.extend(struct.pack('<32I',*machine.call_raw(frame)))
        path=folder/(name+'.f32');path.write_bytes(data[:frames*4]);actual=np.frombuffer(data[:frames*4],dtype='<f4').astype(np.float64)
        wav=captures/(name+'.wav');assert digest(wav)==row['sha256'];reference,rate=sf.read(wav,dtype='float32',always_2d=True)
        assert rate==RATE and reference.shape==(test['duration']*RATE,2) and np.array_equal(reference[:,0],reference[:,1]) and np.isfinite(reference).all() and np.isfinite(actual).all()
        assert sf.info(wav).subtype=='FLOAT';gain=project_gain((captures/(name+'.RPP')).read_text());assert gain==4
        expected=reference[RATE:,0].astype(np.float64)*gain
        results.append(dict(name=name,frames=frames,duration_s=frames/RATE,actual_executed_cpu_samples=frames,scheduled_notes=test['notes'],start_timeline=timeline,
            path=path.name,sha256=digest(path),reference_sha256=row['sha256'],reference_project_sha256=digest(captures/(name+'.RPP')),
            tune_raw=native_word(tune),decay_raw=native_word(decay),actual_attack_raw=native_word(attack) if backend=='sharc' else None,attack_implemented=False,
            actual=summary(actual),reference=summary(expected),residual=summary(actual-expected)))
    dump(folder/'report.json',dict(status='diagnostic_complete',accepted_commit=frozen['commit'],backend=backend,cases=results,image_sha256=hashlib.sha256(code).hexdigest(),
        scope='one explicitlyowned testvoice; everySTARTuses acceptedclearpolicy; notnativeallocation/analogretention acceptance',
        history_acceptance='reserved',noteoffs='10ms sourceevents recorded; standalonebody hasno GATE/stockAMP path',alignment_samples=0,fitted_gain=False,reference_gain=4,held_out_audio_read=False))
    other=out/'history'/('sharc' if backend=='coldfire' else 'coldfire')/'report.json'
    if other.is_file():
        reports={b:json.loads((out/'history'/b/'report.json').read_text()) for b in ('coldfire','sharc')}
        assert all(r['accepted_commit']==frozen['commit'] for r in reports.values());rows=[]
        for a,b in zip(reports['coldfire']['cases'],reports['sharc']['cases']):
            assert a['name']==b['name'] and a['frames']==b['frames'] and a['start_timeline']==b['start_timeline']
            left=np.fromfile(out/'history/coldfire'/a['path'],dtype='<f4');right=np.fromfile(out/'history/sharc'/b['path'],dtype='<f4');error=float(np.max(np.abs(left-right)));assert error<=1e-5
            rows.append(dict(name=a['name'],frames=a['frames'],duration_s=a['duration_s'],timeline=a['start_timeline'],cpu_peer_error_fs=error,coldfire_residual=a['residual'],sharc_residual=b['residual']))
        dump(out/'history/report.json',dict(status='component_diagnostic_complete',cases=rows,scope='explicit singlecomponentvoice, notnative/analoghistoryacceptance',history_acceptance='reserved',alignment_samples=0,held_out_audio_read=False,numeric_peer_limit_fs=1e-5))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--stage',choices=('render-coldfire','render-sharc','history-coldfire','history-sharc','references','compare','repeats'),required=True)
    parser.add_argument('--revision',default=COMMIT)
    parser.add_argument('--frozen',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--frames',type=int,default=FRAMES,help='render-only smoke length; comparisons require the full16seconds')
    parser.add_argument('--frozen-child',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args();root=args.root.resolve();out=args.output.resolve() if args.output else root/'out/reference/909-grid';out.mkdir(parents=True,exist_ok=True)
    from reference_grid_common import prepare_frozen,frozen_invocation
    revision=subprocess.check_output(['git','rev-parse',args.revision],cwd=root,text=True).strip()
    if revision!=COMMIT:
        raise ValueError('909grid is bound to accepted65aeaf7; review the actual render chain and ATTACKcoverage before adopting another baseline')
    frozen_path=args.frozen or root/'out/reference/808-grid'/('accepted-'+revision[:7])
    frozen=prepare_frozen(frozen_path,revision);dump(out/'frozen.json',frozen)
    if not args.frozen_child:
        forwarded=['--stage',args.stage,'--root',str(root),'--revision',frozen['commit'],'--frozen',str(frozen_path),'--output',str(out),'--frames',str(args.frames),'--frozen-child']
        return frozen_invocation(Path(__file__),forwarded,frozen_path)
    from x0x import reference909_compare as accepted,cpu
    assert cpu.ROOT==Path(frozen['frozen_source_root'])
    if args.stage.startswith('render-'):
        if args.frames<=0 or args.frames%32:raise ValueError('render length must be positive and divisible by32')
        (render_coldfire if args.stage=='render-coldfire' else render_sharc)(root,out,frozen,args.frames)
    elif args.stage.startswith('history-'):
        if args.frames!=FRAMES:raise ValueError('history retains its full protocol duration; no smoke truncation')
        render_history(root,out,frozen,args.stage.split('-')[1],accepted.project_gain)
    else:
        if args.frames!=FRAMES:raise ValueError('reference comparisons retain the complete16second window')
        {'references':references,'compare':compare,'repeats':repeats}[args.stage](root,out,accepted.project_gain)
    return 0


if __name__=='__main__':raise SystemExit(main())
