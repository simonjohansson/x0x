"""Isolated Attack0 control-remapping trial using the unchanged 909 host renderer."""
import argparse
from functools import lru_cache
import itertools
import json
from pathlib import Path

from . import body909, trigger909, vca909
from . import reference909_grid as grid
from .reference909_compare import project_gain

ROOT = Path(__file__).resolve().parents[2]
COARSE = (0, 64, 128, 191, 255)
WORDS = tuple(grid.native_word(v) for v in COARSE)
FIT_FRAMES = 24000
FIT_START = 288
WINDOWS = {'first6ms': (0, 288), '6to500ms': (288, 24000), 'first500ms': (0, 24000),
           '500msTo2s': (24000, 96000), 'tail2to16s': (96000, grid.FRAMES), 'full16s': (0, grid.FRAMES)}


@lru_cache(maxsize=128)
def carrier(word):
    import numpy as np
    phases, _, _ = trigger909.reference(FIT_FRAMES, int(word))
    return np.asarray([-body909.GAIN * body909.shaped_triangle(p) for p in phases])


@lru_cache(maxsize=128)
def envelope(word):
    import numpy as np
    return np.asarray([vca909.gain(v) for v in vca909.envelope(FIT_FRAMES, int(word))])


def mapped(word, knots):
    import numpy as np
    if type(word) is not int or not 0 <= word <= body909.RAW_MAX:
        raise ValueError('exact native control word required')
    if len(knots) != 5 or any(type(k) is not int or not 0 <= k <= body909.RAW_MAX for k in knots) or sorted(knots) != list(knots):
        raise ValueError('five monotone native remapping knots required')
    return int(round(float(np.interp(word, WORDS, knots))))


