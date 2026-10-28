"""Build a portable matrix from qualified 808 receipts without rendering audio."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

METRICS = {'t90': 'Decay: 90% energy', 't99': 'Decay: 99% energy',
           'peak': 'Peak level', 'attack': 'Attack level · 0–25 ms',
           'body': 'Body level · 25–150 ms', 'tail_body': 'Tail level · 150–500 ms',
           'pitch_early': 'Early pitch · diagnostic', 'pitch_body': 'Body pitch · diagnostic',
           'pitch_late_sigh': 'Late pitch · diagnostic', 'pitch_settling': 'Settling pitch · diagnostic',
           'pitch_quiet': 'Quiet pitch · diagnostic', 'tone_band': 'Broad body-band ratio · unscored',
           'waveform': 'Raw waveform RMS · unscored', 'numeric': 'CPU vs independent model'}


def result(actual, reference, limit, unit, *, eligible=True, kind='scored', before_error=None):
    if not math.isfinite(limit) or limit <= 0:
        raise ValueError('A positive finite limit is required')
    if any(v is not None and not math.isfinite(v) for v in (actual, reference, before_error)):
        raise ValueError('Nonfinite evidence cannot be scored')
    error = actual-reference if actual is not None and reference is not None else None
    margin = limit-abs(error) if error is not None else None
    status = ('unresolved' if error is None else 'quiet' if not eligible else
              'pass' if margin >= 0 else 'fail')
    return dict(actual=actual, reference=reference, limit=limit, unit=unit,
                error=error, margin=margin, status=status, kind=kind, before_error=before_error)


def build_data(folder):
    def read(name):
        return json.loads((folder/name).read_text())
    def digest(name):
        return hashlib.sha256((folder/name).read_bytes()).hexdigest()
    q = read('final-qualification.json')
    comparison = read('comparison.json')
    grid = read('qualified-grid/measurements.json')
    if (q['status'] != 'passed' or comparison['status'] != 'passed' or
            not q['commit'] == comparison['commit'] == grid['commit'] or
            digest('comparison.json') != q['comparison_sha256'] or
            grid['cross_cpu_status'] != 'passed' or grid['held_out_audio_read']):
        raise ValueError('Use matching, qualified training receipts')
    if len(comparison['records']) != 243 or len(grid['records']) != 243:
        raise ValueError('Expected all 243 separate training takes')
    levels = {(r['name'], r['backend'], r['metric']): r for r in comparison['level_records']}
    references = {r['reference']['name']: r for r in grid['records']}
    cases = {b: {} for b in ('coldfire', 'sharc')}
    for r in comparison['records']:
        receipt = r['reference']; name = receipt['name']
        tone, decay = receipt['tone_displayed'], receipt['decay_displayed']
        key = f't{tone:03}-d{decay:03}'; repeat = int(name.rsplit('-r', 1)[1])
        for backend in cases:
            cell = cases[backend].setdefault(key, dict(tone=tone, decay=decay, tests=[]))
            tests = cell['tests']; data = r['backends'][backend]
            for i, metric in enumerate(('t90', 't99')):
                target = r['reference_duration_ms'][i]
                item = result(data['after_duration_ms'][i], target, max(5, .1*target), 'ms',
                              before_error=data['before_duration_ms'][i]-target)
                tests.append(dict(metric=metric, repeat=repeat, **item))
            for metric in ('peak', 'attack', 'body', 'tail_body'):
                level = levels[name, backend, metric]
                item = result(level['after_error_db'], 0, 2, 'dB', eligible=level['eligible'],
                              before_error=level['before_error_db'])
                tests.append(dict(metric=metric, repeat=repeat, **item))
            reference = references[name]['reference_metrics']['host_gain_removed']['pitch_windows']
            actual = grid['cpu_features'][backend][key]['pitch_windows']
            spectra = [v['first2s_analysis']['spectra']['body']['bands'] for v in
                       (references[name]['reference_metrics']['host_gain_removed'], grid['cpu_features'][backend][key])]
            ratios = [10*math.log10(v[2]['mean_square_fs']/v[1]['mean_square_fs']) for v in spectra]
            tests.append(dict(metric='tone_band', repeat=repeat, kind='diagnostic', status='unscored',
                actual=ratios[1], reference=ratios[0], error=ratios[1]-ratios[0], limit=None,
                margin=None, unit='dB', before_error=None))
            residual = data['windows']['whole12s']['routing_corrected']
            tests.append(dict(metric='waveform', repeat=repeat, kind='diagnostic', status='unscored',
                actual=residual['after'], reference=0, error=residual['after'], limit=None,
                margin=None, unit='FS', before_error=residual['before']))
            for window, target in reference.items():
                measured = actual[window]; valid = target['reliable'] and measured['reliable']
                cents = 1200*math.log2(measured['median_hz']/target['median_hz']) if valid else None
                item = result(cents, 0, 20 if window in ('settling', 'quiet') else 50,
                              'cents', kind='diagnostic')
                tests.append(dict(metric='pitch_'+window, repeat=repeat, **item))
    for backend, cells in cases.items():
        report = read(f'qualified-grid/{backend}/report.json')
        if report['status'] != 'passed' or report['commit'] != q['commit'] or len(cells) != 81:
            raise ValueError('CPU renderer receipt does not match')
        for row in report['cases']:
            key = f"t{row['tone_displayed']:03}-d{row['decay_displayed']:03}"
            cells[key]['tests'].append(dict(metric='numeric', repeat=0,
                **result(row['oracle_maximum_error_fs'], 0, row['numeric_limit_fs'], 'FS', kind='verification')))
    counts = Counter(t['status'] for cells in cases.values() for cell in cells.values()
                     for t in cell['tests'] if t['kind'] == 'scored')
    if sum(counts.values()) != 2916:
        raise ValueError('Every setting, repeat and scored check must be present')
    duration = comparison['durations']['coldfire']
    misses = Counter((r['decay'], r['metric']) for r in duration['checks'] if not r['after_pass'])
    peak_misses = [r for r in comparison['level_records'] if r['backend']=='coldfire' and
                   r['metric']=='peak' and r['eligible'] and abs(r['before_error_db'])<=2<abs(r['after_error_db'])]
    rms = comparison['summary']['coldfire']['whole12s']['routing_corrected']
    progress = dict(duration_before=duration['before_pass'], duration_after=duration['after_pass'],
        duration_total=duration['total'], affected=comparison['summary']['coldfire']['duration'],
        remaining_duration=[dict(decay=d, metric=m, count=n) for (d,m),n in sorted(misses.items())],
        peak_new_failures=len(peak_misses), peak_new_failure_range_db=[min(r['after_error_db'] for r in peak_misses),max(r['after_error_db'] for r in peak_misses)] if peak_misses else None,
        waveform_before=rms['before'], waveform_after=rms['after'])
    progress['affected'] = {k:v for k,v in progress['affected'].items() if k!='checks'}
    return dict(commit=q['commit'], previous_commit=comparison['previous_commit'],
                qualification_sha256=digest('final-qualification.json'), counts=dict(counts), progress=progress,
                cases=cases, metrics=METRICS, qualification={k: q[k] for k in
                    ('host_tests', 'grid_oracle_max_fs', 'history_oracle_max_fs', 'numeric_limit_fs',
                     'peer_grid_max_fs', 'unchanged_grid_settings', 'unchanged_histories',
                     'output_gain_unchanged', 'fresh_native_os', 'physical_devices', 'heldout_audio_used')})


def write_report(folder, output):
    data = build_data(folder)
    payload = json.dumps(data, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c')
    template = Path(__file__).with_suffix('.html').read_text()
    output.mkdir(parents=True, exist_ok=True)
    (output/'index.html').write_text(template.replace('__MATRIX_DATA__', payload))
    print(json.dumps(dict(output=str((output/'index.html').resolve()), counts=data['counts'], commit=data['commit'])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('out/reference/808-test-matrix'))
    args = parser.parse_args()
    write_report(args.evidence, args.output)


if __name__ == '__main__':
    main()
