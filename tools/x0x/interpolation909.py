"""Interpolate withheld positions in the 909 training grid; reserve final validation."""
import argparse
import itertools
import json
from pathlib import Path

from . import reference909_grid as grid
from .interaction909 import FEATURE_NAMES, ROOT, features
from .reference909_compare import project_gain


def weights(knots, targets, method):
    import numpy as np
    knots, targets = np.asarray(knots, dtype=float), np.asarray(targets, dtype=float)
    width = {'linear': 2, 'cubic': 4}.get(method)
    if (width is None or knots.ndim != 1 or targets.ndim != 1 or len(knots) < width
            or not np.isfinite(knots).all() or not np.isfinite(targets).all()
            or not np.all(np.diff(knots) > 0)
            or np.any(targets < knots[0]) or np.any(targets > knots[-1])):
        raise ValueError('ordered finite knots, supported method and interpolation-only targets required')
    result = np.zeros((len(targets), len(knots)))
    for row, x in enumerate(targets):
        exact = np.flatnonzero(knots == x)
        if len(exact):
            result[row, exact[0]] = 1
            continue
        start = int(np.clip(np.searchsorted(knots, x) - width // 2, 0, len(knots) - width))
        selected = range(start, start + width)
        for j in selected:
            result[row, j] = np.prod([(x - knots[k]) / (knots[j] - knots[k]) for k in selected if k != j])
    return result


def interpolate(values, knots, targets, method):
    """Tensor-product interpolation using actual source control coordinates."""
    import numpy as np
    for axis, (source, target) in enumerate(zip(knots, targets)):
        moved = np.moveaxis(values, axis, 0)
        rows = []
        for row in weights(source, target, method):
            selected = np.flatnonzero(row)
            # Zero-weight missing measurements must not poison unrelated predictions.
            rows.append(np.tensordot(row[selected], moved[selected], axes=(0, 0)))
        values = np.moveaxis(np.stack(rows), 0, axis)
    return values


def experiments():
    all_positions = tuple(range(9))
    targets = (1, 3, 5, 7)
    for training, method in [((0, 4, 8), 'linear'), ((0, 2, 4, 6, 8), 'linear'),
                             ((0, 2, 4, 6, 8), 'cubic')]:
        yield dict(kind='common64', method=method, training=(training,) * 3, targets=(targets,) * 3)
    for axis in range(3):
        for missing in range(1, 8):
            training = [all_positions] * 3
            target = [all_positions] * 3
            training[axis] = tuple(i for i in all_positions if i != missing)
            target[axis] = (missing,)
            for method in ('linear', 'cubic'):
                yield dict(kind='leave_one_position', axis=axis, missing=missing, method=method,
                           training=tuple(training), targets=tuple(target))


def summarize(predicted, actual, controls):
    """Each target keeps three takes; missing features remain unscored."""
    import numpy as np
    valid = np.isfinite(predicted).all(axis=1) & np.isfinite(actual).all(axis=(1, 2))
    count = int(valid.sum())
    if not count:
        return dict(settings=0, excluded_settings=len(valid))
    error = predicted[valid, None, :] - actual[valid]
    per_setting = np.sqrt(np.mean(error ** 2, axis=2))
    energy = np.sum(actual[valid] ** 2, axis=(0, 2))
    worst = int(np.argmax(np.mean(per_setting, axis=1)))
    return dict(settings=count, excluded_settings=len(valid) - count,
                rmse_by_take=np.sqrt(np.mean(error ** 2, axis=(0, 2))).tolist(),
                relative_l2_by_take=[float(np.sqrt(e / a)) if a else None for e, a in
                                    zip(np.sum(error ** 2, axis=(0, 2)), energy)],
                p95_setting_rmse_by_take=np.percentile(per_setting, 95, axis=0).tolist(),
                worst_setting_rmse_by_take=np.max(per_setting, axis=0).tolist(),
                maximum_absolute_error_by_take=np.max(abs(error), axis=(0, 2)).tolist(),
                worst_controls=list(controls[i] for i in np.flatnonzero(valid))[worst],
                negative_predicted_values=int(np.count_nonzero(predicted[valid] < 0)))


def load(output, baseline):
    import numpy as np
    captures, records, manifest = grid.audit(ROOT, output)
    status = json.loads((baseline / 'reference-status.json').read_text())
    assert status['status'] == 'passed' and status['metadata'] == manifest['metadata_sha256']
    for name, key in [('reference-metrics.jsonl', 'metrics_sha256'), ('reference-envelopes.npz', 'envelopes_sha256')]:
        assert grid.digest(baseline / name) == status[key]
    metrics = list(map(json.loads, (baseline / 'reference-metrics.jsonl').read_text().splitlines()))
    assert len(metrics) == len(records) and {r['name'] for r in metrics} == set(records)
    with np.load(baseline / 'reference-envelopes.npz', allow_pickle=False) as saved:
        names, envelopes = saved['names'], saved['rms_10ms'].astype(float)
    assert envelopes.shape == (2187, 1600)
    wave = np.empty((9, 9, 9, 3, 24000))
    env = np.empty((9, 9, 9, 3, 1600))
    scalar = np.empty((9, 9, 9, 3, len(FEATURE_NAMES)))
    for index, record in enumerate(metrics):
        name = record['name']; row = records[name]
        position = tuple(grid.POSITIONS.index(int(row[k + '_displayed'])) for k in ('tune', 'attack', 'decay'))
        take = int(name.rsplit('-r', 1)[1]) - 1
        values, source = grid.read_capture(captures, name, row, project_gain)
        assert source == record['source']
        assert tuple(record[k] for k in ('tune', 'attack', 'decay')) == tuple(grid.POSITIONS[i] for i in position)
        e = record['envelope_row']; assert names[e] == name
        wave[position + (take,)] = values[:24000] * 4
        env[position + (take,)] = envelopes[e]
        scalar[position + (take,)] = [np.nan if v is None else v for v in features(record)]
        if (index + 1) % 243 == 0:
            print('verified captures', index + 1, '/2187', flush=True)
    return wave, env, scalar


def cycle_times(samples):
    """First 13 positive crossings after 6 ms, for the long-decay phase probe."""
    import numpy as np
    indices = np.flatnonzero((samples[:-1] <= 0) & (samples[1:] > 0)) + 1
    times = indices - 1 - samples[indices - 1] / (samples[indices] - samples[indices - 1])
    times = times[times >= .006 * grid.RATE][:13]
    if len(times) != 13 or not np.all((np.diff(times) > grid.RATE / 2000) & (np.diff(times) < grid.RATE / 10)):
        raise ValueError('long-decay probe requires 13 resolved body crossings')
    for lo, hi in zip(times, times[1:]):
        if np.max(abs(samples[int(lo):int(hi) + 1])) < np.max(abs(samples)) * 1e-4:
            raise ValueError('body crossing is below the measurement floor')
    return times / grid.RATE


def phase_probe(wave):
    """Interpolate cycle timing without moving or aligning recorded samples."""
    import numpy as np
    measured = np.stack([cycle_times(wave[t, 0, 8, 0]) for t in range(9)])
    target = (1, 3, 5, 7)
    rows = []
    for train, method in [((0, 4, 8), 'linear'), ((0, 2, 4, 6, 8), 'linear'), ((0, 2, 4, 6, 8), 'cubic')]:
        predicted = weights([grid.POSITIONS[i] for i in train], [grid.POSITIONS[i] for i in target], method) @ measured[list(train)]
        actual = measured[list(target)]
        delta = predicted[:, :12] - actual[:, :12]
        rows.append(dict(training_positions=len(train), method=method,
                         timing_rmse_ms=float(np.sqrt(np.mean(delta ** 2))) * 1000,
                         maximum_timing_error_ms=float(np.max(abs(delta))) * 1000))
    return dict(scope='Tune-only diagnostic at Attack0/Decay255, take1; first12 cycles after6ms',
                target_controls=[grid.POSITIONS[i] for i in target],
                measured_crossings_s=measured.tolist(), results=rows,
                limits='cycle timings only; no reconstructed audio, phase alignment or audibility acceptance')


def run(output):
    import numpy as np
    baseline = ROOT / 'out/reference/909-grid'
    output.mkdir(parents=True, exist_ok=False)
    wave, env, scalar = load(output, baseline)
    result = dict(scope='909 training-only interpolation; final64 validation settings remain reserved',
                  held_out_audio_read=False, history_audio_read=False, production_dsp_changed=False,
                  source_take=1, target_takes=[1, 2, 3], reference_gain=4,
                  normalization=False, alignment_samples=0, averaging=False,
                  cubic='local four-knot Lagrange interpolation; no clipping or monotonicity constraint',
                  limits='waveforms first500ms; envelope/scalar features full16s; feature interpolation does not synthesize audio',
                  feature_status_sha256=grid.digest(baseline / 'reference-status.json'),
                  phase_probe=phase_probe(wave),
                  source_sha256={p: grid.digest(ROOT / p) for p in
                      ('tools/x0x/interpolation909.py', 'tools/x0x/interaction909.py',
                       'tools/x0x/reference909_grid.py', 'tools/x0x/reference909_compare.py')}, experiments=[])
    for experiment in experiments():
        train, targets = experiment['training'], experiment['targets']
        assert not set(itertools.product(*train)) & set(itertools.product(*targets))
        controls = list(itertools.product(*[tuple(grid.POSITIONS[i] for i in axis) for axis in targets]))
        knots = [tuple(grid.POSITIONS[i] for i in axis) for axis in train]
        target_coordinates = [tuple(grid.POSITIONS[i] for i in axis) for axis in targets]
        measurements = {}
        for space, values in [('wave', wave), ('envelope', env), ('features', scalar)]:
            selected = values[np.ix_(*train)][..., 0, :]
            predicted = interpolate(selected, knots, target_coordinates, experiment['method']).reshape(len(controls), -1)
            actual = values[np.ix_(*targets)].reshape(len(controls), 3, -1)
            first = actual[:, 0, :]
            if space == 'wave':
                slices = [('first6ms', 0, 288), ('6to50ms', 288, 2400), ('50to200ms', 2400, 9600),
                          ('200to500ms', 9600, 24000), ('6to500ms', 288, 24000), ('first500ms', 0, 24000)]
            elif space == 'envelope':
                slices = [('first500ms', 0, 50), ('20to500ms', 2, 50), ('full16s', 0, 1600)]
            else:
                slices = [(name, i, i + 1) for i, name in enumerate(FEATURE_NAMES)]
            for name, lo, hi in slices:
                label = space + '_' + name
                measurements[label] = summarize(predicted[:, lo:hi], actual[:, :, lo:hi], controls)
                measurements[label]['repeat_1_vs_targets'] = summarize(first[:, lo:hi], actual[:, :, lo:hi], controls)
                if space == 'features' and name.endswith('pitch_hz'):
                    with np.errstate(invalid='ignore', divide='ignore'):
                        measurements[label]['cents'] = summarize(1200*np.log2(predicted[:, lo:hi]), 1200*np.log2(actual[:, :, lo:hi]), controls)
                    measurements[label]['cents'].pop('relative_l2_by_take', None)
        result['experiments'].append(dict(**experiment, calibration_settings=int(np.prod([len(a) for a in train])),
                                          target_settings=len(controls), measurements=measurements))
        print('interpolated', experiment['kind'], experiment.get('axis', ''), experiment.get('missing', ''), experiment['method'], flush=True)
    grid.dump(output / 'report.json', result)
    (output / 'analyzer-used.py').write_bytes(Path(__file__).read_bytes())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