def search(objective, low, high, current):
    """Deterministic bounded integer search, keeping current as a candidate."""
    import numpy as np
    cache = {}
    def value(word):
        word = int(word)
        if word not in cache:
            cache[word] = float(objective(word))
            if not np.isfinite(cache[word]):
                raise ValueError('nonfinite calibration objective')
        return cache[word]
    best = int(current)
    value(best)
    left, right = int(low), int(high)
    for width in (65, 9, 9, 9, 9):
        points = {int(round(v)) for v in np.linspace(left, right, width)} | {best}
        best = min(points, key=lambda word: (value(word), abs(word-current), word))
        step = max(1, (right-left + width-2)//(width-1))
        left, right = max(low, best-step), min(high, best+step)
    return best, value(best), len(cache)


def residuals(predicted, actual):
    import numpy as np
    return {name: dict(rmse_fs=float(np.sqrt(np.mean((predicted[lo:hi]-actual[lo:hi])**2))),
                       maximum_fs=float(np.max(abs(predicted[lo:hi]-actual[lo:hi]))))
            for name, (lo, hi) in WINDOWS.items()}


def run(output):
    import numpy as np
    import soundfile as sf
    output.mkdir(parents=True, exist_ok=False)
    sources = {p: grid.digest(ROOT/p) for p in ('tools/x0x/calibrate909.py', 'tools/x0x/body909.py',
        'tools/x0x/tune909.py', 'tools/x0x/trigger909.py', 'tools/x0x/vca909.py',
        'tools/x0x/reference909_grid.py', 'tools/x0x/reference909_compare.py')}
    protocol = dict(scope='Attack0 host-only control-remapping experiment; existing synthesis stages unchanged',
        fit_controls=COARSE, calibration_settings=25, evaluation_other_training_settings=56, takes=[1,2,3],
        parameters='five monotone native-word knots each for Tune and Decay; piecewise linear between knots',
        parameter_bounds=[0,body909.RAW_MAX], coordinate_passes=2,
        objective='equal settings/takes squared waveform error, scheduled6to500ms; fixed reference gain4',
        source_hashes=sources, gain_fitting=False, alignment_samples=0, normalization=False,
        final_validation_audio_read=False, history_audio_read=False,
        interpretation='training-grid withheld cases were previously explored; no final or blind acceptance',
        adoption='no production changes; preserve regressions and range-bound optima')
    grid.dump(output/'protocol.json', protocol)
    captures, records, manifest = grid.audit(ROOT, output)
    train = np.empty((5,5,3,FIT_FRAMES)); provenance = {}
    for ti,t in enumerate(COARSE):
        for di,d in enumerate(COARSE):
            for take in (1,2,3):
                name=f'grid-u{t:03}-a000-d{d:03}-r{take}'
                values, source = grid.read_capture(captures,name,records[name],project_gain)
                train[ti,di,take-1] = values[:FIT_FRAMES]*4
                provenance[name]=source
    grid.dump(output/'calibration-provenance.json', provenance)
    tune, decay = list(WORDS), list(WORDS)
    baseline_loss=float(np.mean([(carrier(t)*envelope(d)-train[i,j])[:,FIT_START:]**2
        for i,t in enumerate(tune) for j,d in enumerate(decay)]))
    progress=[]
    for sweep in range(2):
        for kind,knots in [('tune',tune),('decay',decay)]:
            for index in range(5):
                if kind=='tune':
                    amplitudes=np.stack([envelope(d) for d in decay])[:,None,FIT_START:]
                    wanted=train[index,:,:,FIT_START:]
                    def objective(word):
                        error=carrier(word)[None,None,FIT_START:]*amplitudes-wanted
                        return np.mean(error**2)
                else:
                    carriers=np.stack([carrier(t) for t in tune])[:,None,FIT_START:]
                    wanted=train[:,index,:,FIT_START:]
                    def objective(word):
                        error=carriers*envelope(word)[None,None,FIT_START:]-wanted
                        return np.mean(error**2)
                low=knots[index-1] if index else 0
                high=knots[index+1] if index<4 else body909.RAW_MAX
                old=knots[index]; old_loss=float(objective(old))
                word,loss,evaluations=search(objective,low,high,old)
                assert loss<=old_loss+1e-16
                knots[index]=word
                row=dict(sweep=sweep+1,control=kind,index=index,old=old,new=word,
                         old_mse=old_loss,new_mse=loss,evaluations=evaluations)
                progress.append(row)
                grid.dump(output/'fit-progress.json',dict(tune=tune,decay=decay,steps=progress))
                print('fit',sweep+1,kind,COARSE[index],old,'->',word,'MSE',loss,flush=True)
    assert tune==sorted(tune) and decay==sorted(decay)
    fit_loss=float(np.mean([(carrier(t)*envelope(d)-train[i,j])[:,FIT_START:]**2
        for i,t in enumerate(tune) for j,d in enumerate(decay)]))
    assert fit_loss<=baseline_loss
    frozen=dict(tune=tune,decay=decay,baseline_mse=baseline_loss,candidate_mse=fit_loss,
                boundary_knots=dict(tune=[i for i,v in enumerate(tune) if v in (0,body909.RAW_MAX)],
                                    decay=[i for i,v in enumerate(decay) if v in (0,body909.RAW_MAX)]),steps=progress)
    grid.dump(output/'frozen-fit.json', frozen)
    # Only after freezing do we open the 56 other training-grid settings.
    metrics=[]
    for t,d in itertools.product(grid.POSITIONS,repeat=2):
        tr,dr=grid.native_word(t),grid.native_word(d)
        mt,md=mapped(tr,tune),mapped(dr,decay)
        baseline,bproof=grid.model_oracle(dr,tr,grid.FRAMES)
        candidate,cproof=grid.model_oracle(md,mt,grid.FRAMES)
        np.testing.assert_allclose(candidate[:FIT_FRAMES],carrier(mt)*envelope(md),atol=1e-14,rtol=0)
        assert np.isfinite(candidate).all() and max(abs(candidate))<1
        label=f'u{t:03}-a000-d{d:03}'
        np.savez_compressed(output/(label+'.npz'),baseline=baseline,candidate=candidate)
        base_metrics,_=grid.measure(baseline); candidate_metrics,_=grid.measure(candidate)
        takes=[]
        for take in (1,2,3):
            name=f'grid-{label}-r{take}'
            values,source=grid.read_capture(captures,name,records[name],project_gain)
            reference=values*4
            reference_metrics,_=grid.measure(reference)
            takes.append(dict(take=take,source=source,reference=reference_metrics,
                              baseline=residuals(baseline,reference),candidate=residuals(candidate,reference)))
        metrics.append(dict(tune=t,decay=d,split='fit25' if t in COARSE and d in COARSE else 'withheld56',
                            mapped_tune=mt,mapped_decay=md,baseline=base_metrics,candidate=candidate_metrics,
                            baseline_render=bproof,candidate_render=cproof,takes=takes))
        if (t,d) in ((0,0),(128,128),(255,255)):
            for name,values in [('reference',reference),('baseline',baseline),('candidate',candidate)]:
                sf.write(output/f'{label}-{name}.wav',values,grid.RATE,subtype='FLOAT')
        print('evaluated',label,metrics[-1]['split'],flush=True)
    summary={}
    for split in ('fit25','withheld56'):
        selected=[row for row in metrics if row['split']==split]
        summary[split]={}
        for window in WINDOWS:
            before=np.asarray([take['baseline'][window]['rmse_fs'] for row in selected for take in row['takes']])
            after=np.asarray([take['candidate'][window]['rmse_fs'] for row in selected for take in row['takes']])
            worst=int(np.argmax(after-before))//3
            summary[split][window]=dict(baseline_rmse_fs=float(np.sqrt(np.mean(before**2))),
                candidate_rmse_fs=float(np.sqrt(np.mean(after**2))),improved_takes=int(np.sum(after<before)),
                regressed_takes=int(np.sum(after>before)),equal_takes=int(np.sum(after==before)),
                largest_regression_fs=float(np.max(after-before)),
                worst_regression_controls=[selected[worst]['tune'],0,selected[worst]['decay']])
    assert all(grid.digest(ROOT/p)==h for p,h in sources.items()),'source changed during experiment'
    result=dict(protocol=protocol,frozen_fit=frozen,summary=summary,cases=metrics,
                acceptance='host-only diagnostic; full fidelity and actual CPU implementation remain unqualified')
    grid.dump(output/'report.json',result)
    (output/'analyzer-used.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
