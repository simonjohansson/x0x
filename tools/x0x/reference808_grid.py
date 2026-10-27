"""Raw full-tail training-grid diagnostic for frozen, actual 808 CPU renders.

This consumes component render receipts; it does not render a host substitute,
fit gain/timing, inspect held-out audio, or generate the HTML report.
"""
import argparse
import csv
import json
import re
import statistics
from pathlib import Path

from x0x import analysis
from x0x.reference808_compare import digest, raw_position

RATE, FRAMES = 48000, 12 * 48000
COMMIT = '65aeaf7a76a55248903f2eec2b464752711defd7'
WINDOWS = [('first6ms', 0, .006), ('first25ms', 0, .025),
           ('first150ms', 0, .15), ('first500ms', 0, .5),
           ('first2s', 0, 2), ('tail2to4s', 2, 4),
           ('tail4to8s', 4, 8), ('tail8to12s', 8, 12), ('whole12s', 0, 12)]


def waveform(values):
    import numpy as np
    a = np.asarray(values, dtype=np.float64)
    return dict(frames=len(a), peak_fs=float(np.max(np.abs(a))),
                rms_fs=float(np.sqrt(np.mean(a * a))), dc_fs=float(np.mean(a)),
                energy_fs2_s=float(np.dot(a, a) / RATE))


def residual(actual, reference):
    import numpy as np
    delta = np.asarray(actual, dtype=np.float64) - reference
    return {name: waveform(delta[round(lo * RATE):round(hi * RATE)])
            for name, lo, hi in WINDOWS}


def pitch_windows(a):
    pitch = {}
    for name, lo, hi in [('early', .01, .05), ('body', .05, .2),
                         ('late_sigh', .15, .3), ('settling', .3, .5),
                         ('quiet', .5, 2)]:
        cycles = [c['frequency_hz'] for c in a['frequency']['cycles']
                  if c['valid'] and lo <= (c['start_sample'] + c['end_sample']) / (2 * RATE) < hi]
        pitch[name] = dict(reliable_cycles=len(cycles), reliable=len(cycles) >= 3,
                           median_hz=statistics.median(cycles) if len(cycles) >= 3 else None)
    return pitch


def features(values):
    """Existing estimator on first2s; full12s amplitude/tails stay separate."""
    import numpy as np
    a = analysis.analyze(values[:2 * RATE].tolist(), RATE)
    pitch = pitch_windows(a)
    envelope = np.sqrt(np.mean(np.asarray(values).reshape(-1, 480) ** 2, axis=1))
    return dict(full=waveform(values), windows={name: waveform(values[round(lo * RATE):round(hi * RATE)])
                for name, lo, hi in WINDOWS}, first2s_analysis=a, pitch_windows=pitch,
                envelope_rms_10ms=envelope.tolist())


def grid_records(captures):
    with (captures / 'recordings.csv').open() as stream:
        rows = [r for r in csv.DictReader(stream) if r['split'] == 'grid']
    assert len(rows) == 243 and len({r['name'] for r in rows}) == 243
    settings = {(int(r['tone_displayed']), int(r['decay_displayed'])) for r in rows}
    assert len(settings) == 81
    for tone, decay in settings:
        assert {r['name'] for r in rows if (int(r['tone_displayed']), int(r['decay_displayed'])) == (tone, decay)} == {
            f'grid-t{tone:03}-d{decay:03}-r{repeat}' for repeat in (1, 2, 3)}
    return rows


def unchanged_readbacks(before, after):
    assert set(before) == set(after) == set(range(193))
    assert all(before[i]['normalized'] == after[i]['normalized'] for i in range(193))


