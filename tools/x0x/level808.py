"""Frozen 808 level protocol and one training-only output calibration."""
import math

RATE = 48000
WINDOWS = {"attack": (0, .025), "body": (.025, .15), "tail_body": (.15, .5)}
REFERENCE_FLOOR_FS = .001  # -60 dBFS; keep quieter windows as diagnostics.
LIMIT_DB = 2.0


def levels(samples):
    """Scheduled first 500 ms, without onset alignment or normalization."""
    if len(samples) < RATE // 2:
        raise ValueError("Level measurements need at least 500 ms")
    prefix = samples[:RATE // 2]
    if not all(math.isfinite(x) for x in prefix):
        raise ValueError("Level measurements must be finite")
    result = {"peak": float(max(map(abs, prefix)))}
    for name, (lo, hi) in WINDOWS.items():
        window = prefix[round(lo * RATE):round(hi * RATE)]
        result[name] = math.sqrt(math.fsum(x * x for x in window) / len(window))
    return result


def error_db(actual, reference):
    if not all(math.isfinite(x) and x >= 0 for x in (actual, reference)):
        raise ValueError("Levels must be finite and nonnegative")
    return 20 * math.log10(actual / reference) if actual and reference else None


def fit_factor(errors_db, maximum_peak):
    """Equal-weight squared dB error, subject to unchanged synth headroom."""
    if not errors_db or not all(math.isfinite(x) for x in errors_db):
        raise ValueError("Calibration needs finite training errors")
    if not math.isfinite(maximum_peak) or maximum_peak <= 0:
        raise ValueError("Calibration needs a positive finite peak")
    requested = 10 ** (-math.fsum(errors_db) / len(errors_db) / 20)
    bounded = min(requested, .5 * .999 / maximum_peak)
    # One binary factor is representable in both float32 and the CF Q2.30 load.
    return round(bounded * 2**23) / 2**23


def main():
    import argparse
    import hashlib
    import json
    from pathlib import Path
    from . import coupling808, reference808_grid as grid

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    protocol = dict(version=1, sample_rate=RATE, windows_s=WINDOWS,
                    peak_window_s=[0, .5], reference_floor_fs=REFERENCE_FLOOR_FS,
                    limit_db=LIMIT_DB, reference_multiplier=4,
                    objective='equal-weight squared dB level error across eligible measures, all training takes and both CPUs',
                    headroom_fs=.5, headroom_safety_fraction=.999,
                    gain_scope='one post-C47 factor shared across settings and CPUs',
                    alignment_samples=0, per_hit_normalization=False,
                    held_out_audio_read=False)
    protocol_path = args.output / 'level-protocol.json'
    protocol_path.write_text(json.dumps(protocol, indent=2) + '\n')

    def load(folder):
        revision = json.loads((folder / 'coldfire/report.json').read_text())['commit']
        return {b: grid.load_backend(folder / b, revision)[1] for b in ('coldfire', 'sharc')}

    before = load(args.baseline)
    after = load(args.candidate) if args.candidate else None
    cached = {b: {key: levels(samples) for key, (_, samples) in rows.items()}
              for b, rows in before.items()}
    candidate_levels = ({b: {key: levels(samples) for key, (_, samples) in rows.items()}
                         for b, rows in after.items()} if after else None)
    maximum = max(float(max(map(abs, samples))) for rows in before.values() for _, samples in rows.values())
    records, training_errors = [], []
    for receipt, samples in grid.references(Path('research/reference/808/captures')):
        key = receipt['tone_displayed'], receipt['decay_displayed']
        reference = levels(samples * 4)
        for backend in before:
            for name, target in reference.items():
                value = cached[backend][key][name]
                error = error_db(value, target)
                eligible = target >= REFERENCE_FLOOR_FS
                if eligible:
                    if error is None:
                        raise ValueError('A silent model cannot be repaired by fixed scaling')
                    training_errors.append(error)
                row = dict(reference=receipt['name'], tone=key[0], decay=key[1],
                           backend=backend, metric=name, eligible=eligible,
                           reference_level_fs=target, baseline_level_fs=value,
                           baseline_error_db=error, reference_sha256=receipt['sha256'])
                if after:
                    value = candidate_levels[backend][key][name]
                    row.update(candidate_level_fs=value, candidate_error_db=error_db(value, target))
                records.append(row)
    factor = fit_factor(training_errors, maximum)
    summary = dict(protocol=protocol, protocol_sha256=digest(protocol_path),
                   baseline_render_reports={b: digest(args.baseline / b / 'report.json') for b in before},
                   factor=factor, factor_db=20 * math.log10(factor),
                   source_sha256=digest(Path(__file__)), records=records,
                   eligible=len(training_errors),
                   baseline_passed=sum(abs(e) <= LIMIT_DB for e in training_errors))
    if after:
        if factor != coupling808.OUTPUT_GAIN:
            raise ValueError('Production output factor differs from frozen training calibration')
        errors = [r['candidate_error_db'] for r in records if r['eligible']]
        peak = max(float(max(map(abs, samples))) for rows in after.values() for _, samples in rows.values())
        assert peak < .5, peak
        summary.update(candidate_render_reports={b: digest(args.candidate / b / 'report.json') for b in after},
                       candidate_passed=sum(e is not None and abs(e) <= LIMIT_DB for e in errors),
                       baseline_rms_error_db=math.sqrt(math.fsum(e * e for e in training_errors) / len(errors)),
                       candidate_rms_error_db=math.sqrt(math.fsum(e * e for e in errors) / len(errors)),
                       candidate_peak_fs=peak,
                       all_level_targets_pass=all(e is not None and abs(e) <= LIMIT_DB for e in errors))
    (args.output / 'levels.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k not in ('protocol', 'records')}))


if __name__ == '__main__':
    main()
