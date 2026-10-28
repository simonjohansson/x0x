"""Frozen fresh-corpus protocol and benchmark for the replacement 808 (#82)."""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import platform

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/fixtures/808-model'
CORPUS = ROOT / 'research/reference/808-fit-model'
RATE, FRAMES = 48000, 264000


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def source_step(cc):
    if type(cc) is not int or not 0 <= cc <= 127:
        raise ValueError('CC must be an integer in 0..127')
    return (cc * 255 + 63) // 127


def native_coordinate(raw):
    """Keep fractional native modulation between the captured integer anchors."""
    if isinstance(raw, bool) or not math.isfinite(raw) or not 0 <= raw <= 127 * 256:
        raise ValueError('Native control must be finite in 0..32512')
    cc, fraction = divmod(float(raw) / 256, 1)
    lo = source_step(int(cc))
    hi = source_step(min(int(cc) + 1, 127))
    return (lo + fraction * (hi - lo)) / 255


def protocol():
    config = json.loads((FIXTURES / 'protocol.json').read_text())
    if digest(FIXTURES / 'events.csv') != config['events_sha256']:
        raise ValueError('Frozen event manifest hash mismatch')
    with (FIXTURES / 'events.csv').open(newline='') as stream:
        events = [{k: v if k in ('capture_group', 'partition') else int(v)
                   for k, v in row.items()} for row in csv.DictReader(stream)]
    groups = defaultdict(set)
    for i, event in enumerate(events):
        pair = event['tone_cc'], event['decay_cc']
        if (event['index'] != i or event['slot_frames'] != FRAMES or
                event['onset_sample'] != RATE + i * FRAMES or
                event['parameter_change_sample'] != event['onset_sample'] - 12000 or
                any(event[name + '_source'] != source_step(event[name + '_cc'])
                    for name in ('tone', 'decay'))):
            raise ValueError('Invalid frozen event coordinates/timing')
        groups[event['partition']].add(pair)
    if (len(events) != 512 or {k: len(v) for k, v in groups.items()} != config['setting_counts'] or
            len(set.union(*groups.values())) != 480):
        raise ValueError('Invalid grouped partition or repeated setting leakage')
    return config, events