def references(captures):
    """Verify only selected training WAVs and retain all three raw repetitions."""
    import numpy as np
    import soundfile as sf
    rows = grid_records(captures)
    protocol = json.loads((captures / 'protocol.json').read_text())
    assert protocol['route'] == 'main' and protocol['channels'] == 2
    tests = {row['name']: row for row in protocol['tests'] if row['split'] == 'grid'}
    wanted = {r['name'] + suffix: {} for r in rows for suffix in (':before', ':after')}
    with (captures / 'settings.tsv').open() as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            if row['capture'] in wanted:
                wanted[row['capture']][int(row['index'])] = row
    frozen = None
    for record in rows:
        name = record['name']; test = tests[name]
        tone, decay = int(record['tone_displayed']), int(record['decay_displayed'])
        assert test['split'] == 'grid' and test['duration'] == 13
        assert test['notes'] == [dict(start=1, finish=1.01, pitch=36, velocity=100)]
        before, after = wanted[name + ':before'], wanted[name + ':after']
        unchanged_readbacks(before, after)
        assert (int(before[3]['displayed']), int(before[2]['displayed'])) == (tone, decay)
        fixed = {str(i): (before[i]['parameter'], before[i]['displayed']) for i in range(59) if i not in (2, 3)}
        if frozen is None:
            frozen = fixed
        assert fixed == frozen and before[0]['displayed'] == '204'
        assert all(before[i]['displayed'] == '128' for i in (1, 4, 5))
        path = captures / (name + '.wav'); project = path.with_suffix('.RPP')
        assert digest(path) == record['sha256']
        state = project.read_text()
        assert float(re.search(r'^\s+VOLPAN (\S+)', state, re.M)[1]) == .25
        assert float(re.search(r'^\s+MASTER_VOLUME (\S+)', state, re.M)[1]) == 1
        assert not re.search(r'^\s+HWOUT ', state, re.M) and 'REC 0 -1 0 ' in state
        data, rate = sf.read(path, always_2d=True, dtype='float64')
        assert sf.info(path).subtype == 'FLOAT' and rate == RATE and data.shape == (13 * RATE, 2)
        assert np.isfinite(data).all() and np.array_equal(data[:, 0], data[:, 1])
        assert float(np.max(np.abs(data))) < 1 and float(np.max(np.abs(data[:RATE]))) < 1e-7
        receipt = dict(name=name, tone_displayed=tone, decay_displayed=decay,
                       tone_raw=raw_position(tone), decay_raw=raw_position(decay),
                       sha256=record['sha256'], project_sha256=digest(project),
                       midi_on_sample=RATE, crop='fixed scheduled MIDI sample48000, no onset alignment',
                       prefix_peak_fs=float(np.max(np.abs(data[:RATE]))),
                       final200ms_peak_fs=float(np.max(np.abs(data[-9600:]))),
                       fixed_source_controls=fixed)
        yield receipt, data[RATE:, 0].copy()


def load_backend(folder, revision=COMMIT):
    report = json.loads((folder / 'report.json').read_text())
    assert report['commit'] == revision, 'render revision differs from selected comparison'
    assert report['status'] == 'passed', 'numeric render is not qualified'
    assert report['frames'] == FRAMES
    assert report['sample_rate'] == RATE and len(report['cases']) == 81
    import numpy as np
    result = {}
    for row in report['cases']:
        key = row['tone_displayed'], row['decay_displayed']
        assert key not in result
        assert (row['tone_raw'], row['decay_raw']) == tuple(raw_position(x) for x in key)
        path = folder / row['path']; assert path.resolve().is_relative_to(folder.resolve())
        assert digest(path) == row['sha256']
        data = np.fromfile(path, dtype='<f4').astype(np.float64)
        assert len(data) == FRAMES and np.isfinite(data).all()
        result[key] = (row, data)
    return report, result


