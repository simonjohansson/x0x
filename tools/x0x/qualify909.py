"""Render every frozen test setting through actual DSP ASM, preserving raw errors."""
import argparse
import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import time
import sys
import numpy as np
import soundfile as sf
from . import cpu,field909,fit909,sharc_field808 as sharc,coldfire_field909 as coldfire
from .firmware import load_json

OUT=cpu.ROOT/'out/909-model/qualification'


def input_hashes():
    return cpu.source_hashes()


def load_report(target):
    report = load_json(OUT/target/'report.json')
    if (report['status'] != 'passed' or report['target'] != target
            or report['model_sha256'] != field909.MODEL_SHA
            or (report['test_settings'], report['test_events']) != (721, 724)):
        raise ValueError('Both complete matching ASM qualifications are required')
    if report.get('inputs_sha256') != input_hashes():
        raise ValueError('Historical qualification: source inputs differ; rerun qualification')
    for path_key, hash_key in [('rendered_wav', 'rendered_wav_sha256'),
                               ('corners_png', 'corners_png_sha256')]:
        if hashlib.sha256(Path(report[path_key]).read_bytes()).hexdigest() != report[hash_key]:
            raise ValueError('Qualification artifact hash mismatch: ' + path_key)
    return report


def measure(predicted,reference):
    if not (np.isfinite(predicted).all() and np.isfinite(reference).all()):
        raise ValueError('Non-finite qualification audio')
    error=predicted-reference;energy=np.cumsum(reference*reference);penergy=np.cumsum(predicted*predicted)
    return dict(l2=float(np.linalg.norm(error)/np.linalg.norm(reference)),after10ms_l2=float(np.linalg.norm(error[480:])/np.linalg.norm(reference[480:])),max_fs=float(abs(error).max()),level_db=float(20*np.log10(np.linalg.norm(predicted)/np.linalg.norm(reference))),peak_db=float(20*np.log10(max(abs(predicted))/max(abs(reference)))),t99_delta_ms=float((np.searchsorted(penergy,.99*penergy[-1])-np.searchsorted(energy,.99*energy[-1]))/48))


def port_error(actual, expected):
    if not (np.isfinite(actual).all() and np.isfinite(expected).all()):
        raise ValueError('Non-finite port audio')
    error = float(abs(actual-expected).max())
    if error >= 1e-5:
        raise AssertionError(('Port error', error))
    return error


def plots(folder,corners):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(8,3,figsize=(15,20),constrained_layout=True)
    for i,(settings,reference,prediction) in enumerate(corners):
        for j,(limit,step) in enumerate(((96000,8),(960,1),(1152,1))):
            ax=axes[i,j];t=np.arange(0,limit,step)/48
            if j<2:
                ax.plot(t,reference[:limit:step],color='#202b38',linewidth=.8,label='VST recording')
                ax.plot(t,prediction[:limit:step],color='#008b91',linewidth=.8,alpha=.85,label='Executed ASM / 4')
            else:ax.plot(t,(prediction-reference)[:limit:step],color='#b55d15',linewidth=.8,label='Prediction minus VST')
            ax.grid(alpha=.2);ax.set_xlabel('Milliseconds after MIDI trigger')
            if j==0:ax.set_ylabel(f'Tune {settings[0]}, Attack {settings[1]}, Decay {settings[2]}\nSource full scale')
            if i==0:ax.legend(fontsize=8)
    fig.suptitle('Eight corners: full kick, first 20 ms, and transient error. No alignment or fitted gain.')
    fig.savefig(folder/'corners.png',dpi=140);plt.close(fig)


