"""Training-only test of anchored single-knob and pairwise 909 predictions."""
import argparse
import itertools
import json
from pathlib import Path

from .reference909_compare import project_gain
from . import reference909_grid as grid

ROOT = Path(__file__).resolve().parents[2]
ANCHORS = ((0, 0, 0), (128, 128, 128), (128, 0, 255))
WAVE_WINDOWS = {'first6ms': (0, 288), '6to50ms': (288, 2400),
                '50to200ms': (2400, 9600), '200to500ms': (9600, 24000),
                'first500ms': (0, 24000)}


def predict(values, anchor, pairwise=False):
    """First three dimensions are Tune/Attack/Decay; retain trailing dimensions."""
    t, a, d = anchor
    base = values[t, a, d]
    singles = (values[:, a, d][:, None, None] + values[t, :, d][None, :, None]
               + values[t, a, :][None, None, :])
    if not pairwise:
        return singles - 2 * base
    return (values[:, :, d][:, :, None] + values[:, a, :][:, None, :]
            + values[t, :, :][None, :, :] - singles + base)


def evaluation_mask(size, anchor):
    import numpy as np
    coordinates = np.indices((size, size, size))
    return np.all(coordinates != np.asarray(anchor)[:, None, None, None], axis=0)


def body_attack(values, anchor):
    t, a, d = anchor
    return (values[:, a, :][:, None, :] + values[t, :, d][None, :, None]
            - values[t, a, d])


def score(predicted, actual, mask):
    import numpy as np
    predicted, actual = predicted[mask], actual[mask]
    valid = np.isfinite(predicted).all(axis=-1) & np.isfinite(actual).all(axis=-1)
    if not valid.any():
        return dict(settings=0, rmse=None)
    error = predicted[valid] - actual[valid]
    per_setting = np.sqrt(np.mean(error * error, axis=-1))
    energy = float(np.sum(actual[valid] ** 2))
    coordinates = np.argwhere(mask)[valid]
    return dict(settings=int(valid.sum()), rmse=float(np.sqrt(np.mean(error * error))),
                median_setting_rmse=float(np.median(per_setting)),
                p95_setting_rmse=float(np.percentile(per_setting, 95)),
                worst_setting_rmse=float(np.max(per_setting)),
                worst_controls=[grid.POSITIONS[i] for i in coordinates[np.argmax(per_setting)]],
                relative_l2=float(np.sqrt(np.sum(error * error) / energy)) if energy else None)


def features(record):
    r = record['reference']
    return [r['peak_fs'], r['windows']['first6ms']['rms_fs'] ** 2 * .006,
            r['windows']['first50ms']['rms_fs'] ** 2 * .05,
            r['energy_fs2_s'], r['energy_duration_s']['0.99'],
            r['pitch']['body']['median_hz'], r['pitch']['late']['median_hz']]


FEATURE_NAMES = ('peak_fs', 'energy_first6ms_fs2_s', 'energy_first50ms_fs2_s',
                 'energy_full16s_fs2_s', 't99_s', 'body_pitch_hz', 'late_pitch_hz')


