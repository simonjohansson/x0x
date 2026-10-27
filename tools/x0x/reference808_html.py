"""Portable scientific report with embedded plots and unnormalized audio excerpts."""
import base64
import html
import json
import math

from . import audio


def fmt(value,digits=2):
    return 'unresolved' if value is None else f'{value:.{digits}f}'


def write_report(report,refs,cf,sh,folder):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    rate=report['sample_rate'];lag=report['common_lag']['samples']
    colours=['#7836a5','#146aab','#168259']
    labels=['Reference (known host gain removed)','X0X ColdFire (DT/DN)','X0X SHARC (DN2)']
    def figure(key,shifted):
        signals=[np.asarray(refs[key]),np.asarray(cf[key]),np.asarray(sh[key])]
        fig,axes=plt.subplots(3,2,figsize=(14,11),layout='constrained')
        for col,lo,hi,title in [(0,0,.025,'Attack — MIDI starts at 0'),(1,.025,.15,'Body — fixed gain')]:
            ax=axes[0,col]
            for i,(signal,name,colour) in enumerate(zip(signals,labels,colours)):
                t=np.arange(len(signal))/rate-(lag/rate if shifted and i else 0)
                ax.plot(t*1000,signal,color=colour,lw=1.2,ls='--' if i==2 else '-',label=name)
            ax.set(xlim=(lo*1000,hi*1000),xlabel='Time from scheduled MIDI (ms)',ylabel='Sample amplitude (FS)',title=title)
        row=report['cases'][key]
        for i,(name,colour) in enumerate(zip(['reference_host_gain_removed','coldfire','sharc'],colours)):
            values=row[name]
            env=values['envelope_rms_10ms']
            axes[1,0].plot((np.arange(len(env))+.5)*.01,20*np.log10(np.maximum(env,1e-10)),color=colour,ls='--' if i==2 else '-')
            cycles=[c for c in values['analysis']['frequency']['cycles'] if c['valid']]
            axes[1,1].plot([(c['start_sample']+c['end_sample'])/2/rate*1000 for c in cycles],
                           [c['frequency_hz'] for c in cycles],color=colour,ls='--' if i==2 else '-',marker='.',ms=3)
        axes[1,0].set(xlim=(0,2),ylim=(-120,0),xlabel='Time from MIDI (s)',ylabel='10 ms RMS (dBFS)',title='Envelope — raw timing and fixed scales')
        axes[1,1].set(xlim=(0,500),xlabel='Cycle midpoint from MIDI (ms)',ylabel='Valid cycle estimate (Hz)',title='Pitch trajectory — valid cycles, raw timing')
        for i,(signal,colour) in enumerate(zip(signals,colours)):
            part=signal[int(.02*rate):int(.2*rate)];window=np.hanning(len(part));size=16384
            power=np.abs(np.fft.rfft(part*window,n=size))**2/(size*np.sum(window*window))
            power[1:-1]*=2
            axes[2,0].semilogx(np.fft.rfftfreq(size,1/rate),10*np.log10(np.maximum(power,1e-16)),color=colour,ls='--' if i==2 else '-')
        axes[2,0].set(xlim=(30,10000),ylim=(-130,-10),xlabel='Frequency (Hz)',ylabel='Window-weighted bin power (dB FS²)',title='Spectrum 20–200 ms — raw timing, symmetric Hann')
        av,ev=(signals[1][lag:],signals[0][:-lag]) if shifted and lag>0 else ((signals[1][:lag],signals[0][-lag:]) if shifted and lag<0 else (signals[1],signals[0]))
        start=max(0,-lag)/rate if shifted else 0
        axes[2,1].plot((np.arange(len(av))/rate+start)*1000,av-ev,color='#ae402e',lw=1)
        axes[2,1].set(xlim=(0,150),xlabel='Reference time from MIDI (ms)',ylabel='ColdFire − reference (FS)',title='Residual — '+('supplemental common shift' if shifted else 'primary, unaligned'))
        for ax in axes.flat:ax.grid(alpha=.18)
        fig.legend(*axes[0,0].get_legend_handles_labels(),loc='outside lower center',ncols=3,fontsize=10)
        suffix=f'waveform time axis shifted {-lag:+d} samples; other panels raw' if shifted else 'all timing raw; no alignment'
        fig.suptitle(key.replace('-',' ').title()+' · '+suffix,fontsize=16)
        path=folder/f"{key}-{'aligned' if shifted else 'raw'}.png"
        fig.savefig(path,dpi=140);plt.close(fig)
        return 'data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()
    summaries=[];articles=[]
    for key,row in report['cases'].items():
        ref=row['reference_host_gain_removed'];mod=row['coldfire'];info=report['reference_provenance']['cases'][key]
        ra,ma=ref['analysis'],mod['analysis']
        ratio=ma['peak_fs']/ra['peak_fs']
        summaries.append(f'<tr><th scope="row">{html.escape(key)}</th><td>{info["reference_tone"]}/{info["reference_decay"]}</td><td>{fmt(ra["frequency"]["median_hz"])}</td><td>{fmt(ma["frequency"]["median_hz"])}</td><td>{fmt(ra["decay_positive"]["time_constant_s"]*1000 if ra["decay_positive"]["time_constant_s"] else None,1)} / {fmt(ma["decay_positive"]["time_constant_s"]*1000,1)}</td><td>{20*math.log10(ratio):+.2f} dB</td></tr>')
        players=[]
        for name,samples in [('Reference as recorded',[x/4 for x in refs[key]]),('Reference ×4 host correction',refs[key]),('X0X ColdFire · DT/DN',cf[key]),('X0X SHARC · DN2',sh[key]),('Unaligned ColdFire − corrected reference',[a-b for a,b in zip(cf[key],refs[key])])]:
            path=folder/(key+'-'+str(len(players))+'.wav')
            audio.write_wav(path,samples,rate)
            uri='data:audio/wav;base64,'+base64.b64encode(path.read_bytes()).decode()
            players.append(f'<label class="player">{html.escape(name)}<audio controls preload="metadata" aria-label="{html.escape(key+": "+name)}" src="{uri}"></audio></label>')
        images=(figure(key,False),figure(key,True))
        diff=row['coldfire_vs_reference_host_gain_removed'];aligned=row['supplemental_common_lag_residual']
        articles.append(f'''<article id="{key}" class="case" {'hidden' if key!='default' else ''}>
<h2>{html.escape(key.replace('-',' ').title())}</h2><p>Reference Tone/Decay {info['reference_tone']}/255, {info['reference_decay']}/255 → x0x raw {info['tone_raw']}, {info['decay_raw']}. Three verified identical fresh reference takes.</p>
<div class="badges"><span>Unaligned residual RMS {diff['rms_fs']:.5f} FS</span><span>Common-shift residual RMS {aligned['rms_fs']:.5f} FS</span><span>CPU difference ≤ {row['cpu_maximum_difference_fs']*1e6:.3f} µFS</span><span>Analyzer onset ref/x0x: {ra['onset_sample']}/{ma['onset_sample']} samples</span></div>
<img class="chart" alt="Six measured comparisons for {key}: attack, body, envelope, pitch, spectrum and residual" src="{images[0]}" data-raw="{images[0]}" data-aligned="{images[1]}">
<h3>Listen · 2-second excerpts</h3><p>PCM16 listening copies, fixed gains, no fades or fitted normalization. Their hard stop at 2 seconds is an excerpt boundary, not a modeled release. Metrics use raw floating-point data.</p><div class="players">{''.join(players)}</div></article>''')
    default=report['cases']['default'];dr=default['reference_host_gain_removed']['analysis'];dm=default['coldfire']['analysis']
    priorities=[
        f'Resonator and pitch path: default reference median {dr["frequency"]["median_hz"]:.2f} Hz versus x0x {dm["frequency"]["median_hz"]:.2f} Hz. Model the source-derived body tuning and pitch evolution; a display shift cannot correct pitch drift.',
        'Decay feedback and knob mapping: compare the short/long fits in the table. Derive the stock feedback shelf and control curve rather than tuning each corner independently.',
        'Pulse-edge shaping and loaded Tone/output interaction: examine the attack and spectral panels, then derive the missing RC/diode and forcing stages. Existing isolated Tone/C47 sections are only part of that path.',
        'Output calibration after those shape changes: preserve one global scale. Native AMP/filter/velocity processing is outside these raw engine renders; do not use a per-hit gain fit.'
    ]
    report['priorities']=priorities
    provenance={k:v for k,v in report.items() if k != 'cases'}
    page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>X0X 808 · initial reference comparison</title>