def compare(captures, output, revision=COMMIT):
    import numpy as np
    backends = {b: load_backend(output / b, revision) for b in ('coldfire', 'sharc')}
    assert set(backends['coldfire'][1]) == set(backends['sharc'][1])
    cpu_features = {b: {key: features(data) for key, (_, data) in rows.items()}
                    for b, (_, rows) in backends.items()}
    records, metrics_cache, repeats = [], {}, {}
    cross_cpu = {}
    for key, (_, cf) in backends['coldfire'][1].items():
        sh = backends['sharc'][1][key][1]
        cross_cpu[f't{key[0]:03}-d{key[1]:03}'] = dict(maximum_difference_fs=float(np.max(np.abs(cf-sh))),
            rms_difference_fs=float(np.sqrt(np.mean((cf-sh)**2))))
    for receipt, data in references(captures):
        name = receipt['name']; key = receipt['tone_displayed'], receipt['decay_displayed']
        sha = receipt['sha256']
        if sha not in metrics_cache:
            metrics_cache[sha] = dict(as_recorded=features(data), host_gain_removed=features(data * 4))
        row = dict(reference=receipt, reference_metrics=metrics_cache[sha], backends={})
        for backend, (_, renders) in backends.items():
            render, actual = renders[key]
            row['backends'][backend] = dict(render=render,
                as_recorded_residual=residual(actual, data), host_gain_removed_residual=residual(actual, data*4))
        first = repeats.setdefault(key, data)
        row['maximum_repeat_difference_fs'] = float(np.max(np.abs(data-first)))
        records.append(row)
        print(json.dumps(dict(event='compared', count=len(records), total=243, name=name)), flush=True)
    ranked = {}
    for backend in backends:
        ranking = []
        for key in backends[backend][1]:
            rows = [r for r in records if (r['reference']['tone_displayed'], r['reference']['decay_displayed']) == key]
            errors = [r['backends'][backend]['host_gain_removed_residual']['whole12s']['rms_fs'] for r in rows]
            ranking.append(dict(tone_displayed=key[0], decay_displayed=key[1],
                                mean_rms_error_fs=statistics.fmean(errors), minimum_rms_error_fs=min(errors),
                                maximum_rms_error_fs=max(errors)))
        ranked[backend] = sorted(ranking, key=lambda r: r['mean_rms_error_fs'], reverse=True)
    result = dict(measurement_driver_sha256=digest(Path(__file__)),
        scope='full808 training grid only, actual isolated CPU components, not native OS or fidelity acceptance',
        commit=revision, sample_rate=RATE, frames=FRAMES, reference_recordings=243, settings=81, repeats_per_setting=3,
        posttrigger_window_s=[0,12], feature_window_s=[0,2], reference_multiplier=4,
        gain_reason='verifiedREAPERtrackVOLPAN.25/master1; as-recorded residuals retained',
        fitted_gain=False, alignment_samples=0, held_out_audio_read=False, html_changed=False,
        excluded=dict(validation_recordings=48, history_recordings=7),
        metadata_sha256={f:digest(captures/f) for f in ('protocol.json','recordings.csv','settings.tsv')},
        source_inventory=dict(path=str(output/'source-inventory.json'),
                              sha256=digest(output/'source-inventory.json'),
                              receipt=json.loads((output/'source-inventory.json').read_text())),
        renderer_reports={b:dict(path=str(output/b/'report.json'),sha256=digest(output/b/'report.json'),receipt=r)
                          for b,(r,_) in backends.items()},
        cpu_features={b:{f't{t:03}-d{d:03}':v for (t,d),v in rows.items()} for b,rows in cpu_features.items()},
        cross_cpu=cross_cpu,cross_cpu_limit_fs=1e-5,
        cross_cpu_status='passed' if all(r['maximum_difference_fs']<=1e-5 for r in cross_cpu.values()) else 'failed',
        ranked_whole12s_residuals=ranked,records=records)
    (output/'measurements.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result


def compare_histories(captures, output, revision=COMMIT):
    import numpy as np
    import soundfile as sf
    p, OUT = captures, output
    protocol=json.loads((p/'protocol.json').read_text());tests={t['name']:t for t in protocol['tests'] if t['split']=='history'};assert len(tests)==7
    with (p/'recordings.csv').open() as stream:records={r['name']:r for r in csv.DictReader(stream) if r['split']=='history'}
    assert set(tests)==set(records)
    readbacks={n+s:{} for n in tests for s in (':before',':after')}
    with (p/'settings.tsv').open() as stream:
     for row in csv.DictReader(stream,delimiter='\t'):
      if row['capture'] in readbacks:readbacks[row['capture']][int(row['index'])]=row
    fixed=json.loads((OUT/'measurements.json').read_text())['records'][0]['reference']['fixed_source_controls']
    backends={b:json.loads((OUT/f'history/{b}-current/report.json').read_text()) for b in ('coldfire','sharc')}
    assert all(report['commit'] == revision for report in backends.values()), 'history render revision differs'
    by_backend={b:{r['name']:r for r in report['cases']} for b,report in backends.items()}
    result=[]
    for name,test in tests.items():
     before,after=readbacks[name+':before'],readbacks[name+':after']
     assert set(before)==set(after)==set(range(193))
     assert all(before[i]['normalized']==after[i]['normalized'] for i in range(59))
     assert {str(i):[before[i]['parameter'],before[i]['displayed']] for i in range(59) if i not in (2,3)}==fixed
     path=p/(name+'.wav');assert digest(path)==records[name]['sha256']
     project=path.with_suffix('.RPP');state=project.read_text();assert float(re.search(r'^\s+VOLPAN (\S+)',state,re.M)[1])==.25
     assert float(re.search(r'^\s+MASTER_VOLUME (\S+)',state,re.M)[1])==1
     assert not re.search(r'^\s+HWOUT ',state,re.M) and 'REC 0 -1 0 ' in state
     data,rate=sf.read(path,always_2d=True,dtype='float64');assert rate==48000 and data.shape==(test['duration']*rate,2) and sf.info(path).subtype=='FLOAT'
     assert np.isfinite(data).all() and np.array_equal(data[:,0],data[:,1]) and np.max(abs(data[:rate]))<1e-7
     reference=data[rate:,0];cpu_data={};measured={}
     for backend in backends:
      receipt=by_backend[backend][name];file=OUT/f'history/{backend}-current'/receipt['path'];assert digest(file)==receipt['sha256']
      actual=np.fromfile(file,dtype='<f4').astype(np.float64);assert len(actual)==len(reference)==receipt['frames'] and np.isfinite(actual).all()
      cpu_data[backend]=actual
      measured[backend]=dict(render=receipt,actual=waveform(actual),as_recorded_residual=waveform(actual-reference),host_gain_removed_residual=waveform(actual-reference*4),per_reference_trigger=[])
      for note in test['notes']:
       onset=round((note['start']-1)*rate)
       measured[backend]['per_reference_trigger'].append(dict(reference_onset_sample=onset,first25ms_residual=waveform((actual-reference*4)[onset:onset+1200]),first150ms_residual=waveform((actual-reference*4)[onset:onset+7200])))
     error=float(np.max(np.abs(cpu_data['coldfire']-cpu_data['sharc'])))
     result.append(dict(name=name,protocol=test,reference_sha256=records[name]['sha256'],project_sha256=digest(project),frames=len(reference),reference_as_recorded=waveform(reference),reference_host_gain_removed=waveform(reference*4),backends=measured,cpu_maximum_difference_fs=error,cpu_numeric_limit_fs=1e-5,cpu_status='passed' if error<=1e-5 else 'failed'))
    output=dict(scope='seven explicit declared-single-voice component timelines; not inferred native allocator identity or retrigger fidelity acceptance',commit=revision,records=result,reference_multiplier=4,fitted_gain=False,alignment_samples=0,held_out_audio_read=False,actual_start_scheduling='ceil scheduled MIDI onto32sample blocks; musical event3.125s is16sampleslate; retained visibly, never onset-aligned',START_policy='acceptedbody,Tone,C47clear; priorretainedfiltertrial excluded',rejected_alternate=('history/coldfire is initial retainedTone/C47policy trial, not currentmodbaseline' if revision==COMMIT else None),input_metadata_sha256={f:digest(p/f) for f in ('protocol.json','recordings.csv','settings.tsv')},renderer_report_sha256={b:digest(OUT/f'history/{b}-current/report.json') for b in backends},driver_sha256=digest(Path(__file__)))
    (OUT/'history/measurements.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'records':len(result),'maximum_cpu_difference_fs':max(r['cpu_maximum_difference_fs'] for r in result),'failures':[r['name'] for r in result if r['cpu_status']!='passed']}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--captures',type=Path,default=Path('research/reference/808/captures'))
    parser.add_argument('--output',type=Path,default=Path('out/reference/808-grid'))
    parser.add_argument('--backend',choices=('coldfire','sharc'),help='render actual components before comparison')
    parser.add_argument('--revision',default=COMMIT,help='explicit committed 808 implementation; defaults to the initial baseline')
    parser.add_argument('--frozen-source',type=Path)
    args=parser.parse_args()
    try:
        from .reference_grid_common import _git, prepare_frozen, frozen_invocation
    except ImportError:
        from reference_grid_common import _git, prepare_frozen, frozen_invocation
    revision=_git('rev-parse','--verify',args.revision+'^{commit}').decode().strip()
    frozen_source=args.frozen_source or args.output/('accepted-'+revision[:7])
    if args.backend:
        from x0x import cpu
        metadata=prepare_frozen(frozen_source,revision)
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'frozen.json').write_text(json.dumps(metadata,indent=2)+'\n')
        (args.output/'source-inventory.json').write_text(json.dumps(metadata,indent=2)+'\n')
        if cpu.ROOT.resolve()!=frozen_source.resolve():
            import sys
            forwarded=[*sys.argv[1:],'--revision',revision,'--frozen-source',str(frozen_source.resolve())]
            raise SystemExit(frozen_invocation(__file__,forwarded,frozen_source))
        try:
            from .reference808_grid_render import render
        except ImportError:
            from reference808_grid_render import render
        render(args.backend,args.output.resolve(),args.captures.resolve(),metadata)
    else:
        compare(args.captures,args.output,revision)
        compare_histories(args.captures,args.output,revision)


if __name__=='__main__':main()