def run(baseline, output):
    import numpy as np
    output.mkdir(parents=True, exist_ok=False)
    captures, records, manifest = grid.audit(ROOT, output)
    status = json.loads((baseline / 'reference-status.json').read_text())
    assert status['status'] == 'passed' and status['metadata'] == manifest['metadata_sha256']
    for filename, key in [('reference-metrics.jsonl', 'metrics_sha256'),
                          ('reference-envelopes.npz', 'envelopes_sha256')]:
        assert grid.digest(baseline / filename) == status[key], 'stale feature artifact'
    metrics = [json.loads(line) for line in (baseline / 'reference-metrics.jsonl').read_text().splitlines()]
    assert len(metrics) == len(records) and {r['name'] for r in metrics} == set(records)
    with np.load(baseline / 'reference-envelopes.npz', allow_pickle=False) as saved:
        envelope_names, envelopes = saved['names'], saved['rms_10ms'].astype(np.float64)
    assert envelopes.shape == (2187, 1600)
    wave = np.empty((9, 9, 9, 3, 24000), dtype=np.float64)
    env = np.empty((9, 9, 9, 3, 1600), dtype=np.float64)
    scalar = np.empty((9, 9, 9, 3, len(FEATURE_NAMES)), dtype=np.float64)
    for index, record in enumerate(metrics):
        name = record['name']; row = records[name]
        t, a, d = (grid.POSITIONS.index(int(row[k + '_displayed'])) for k in ('tune', 'attack', 'decay'))
        take = int(name.rsplit('-r', 1)[1]) - 1
        values, source = grid.read_capture(captures, name, row, project_gain)
        assert source == record['source'], 'stale WAV/project feature provenance'
        assert (record['tune'], record['attack'], record['decay']) == tuple(grid.POSITIONS[i] for i in (t, a, d))
        e = record['envelope_row']; assert envelope_names[e] == name
        wave[t, a, d, take] = values[:24000] * 4
        env[t, a, d, take] = envelopes[e]
        scalar[t, a, d, take] = [np.nan if v is None else v for v in features(record)]
        if (index + 1) % 243 == 0:
            print('verified captures', index + 1, '/2187', flush=True)
    result = dict(scope='anchored representation diagnostic; training-grid settings withheld from each fit',
                  production_dsp_changed=False, held_out_audio_read=False, history_audio_read=False,
                  sample_rate=grid.RATE, reference_gain=4, alignment_samples=0, normalization=False,
                  waveform_scope='scheduled first500ms; envelopes/energy/duration cover full16s',
                  fit_take=1, evaluation_takes=[1, 2, 3], averaging=False,
                  interpretation='no perceptual/fidelity threshold; pairwise success does not identify a circuit',
                  follow_up_model='TuneDecay surface plus Attack curve; exploratory simplification after initial pairwise result',
                  features_missing='unreliable pitch stays missing; each metric reports eligible setting count',
                  feature_status_sha256=grid.digest(baseline / 'reference-status.json'),
                  source_sha256={p: grid.digest(ROOT / p) for p in
                      ('tools/x0x/interaction909.py', 'tools/x0x/reference909_grid.py', 'tools/x0x/reference909_compare.py')},
                  anchors=[])
    spaces = [('waveform_' + n, wave[..., lo:hi]) for n, (lo, hi) in WAVE_WINDOWS.items()]
    spaces += [('envelope_first500ms', env[..., :50]), ('envelope_full16s', env)]
    spaces += [(n, scalar[..., i:i+1]) for i, n in enumerate(FEATURE_NAMES)]
    for controls in ANCHORS:
        anchor = tuple(grid.POSITIONS.index(v) for v in controls)
        mask = evaluation_mask(9, anchor)
        assert int(mask.sum()) == 512
        row = dict(controls=controls, evaluation_settings=512,
                   fit_settings=dict(singles=25, pairwise=217, tune_decay_plus_attack=89), measurements={})
        for name, values in spaces:
            training = values[..., 0, :]
            measurements = {}
            predictions = dict(singles=predict(training, anchor), pairwise=predict(training, anchor, True),
                               tune_decay_plus_attack=body_attack(training, anchor))
            eligible = mask & np.isfinite(values).all(axis=(-1, -2))
            for predicted in predictions.values():
                eligible &= np.isfinite(predicted).all(axis=-1)
            for model, predicted in predictions.items():
                measurements[model] = [score(predicted, values[..., take, :], eligible) for take in range(3)]
                measurements[model + '_negative_predictions'] = int(np.count_nonzero(predicted[eligible] < 0)) if not name.startswith('waveform') else None
            measurements['repeat_1_vs_2_and_3'] = [score(training, values[..., take, :], eligible) for take in (1, 2)]
            row['measurements'][name] = measurements
        result['anchors'].append(row)
    grid.dump(output / 'report.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=ROOT / 'out/reference/909-grid')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.baseline, args.output)
    print('Interaction diagnostic:', args.output / 'report.json')


if __name__ == '__main__':
    main()