<style>
:root{font-family:system-ui,sans-serif;color:#243044;background:#f3f5f8;font-size:16px}body{margin:0}main{max-width:1240px;margin:auto;padding:32px 24px}h1{font-size:clamp(30px,5vw,48px);line-height:1.1;margin:12px 0 20px}h2{font-size:26px}h3{font-size:19px}p,li{line-height:1.6}header,section,article{background:#fff;border-radius:12px;padding:24px;margin:0 0 22px}.eyebrow{letter-spacing:.1em;font-size:13px;font-weight:700;color:#5c358d}.notice{background:#fff5d9;padding:16px;border-radius:8px}.badges{display:flex;gap:10px;flex-wrap:wrap}.badges span{background:#edf1f6;padding:8px 12px;border-radius:6px;font-variant-numeric:tabular-nums;font-size:14px}.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}td,th{text-align:left;padding:12px 10px;border-bottom:1px solid #d9e0e9;white-space:nowrap}thead{color:#4d5a6d;font-size:14px}.controls{display:flex;align-items:center;gap:18px;flex-wrap:wrap}select,button{font:inherit;padding:10px 14px;min-height:44px;border:1px solid #7e8da1;border-radius:7px;background:white;color:#243044}button[aria-pressed=true]{background:#243e6b;color:white}.chart{display:block;width:100%;height:auto}.players{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}.player{display:block;font-size:14px;font-weight:600}audio{display:block;width:100%;margin-top:8px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}small{color:#4d5a6d}a{color:#185b9d}button:focus-visible,select:focus-visible,audio:focus-visible{outline:3px solid #9a61cf;outline-offset:3px}@media(max-width:600px){main{padding:12px}header,section,article{padding:16px}.controls{gap:10px}}[hidden]{display:none!important}
</style></head><body><main><header><div class="eyebrow">X0X · ISSUE #2 · 27 OCTOBER 2026</div><h1>808: where the current engine differs</h1><div class="badges"><span>5 settings</span><span>15 reference takes</span><span>2 actual ASM backends</span><span>2-second common window</span></div>
<p>Current compiled ColdFire and SHARC code, with fresh input/state, compared to the captured software reference. This is an initial diagnostic, not a fidelity pass. Native device AMP/filter/effects are excluded.</p><p class="notice">Primary comparisons keep scheduled MIDI at zero and apply no alignment or fitted gain. The reference's documented capture-track attenuation of 0.25 is removed with one common ×4 correction. Reference instrument Level/Volume and x0x's internal scale are not calibrated equivalents.</p></header>
<section><h2>Five-setting overview</h2><p>Reference: Roland TR-808 VST3 1.1.4 build22074, REAPER 7.82 on macOS arm64, 48 kHz float capture. BD Level=204/255; Tune/Gain/Pan=128/255; Volume=108/127; Accent Level=0; MIDI note36, velocity100. Only Tone and Decay vary. X0X uses its current fixed intrinsic excitation and ignores pitch/strength; native AMP/velocity processing is excluded.</p><p>Default means approved x0x A/B=64/127 versus the closest captured midpoint 128/255; the fractions differ by 0.198 percentage points. Corners are exact endpoints. Decay values are descriptive positive-peak exponential fits over 2 seconds, not necessarily single physical time constants.</p><div class="scroll"><table><thead><tr><th>Setting</th><th>Reference T/D</th><th>Reference Hz</th><th>X0X Hz</th><th>Decay fit ms: ref / x0x</th><th>X0X/ref peak</th></tr></thead><tbody>'''+''.join(summaries)+'''</tbody></table></div></section>
<section><h2>Explore alignment and differences</h2><div class="controls"><label>Setting <select id="case-select">'''+''.join(f'<option value="{k}">{k.replace("-"," ").title()}</option>' for k in report['cases'])+'''</select></label><button type="button" data-view="raw" aria-pressed="true">Raw timing</button><button type="button" data-view="aligned" aria-pressed="false">Common display shift</button></div><p>'''+f'''The supplemental view shifts the x0x waveform time axis by {-lag:+d} samples ({-lag/rate*1000:+.3f} ms), chosen once from positive correlation of the default's first 200 ms within ±480 samples. The same offset is used at every setting. It can include phase/pitch/attack differences and is <strong>not a measured device latency</strong>. Only waveform/residual panels change; primary metrics, pitch/envelope/spectrum panels and all audio stay raw. No gain is fitted. Individual early-cycle points are exploratory; the summary estimator requires at least three valid cycles.'''+'''</p></section>'''+''.join(articles)+'''<section><h2>What to fix next</h2><p>Engineering interpretation of this initial prototype, to be revisited after DSP changes. The recordings establish software-reference differences, not original-hardware fidelity.</p><ol>'''+''.join('<li>'+html.escape(p)+'</li>' for p in priorities)+'''</ol><p>Held-out recordings, retrigger/history sequences, other strengths, live controls and aliasing/listening acceptance have not been evaluated here. Source files and captures were not changed.</p></section><section><h2>Method and reproducibility</h2><p>The 1-second reference preroll is removed at the documented scheduled MIDI sample, not at detected onset. Both reference channels are checked identical; the left is used. Fifteen source hashes and fresh-repeat identity are verified. Full 12-second reference measurements are retained in report.json; mod rendering/comparison and listening excerpts cover 2 seconds. The long x0x tail continues beyond that window.</p><p>Compiled images are checked against their existing passing component proofs and current production-source hashes, then freshly executed through the guarded emulator fixtures. Numeric backend/oracle agreement uses the existing 1e-5 FS limit; no VST fidelity limits are invented.</p><details><summary>Provenance and diagnostic settings</summary><pre>'''+html.escape(json.dumps(provenance,indent=2))+'''</pre></details></section></main><script>
const select=document.getElementById('case-select');
select.addEventListener('change',()=>{document.querySelectorAll('audio').forEach(a=>a.pause());document.querySelectorAll('.case').forEach(a=>a.hidden=a.id!==select.value);});
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('[data-view]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));document.querySelectorAll('.chart').forEach(i=>i.src=i.dataset[b.dataset.view]);}));
document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(b=>{if(b!==a)b.pause();})));
</script></body></html>'''
    (folder/'index.html').write_text(page)
    (folder/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