def qualify(target):
    destination=OUT/target;destination.mkdir(parents=True,exist_ok=True)
    runs=destination/'runs';runs.mkdir(exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='run-',dir=runs))
    inputs=input_hashes()
    provenance = dict(project_revision=cpu.revision(cpu.ROOT),
                      project_dirty=cpu.command(['git', 'status', '--porcelain'], cwd=cpu.ROOT),
                      dependencies={name: cpu.clean_revision(cpu.ROOT/'vendor'/name)
                                    for name in ('digiemu', 'digikit', 'elekloader')})
    model=field909.load();events=fit909.load_events();raw=fit909.raw_audio()
    interaction={tuple(e[k+'_cc'] for k in ('tune','attack','decay')):e for e in events if e['split']=='interaction'}
    corner_keys=[(t,a,d) for t in (0,127) for a in (0,127) for d in (0,127)]
    groups={}
    for e in events:
        if e['partition']=='test':groups.setdefault(tuple(e[k+'_cc'] for k in ('tune','attack','decay')),[]).append(e)
    cases=[(key,[interaction[key]],'corner') for key in corner_keys]+[(key,value,'test') for key,value in groups.items()]
    cases += [((1/256,255/256,32511/256),[],'fraction'),((12345/256,23001/256,17001/256),[],'fraction')]
    if target=='sharc':
        receipt,artifact=sharc.build(folder/'build');runner=sharc.Runner(receipt,artifact)
    else:
        receipt,image=coldfire.build(folder/'build');runner=coldfire.Runner(image,guarded=False);oracle=coldfire.Reference(folder/'build')
    if target == 'sharc':
        provenance.update(native_library_sha256=hashlib.sha256(Path(runner.native.DEFAULT_LIB).read_bytes()).hexdigest(),
                          native_info=runner.core.info(),
                          tools={name: cpu.tool_identity(cpu.selache()/'target/release'/name) for name in ('selas', 'seld')})
    else:
        import unicorn
        library=Path(unicorn.__file__).parent/'lib'/('libunicorn.2.dylib' if sys.platform=='darwin' else 'libunicorn.so.2')
        provenance.update(native_library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),
                          unicorn_version=unicorn.__version__,
                          integer_reference_sha256=hashlib.sha256((cpu.ROOT/'tools/x0x/coldfire_field909_ref.c').read_bytes()).hexdigest(),
                          tools={name: cpu.tool_identity(os.environ.get('ELEKLOADER_CROSS', 'm68k-elf-')+name)
                                 for name in ('as', 'ld', 'objcopy')})
    import scipy
    provenance['environment'] = dict(python=sys.version, numpy=np.__version__, scipy=scipy.__version__, soundfile=sf.__version__)
    provenance['tools']['python'] = cpu.tool_identity(sys.executable)
    provenance['tools']['cc'] = cpu.tool_identity(os.environ.get('CC', 'clang'))
    rows=[];corners=[];started=time.monotonic();maximum_port=0.;test_count=0
    wavpath=folder/'rendered-native.wav'
    with sf.SoundFile(wavpath,'w',samplerate=48000,channels=1,subtype='FLOAT' if target=='sharc' else 'PCM_32') as wave, (folder/'rows.jsonl').open('w') as log:
        for number,(settings,source_events,partition) in enumerate(cases):
            controls=tuple(round(x*256) for x in settings)
            if target=='sharc':
                runner.core.poke(receipt['state_base'],bytes(sharc.STATE_BYTES),4)
                y=np.concatenate([runner.call(controls[0],controls[2],b==0,model=32512,attack=controls[1])[0] for b in range(3000)])
                wave.write(y.astype('float32'))
            else:
                runner.uc.mem_write(runner.STATES,bytes(1408));oracle.state=(ctypes.c_int32*352)();blocks=[]
                for b in range(3000):
                    actual=runner.call(*controls,start=b==0);expected=oracle.call(*controls,start=b==0)
                    if actual!=expected:raise AssertionError(('Integer waveform disagreement',settings,b))
                    if bytes(runner.uc.mem_read(runner.STATES,1408))!=struct.pack('>352i',*oracle.state):raise AssertionError(('Integer state disagreement',settings,b))
                    blocks.extend(actual)
                integers=np.asarray(blocks,dtype='int32');wave.write(integers);y=integers.astype(float)/2**31
            expected=4*field909.render(model,*controls);port=port_error(y,expected);maximum_port=max(maximum_port,port)
            runner.check_tables()
            for e in source_events:
                offset=e['onset_sample'];reference=np.asarray(raw[offset:offset+96000,0],dtype=float)
                row=dict(index=e['index'],settings=settings,partition=partition,render_offset=number*96000,port_max_dsp_fs=port,**measure(y/4,reference))
                rows.append(row);log.write(json.dumps(row,allow_nan=False)+'\n')
                if partition=='test':test_count+=1
                if partition=='corner':corners.append((settings,reference,y/4))
            if (number+1)%25==0:
                log.flush();print(target,'renders',number+1,'of',len(cases),'test events',test_count,'max port DSP FS',maximum_port,'seconds',round(time.monotonic()-started,1),flush=True)
    plots(folder,corners)
    selected=[r for r in rows if r['partition']=='test']
    report=dict(status='passed',scope='Isolated actual-instruction ASM renders; no physical-device or perceptual acceptance',target=target,model_sha256=field909.MODEL_SHA,capture_sha256='ad05ef41060e4477dd5bb8fddcfe9de4c106576f448800b29f0693b86fc667ba',build=receipt,renders=len(cases),test_settings=len(groups),test_events=len(selected),maximum_port_dsp_fs=maximum_port,gain_to_capture=.25,alignment_samples=0,rendered_wav=str(wavpath),rendered_wav_sha256=hashlib.sha256(wavpath.read_bytes()).hexdigest(),rows=rows)
    for metric in ('l2','after10ms_l2','max_fs','level_db','peak_db','t99_delta_ms'):
        report[metric]=dict(zip(('min','median','p95','max'),map(float,np.quantile([r[metric] for r in selected],[0,.5,.95,1]))))
    if input_hashes() != inputs:
        raise ValueError('Source inputs changed during qualification')
    report.update(provenance=provenance, inputs_sha256=inputs, corners_png=str(folder/'corners.png'),
                  corners_png_sha256=hashlib.sha256((folder/'corners.png').read_bytes()).hexdigest())
    (folder/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    png=base64.b64encode((folder/'corners.png').read_bytes()).decode()
    (folder/'report.html').write_text('<!doctype html><html><meta charset="utf-8"><title>909 '+target+' ASM</title><style>body{font:17px system-ui;max-width:1400px;margin:40px auto;padding:0 20px;line-height:1.5}img{width:100%}pre{white-space:pre-wrap}</style><h1>909 '+target+' ASM versus VST</h1><p>Every frozen test setting is rendered through the assembled instructions. The VST recordings are unchanged. DSP output is divided by four to match the capture gain, with no per-hit gain fit or sample alignment. This is a waveform comparison, not listening or physical-device acceptance.</p><pre>'+json.dumps({k:v for k,v in report.items() if k not in ('rows','build')},indent=2)+'</pre><img alt="VST and actual ASM at eight corners" src="data:image/png;base64,'+png+'"><p><a href="report.json">Complete numerical receipt</a></p></html>')
    with tempfile.NamedTemporaryFile(dir=destination, suffix='.json', delete=False) as pending:
        pending.write((folder/'report.json').read_bytes())
    Path(pending.name).replace(destination/'report.json')
    print(target,'DONE',{k:v for k,v in report.items() if k not in ('rows','build')},flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('target',choices=('sharc','coldfire'));args=parser.parse_args();qualify(args.target)
