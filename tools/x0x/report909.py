"""Make the local 909 capture/model/ASM report after both full qualifications pass."""
import base64
import html
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from . import field909,fit909,qualify909


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    root=fit909.ROOT;folder=root/'model';folder.mkdir(exist_ok=True)
    reports={target:qualify909.load_report(target) for target in ('sharc','coldfire')}
    fig,ax=plt.subplots(figsize=(9,4),constrained_layout=True)
    for target,r in reports.items():
        values=sorted(100*x['l2'] for x in r['rows'] if x['partition']=='test');ax.plot(values,np.linspace(0,100,len(values)),label=target.upper(),linewidth=2)
    ax.set(xlabel='Whole-waveform error (%) — smaller is closer',ylabel='Held-out recordings at or below this error (%)',title='Every held-out recording, rendered through actual ASM');ax.grid(alpha=.2);ax.legend();fig.savefig(folder/'asm-error-cdf.png',dpi=150);plt.close(fig)
    ticks=sorted({e['tune_cc'] for e in fit909.load_events() if e['split']=='interaction'})
    fig,axes=plt.subplots(1,3,figsize=(14,4),constrained_layout=True);rows=[x for x in reports['sharc']['rows'] if x['partition']=='test']
    for fixed,ax in enumerate(axes):
        others=[i for i in range(3) if i!=fixed];matrix=np.full((16,16),np.nan)
        for row in rows:
            key=row['settings']
            if key[fixed]==110:
                i,j=ticks.index(key[others[1]]),ticks.index(key[others[0]])
                value=100*row['l2'];matrix[i,j]=value if np.isnan(matrix[i,j]) else max(matrix[i,j],value)
        im=ax.imshow(matrix,origin='lower',extent=(-4,131,-4,131),cmap='magma',vmin=0,vmax=7.1,aspect='equal')
        names=('Tune','Attack','Decay');ax.set(xlabel=names[others[0]]+' CC',ylabel=names[others[1]]+' CC',title=names[fixed]+' withheld at CC 110')
    fig.colorbar(im,ax=axes,label='Raw whole-waveform error (%)');fig.savefig(folder/'withheld-planes.png',dpi=160);plt.close(fig)
    worst=sorted(rows,key=lambda r:r['l2'],reverse=True)[:2];events={e['index']:e for e in fit909.load_events()};raw=fit909.raw_audio()
    fig,axes=plt.subplots(2,3,figsize=(14,7),constrained_layout=True)
    for i,row in enumerate(worst):
        e=events[row['index']];start=e['onset_sample'];reference=np.asarray(raw[start:start+96000,0],dtype=float);predictions={}
        for target,r in reports.items():
            match=next(x for x in r['rows'] if x['index']==row['index'])
            with sf.SoundFile(r['rendered_wav']) as f:f.seek(match['render_offset']);predictions[target]=f.read(96000,dtype='float64')/4
        for j,(limit,step) in enumerate(((24000,8),(960,1),(1152,1))):
            ax=axes[i,j];t=np.arange(0,limit,step)/48
            if j<2:
                ax.plot(t,reference[:limit:step],label='VST recording',color='#202b38',linewidth=1)
                for target,y in predictions.items():ax.plot(t,y[:limit:step],label=target.upper()+' ASM / 4',linewidth=.8,alpha=.8)
            else:ax.plot(t,(predictions['sharc']-reference)[:limit:step],color='#b55d15',label='ASM minus VST')
            ax.set_xlabel('Milliseconds after MIDI trigger');ax.grid(alpha=.2)
            if j==0:ax.set_ylabel('Source full scale')
            if i==0:ax.legend(fontsize=8)
        axes[i,0].set_title('Tune %d / Attack %d / Decay %d: %.2f%% error'%(*row['settings'],100*row['l2']))
    fig.suptitle('The two worst held-out recordings: body, first 20 ms, transient residual');fig.savefig(folder/'worst-held-out.png',dpi=150);plt.close(fig)
    def picture(path,alt):return '<img alt="'+html.escape(alt)+'" src="data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()+'">'
    table=''
    for target,r in reports.items():
        table+=f'<tr><td>{target.upper()}</td><td>{100*r["l2"]["median"]:.3f}%</td><td>{100*r["l2"]["p95"]:.3f}%</td><td>{100*r["l2"]["max"]:.3f}%</td><td>{100*r["after10ms_l2"]["max"]:.3f}%</td><td>{r["maximum_port_dsp_fs"]:.3g}</td></tr>'
    metadata=json.loads((field909.ROOT/'models/909.json').read_text())
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>909 reference model and ASM qualification</title><style>body{font:17px system-ui;line-height:1.55;max-width:1350px;margin:40px auto;padding:0 24px;color:#202b38}h1,h2{line-height:1.2}img{width:100%;height:auto}table{border-collapse:collapse;width:100%;font-size:15px}th,td{padding:10px;text-align:left;border-bottom:1px solid #ccd2d8}code{overflow-wrap:anywhere}aside{padding:18px;background:#edf7f6;border-left:5px solid #008b91}li{margin:8px 0}</style><h1>909: captured behaviour → fitted model → actual ASM</h1><aside>Both handwritten ASM implementations pass the local waveform comparison. Across every held-out setting, median error is about 2.53%, and 95% of recordings are below about 3.91%. Listening and physical-device acceptance remain separate.</aside><p><a href="report.html">Captured isolated-knob curves and joint interaction explorer</a></p><h2>What was tested</h2><p>One fresh WAV contains 384 isolated-knob positions and 4,096 joint positions: 4,480 scheduled kicks and 4,432 distinct Tune/Attack/Decay settings. Two-second slots were chosen from fresh maximum-Decay pilots. The frozen test set is the union of three complete planes with one knob withheld at CC 110: 721 settings, compared against 724 raw recordings. All repeats stay in the same fitting partition.</p><p>Each target executes 731 complete, 96,000-sample hits: the 721 held-out settings, eight corners and two fractional native-control cases. ColdFire additionally matches an independent integer specification sample for sample and state for state. Every comparison uses the original sample timing and one fixed gain conversion: native DSP output divided by four to compensate the capture track's 0.25 gain.</p><h2>Measured error</h2><p>Waveform error measures the difference across all samples relative to the recording's overall signal size. Lower is closer. These numbers measure waveform agreement; audibility requires listening.</p><table><tr><th>Actual ASM</th><th>Median VST error</th><th>95th percentile</th><th>Worst VST error</th><th>Worst after 10 ms</th><th>Maximum ASM/model difference, DSP FS</th></tr>'''+table+'''</table><p>For the held-out set, overall level stays within about −0.061 to +0.100 dB, peak level within −0.460 to +0.146 dB, and time to 99% of energy within −2.125 to +1.959 ms. Raw source repetitions vary too: duplicate-setting whole-waveform differences reach 5.35%. Remaining prediction error includes source-history variation and model approximation.</p>'''+picture(folder/'asm-error-cdf.png','Cumulative waveform error for both actual ASM targets')+'''<p>At 95% on the vertical axis, the horizontal axis reads about 3.91% error. Both target curves overlap because their numerical differences are tiny beside the remaining VST/model differences.</p><h2>Every withheld interaction plane</h2>'''+picture(folder/'withheld-planes.png','Error maps over all three held-out CC 110 planes')+'''<p>Every coloured cell is a measured setting excluded from fitting. Darker is closer. Where a setting has repeated recordings, the cell shows the largest raw error. The maps use SHARC output; ColdFire gives effectively the same source-error map.</p><h2>The hardest held-out cases</h2>'''+picture(folder/'worst-held-out.png','Two worst held-out VST waveforms and native ASM predictions')+'''<p>Left: first 500 ms. Middle: first 20 ms. Right: prediction minus recording during the first 24 ms. The target lines overlap at this scale. The short transient carries most of the largest remaining differences.</p><h2>How the model works</h2><ol><li><b>Tune</b> selects a fitted pitch sweep approaching a shared 52.572 Hz carrier. The ASM maintains the carrier phase and a decaying pitch perturbation.</li><li><b>Decay</b> selects five shared envelope-field weights. Cubic time curves modulate the DC term and sine/cosine harmonics 1–5, including the measured release knee near 64 ms.</li><li><b>Tune × Attack</b> jointly selects twelve short onset-residual components. A smooth transition brings in the harmonic body between 6 and 8 ms; the residual fades out between 22 and 24 ms.</li><li>The same frozen coefficient source feeds both targets. SHARC uses packed coefficients and float arithmetic; ColdFire expands the tables to bounded fixed-point arithmetic. Production sample loops are ASM; the C integer implementation is a host test oracle.</li></ol><h2>Eight measured corners</h2>'''+picture(Path(reports['sharc']['corners_png']),'Eight corner VST recordings compared with actual SHARC ASM')+'''<h2>Scope and provenance</h2><p>The full corpus was inspected descriptively; these are fitting holdouts rather than independent fresh-source acceptance. The model covers captured isolated hits at the recorded fixed settings. Dynamic control/retrigger behaviour, physical TR-909 equivalence and inaudibility have not been established. Source global quality options were not freshly read; the earlier user confirmation is historical.</p><p>Coefficient SHA-256: <code>'''+field909.MODEL_SHA+'''</code><br>Capture SHA-256: <code>'''+metadata['capture_sha256']+'''</code></p><p>Raw capture, manifests, readbacks and earlier failed checks remain preserved beside the capture report. Full target receipts and native rendered WAVs are in <code>out/909-model/qualification/{sharc,coldfire}/</code>. The native WAVs retain DSP gain; divide by four for comparison with the source capture. No A/B page is started by this report.</p></html>'''
    path=root/'model-report.html';path.write_text(page);print(path)


if __name__=='__main__':main()