def checked_path(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Artifact path escapes corpus')
    return path


def verify_artifacts(folder, config, events):
    expected = dict(config['artifacts_sha256'])
    for name in ('SHA256SUMS', 'model/SHA256SUMS'):
        path = folder / name
        if digest(path) != expected[name]:
            raise ValueError('Checksum manifest mismatch: ' + name)
        for line in path.read_text().splitlines():
            value, relative = line.split('  ', 1)
            relative = str(checked_path(folder, str(Path(name).parent / relative)).relative_to(folder.resolve()))
            if relative in expected and expected[relative] != value:
                raise ValueError('Conflicting artifact hashes: ' + relative)
            expected[relative] = value
    for name, value in expected.items():
        if digest(checked_path(folder, name)) != value:
            raise ValueError('Artifact hash mismatch: ' + name)
    capture = json.loads((folder / '808-corpus-protocol.json').read_text())
    split = json.loads((folder / 'model/split.json').read_text())
    if len(capture['events']) != len(events) or len(split['events']) != len(events):
        raise ValueError('Capture/split length mismatch')
    for frozen, original, assigned in zip(events, capture['events'], split['events']):
        if (any(original[k] != frozen[k] for k in frozen if k not in ('capture_group', 'partition')) or
                original['split'] != frozen['capture_group'] or
                any(assigned[k] != frozen[k] for k in assigned)):
            raise ValueError('Capture/split differs from frozen manifest')
    with (folder / '808-corpus-control-readbacks.tsv').open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    if len(rows) != 256 or len({(r['cc'], r['parameter']) for r in rows}) != 256:
        raise ValueError('Missing control readbacks')
    for row in rows:
        step = source_step(int(row['cc']))
        if (row['parameter'] not in ('tone', 'decay') or int(row['displayed']) != step or
                not math.isclose(float(row['normalized']), step / 255, abs_tol=1e-7)):
            raise ValueError('Control readback mismatch')
    snapshots = []
    for name in ('before', 'after'):
        with (folder / f'808-corpus-{name}.tsv').open() as stream:
            snapshots.append({r['index']: r for r in csv.DictReader(stream, delimiter='\t')})
    if (snapshots[0].keys() != snapshots[1].keys() or len(snapshots[0]) != 193 or
            any(row != snapshots[1][key] for key, row in snapshots[0].items()
                if row['parameter'] not in ('BD TONE', 'BD DECAY'))):
        raise ValueError('A fixed source parameter changed')
    return expected


def read_slot(wav, event):
    import numpy as np
    if wav.samplerate != RATE or wav.channels != 2 or wav.subtype != 'FLOAT':
        raise ValueError('Expected the original 48 kHz stereo float32 WAV')
    wav.seek(event['onset_sample'])
    data = wav.read(FRAMES, dtype='float64', always_2d=True)
    if (data.shape != (FRAMES, 2) or not np.isfinite(data).all() or
            not np.array_equal(data[:, 0], data[:, 1])):
        raise ValueError('Incomplete, nonfinite or unequal-channel capture slot')
    return data[:, 0]


def measure(prediction, reference, config):
    """Inputs are capture-gain samples at scheduled trigger time, without alignment."""
    import numpy as np
    p, r = np.asarray(prediction, dtype=float), np.asarray(reference, dtype=float)
    if p.ndim != 1 or p.shape != r.shape or len(p) != FRAMES or not np.isfinite([p, r]).all():
        raise ValueError('Expected complete finite 264000-sample mono slots')
    error = p - r
    windows = {}
    for name, (lo, hi) in config['windows'].items():
        rr, ee = r[lo:hi], error[lo:hi]
        energy = float(rr @ rr)
        rms = float(np.sqrt(energy / len(rr)))
        windows[name] = dict(relative_l2=float(np.sqrt((ee @ ee) / energy)) if energy else None,
            reference_rms_fs=rms, residual_rms_fs=float(np.sqrt(np.mean(ee * ee))),
            residual_max_fs=float(np.max(abs(ee))), active=rms >= config['gates']['active_reference_rms_fs'])
    pe, re = float(p @ p), float(r @ r)
    pp, rp = float(np.max(abs(p))), float(np.max(abs(r)))
    def t99(y, energy):
        return int(np.searchsorted(np.cumsum(y * y), .99 * energy)) * 1000 / RATE if energy else 0.
    return dict(relative_l2=windows['whole']['relative_l2'], windows=windows,
        peak_error_db=20 * math.log10(pp / rp) if pp and rp else 0. if pp == rp else None,
        energy_error_percent=100 * (pe / re - 1) if re else 0. if not pe else None,
        t99_error_ms=t99(p, pe) - t99(r, re))


def summarize(rows, config):
    import numpy as np
    groups = defaultdict(list)
    for row in rows:
        groups[row['tone_cc'], row['decay_cc']].append(row)
    result = {}
    gates = config['gates']
    for category in ('all', 'isolated', 'interaction'):
        chosen = [(pair, takes) for pair, takes in groups.items() if category == 'all' or
                  ((0 in pair) == (category == 'isolated'))]
        if not chosen:
            continue
        checks = {}
        def stats(values):
            return dict(median=float(np.median(values)), p95=float(np.percentile(values, 95)),
                        worst=float(np.max(values)))
        relative = [float(np.mean([r['relative_l2'] for r in takes])) for _, takes in chosen]
        whole = stats(relative)
        checks['whole'] = all(whole[k] <= limit for k, limit in gates['whole_relative_l2'].items())
        windows = {}
        for name in config['windows']:
            active, quiet_failures = [], 0
            for _, takes in chosen:
                active_takes = [r['windows'][name]['relative_l2'] for r in takes if r['windows'][name]['active']]
                if active_takes:
                    active.append(float(np.mean(active_takes)))
                quiet_failures += sum(not w['active'] and
                    (w['residual_rms_fs'] > gates['quiet_residual_rms_fs'] or
                     w['residual_max_fs'] > gates['quiet_residual_max_fs'])
                    for w in (r['windows'][name] for r in takes))
            windows[name] = dict(active_settings=len(active), active_relative_l2=stats(active) if active else None,
                                 quiet_take_failures=quiet_failures)
            # The late tail is diagnostic; the quiet residual floor still applies.
            if name not in ('whole', 'tail500ms_to_end'):
                checks[name] = not active or all(windows[name]['active_relative_l2'][k] <= limit
                    for k, limit in gates['active_window_relative_l2'].items())
            checks[name + '_quiet'] = quiet_failures == 0
        levels = {}
        for name, limit in [('peak_error_db', gates['absolute_peak_db']),
                            ('energy_error_percent', gates['absolute_energy_percent']),
                            ('t99_error_ms', gates['absolute_t99_ms'])]:
            valid = all(r[name] is not None for _, takes in chosen for r in takes)
            values = [float(np.mean([abs(r[name]) for r in takes])) for _, takes in chosen] if valid else []
            levels[name] = stats(values) if values else None
            checks[name] = valid and levels[name]['worst'] <= limit
        result[category] = dict(settings=len(chosen), takes=sum(len(takes) for _, takes in chosen),
            relative_l2=whole, worst_controls=list(chosen[int(np.argmax(relative))][0]),
            windows=windows, absolute_errors=levels, checks=checks, passes_gates=all(checks.values()))
    return result


def teacher_weights(model, queries):
    """Local cubic tensor interpolation of the independent axes and joint residual."""
    import numpy as np
    def weights(knots, targets):
        x = np.array([source_step(int(k)) / 255 for k in knots])
        if len(x) < 4 or not np.all(np.diff(x) > 0):
            raise ValueError('Teacher knots must be strictly increasing')
        matrix = np.zeros((len(targets), len(x)))
        for row, target in enumerate(targets):
            z = source_step(int(target)) / 255
            if not x[0] <= z <= x[-1]:
                raise ValueError('Teacher extrapolation is forbidden')
            exact = np.flatnonzero(x == z)
            if len(exact):
                matrix[row, exact[0]] = 1
                continue
            start = int(np.clip(np.searchsorted(x, z) - 2, 0, len(x) - 4))
            selected = range(start, start + 4)
            for j in selected:
                matrix[row, j] = np.prod([(z - x[k]) / (x[j] - x[k]) for k in selected if k != j])
        return matrix
    index = {tuple(pair): i for i, pair in enumerate(model['pairs'])}
    result = np.zeros((len(queries), len(index)))
    for key in ('axis', 'grid'):
        t = weights(model[key], [p[0] for p in queries])
        d = weights(model[key], [p[1] for p in queries])
        if key == 'axis':
            for j, cc in enumerate(model[key]):
                result[:, index[cc, 0]] += t[:, j]
                result[:, index[0, cc]] += d[:, j]
            result[:, index[0, 0]] -= 1
        else:
            for i, tone in enumerate(model[key]):
                for j, decay in enumerate(model[key]):
                    w = t[:, i] * d[:, j]
                    result[:, index[tone, decay]] += w
                    result[:, index[tone, 0]] -= w
                    result[:, index[0, decay]] -= w
                    result[:, index[0, 0]] += w
    return result


def benchmark(folder, config, events, partition):
    import numpy as np
    import soundfile as sf
    with np.load(folder / config['teacher']['path'], allow_pickle=False) as data:
        model = {k: data[k] for k in data.files}
    expected_pairs = sorted({(e['tone_cc'], e['decay_cc']) for e in events if e['partition'] == 'train'})
    if (model['pairs'].tolist() != [list(p) for p in expected_pairs] or
            model['basis'].shape != (48, FRAMES) or model['coefficients'].shape != (193, 48) or
            str(model['method']) != 'cubic' or not bool(model['interaction']) or
            not np.isfinite(model['basis']).all() or not np.isfinite(model['coefficients']).all()):
        raise ValueError('Expected the frozen fitting-only teacher, not the all-data refit')
    selected = [e for e in events if e['partition'] == partition]
    rows = []
    with sf.SoundFile(folder / '808-corpus.wav') as wav:
        for start in range(0, len(selected), 8):
            batch = selected[start:start + 8]
            weights = teacher_weights(model, [(e['tone_cc'], e['decay_cc']) for e in batch])
            predicted = ((weights @ model['coefficients']) @ model['basis']).astype('float32')
            for event, y in zip(batch, predicted):
                rows.append(dict(index=event['index'], tone_cc=event['tone_cc'], decay_cc=event['decay_cc'],
                                 **measure(y, read_slot(wav, event), config)))
    summary = summarize(rows, config)
    expected = config['teacher']['expected_' + partition]
    for name, actual in summary.items():
        for metric, old in [('median', 'median_relative_l2'), ('p95', 'p95_relative_l2'), ('worst', 'worst_relative_l2')]:
            if abs(actual['relative_l2'][metric] - expected[name][old]) > config['teacher']['regression_absolute_tolerance']:
                raise ValueError('Teacher benchmark regression: ' + name + '/' + metric)
    return dict(partition=partition, reproduced=True, summary=summary, records=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('verify', 'benchmark'))
    parser.add_argument('--corpus', type=Path, default=CORPUS)
    parser.add_argument('--partition', choices=('validation', 'test'), default='test')
    parser.add_argument('--output', type=Path, default=ROOT / 'out/808-model/protocol-benchmark.json')
    args = parser.parse_args()
    if (args.output.resolve().is_relative_to(args.corpus.resolve()) or
            args.output.resolve().is_relative_to(FIXTURES.resolve())):
        parser.error('Write reports outside the immutable corpus and protocol fixtures')
    config, events = protocol()
    hashes = verify_artifacts(args.corpus, config, events)
    result = dict(protocol=config['version'], artifacts_verified=len(hashes), artifact_sha256=hashes,
                  driver_sha256=digest(Path(__file__)), protocol_sha256=digest(FIXTURES / 'protocol.json'),
                  events_sha256=config['events_sha256'], scope='Host only; no DSP or physical-device evidence.')
    import numpy as np
    import soundfile as sf
    result['environment'] = dict(python=platform.python_version(), numpy=np.__version__, soundfile=sf.__version__)
    with sf.SoundFile(args.corpus / '808-corpus.wav') as wav:
        if wav.frames != RATE + 512 * FRAMES:
            raise ValueError('Unexpected corpus duration')
        maximum, quiet, onset_ok = 0., 0., True
        for event in events:
            slot = read_slot(wav, event)
            maximum = max(maximum, float(np.max(abs(slot))))
            quiet = max(quiet, float(np.max(abs(slot[-12000:]))))
            active = np.flatnonzero(abs(slot) >= 1e-7)
            onset_ok &= bool(len(active) and active[0] == 1)
        if maximum >= 1 or quiet >= 1e-7 or not onset_ok:
            raise ValueError('Capture onset/clipping/quiet-tail audit failed')
        result['audio'] = dict(slots=512, maximum_peak_fs=maximum, maximum_last250ms_fs=quiet,
                               threshold_onset_sample=1, normalization=False, alignment=False)
    if args.command == 'benchmark':
        result.update(benchmark(args.corpus, config, events, args.partition))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(f"Verified {len(hashes)} artifacts and 512 audio slots; {args.output}")
    if 'summary' in result:
        for category, summary in result['summary'].items():
            values = summary['relative_l2']
            print(category, {k + '_percent': 100 * v for k, v in values.items()},
                  'compact gates:', summary['passes_gates'])


if __name__ == '__main__':
    main()
