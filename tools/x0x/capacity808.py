"""Fitting-only generator capacity experiment; not the shipping control model (#84)."""
import argparse
import json
from pathlib import Path
import platform
import time

from . import fit808


def columns(parameters, seconds, harmonic=False):
    """Two complex envelopes share one phase trajectory; transients decay to zero."""
    import numpy as np
    f0, bend1, log_pitch1, bend2, log_pitch_gap, log_fast, log_gap, log_dc = parameters[:8]
    pitch1 = np.exp(log_pitch1)
    pitch2 = pitch1 + np.exp(log_pitch_gap)
    fast = np.exp(log_fast)
    slow = fast + np.exp(log_gap)
    phase = 2 * np.pi * (f0 * seconds - bend1 * pitch1 * np.expm1(-seconds / pitch1)
                        - bend2 * pitch2 * np.expm1(-seconds / pitch2))
    sine, cosine = np.sin(phase), np.cos(phase)
    envelopes = [np.exp(-seconds / slow), np.exp(-seconds / fast)]
    result = [v * wave for v in envelopes for wave in (sine, cosine)]
    result.append(np.exp(-seconds / np.exp(log_dc)))
    if harmonic:
        envelope = np.exp(-seconds / np.exp(parameters[8]))
        result += [envelope * np.sin(2 * phase), envelope * np.cos(2 * phase)]
    return np.column_stack(result)


def sample_objective(reference, config):
    """Deterministic quadrature for full-slot and equally weighted short-window losses."""
    import numpy as np
    indices = np.concatenate([np.arange(0, 288), np.arange(288, 2400, 4),
                              np.arange(2400, 24000, 16), np.arange(24000, fit808.FRAMES, 128)])
    width = np.diff(np.r_[indices, fit808.FRAMES])
    energy = float(reference @ reference)
    weight2 = width / energy
    for name, (lo, hi) in config['windows'].items():
        if name in ('whole', 'tail500ms_to_end'):
            continue
        region = reference[lo:hi]
        region_energy = float(region @ region)
        if np.sqrt(region_energy / len(region)) >= config['gates']['active_reference_rms_fs']:
            weight2 += .25 * width * ((indices >= lo) & (indices < hi)) / region_energy
    return indices, np.sqrt(weight2)


def fit_one(reference, config, experiment, harmonic=False):
    import numpy as np
    from scipy.optimize import least_squares
    indices, weights = sample_objective(reference, config)
    seconds = indices / fit808.RATE
    target = reference[indices] * weights
    energy = np.cumsum(reference * reference)
    t99 = np.searchsorted(energy, .99 * energy[-1]) / fit808.RATE
    tau = np.clip(t99 / 2.3026, .004, 1.)
    lo = np.array([30, -10, np.log(.00005), -10, np.log(.0005), np.log(.00015), np.log(.001), np.log(.00003)])
    hi = np.array([85, 300, np.log(.03), 150, np.log(2.), np.log(.05), np.log(2.), np.log(.03)])
    if harmonic:
        lo, hi = np.r_[lo, np.log(.00015)], np.r_[hi, np.log(1.)]
    runs = []
    solutions = []
    for start in range(experiment['starts']):
        initial = [47.65, (45, 100, 15)[start], np.log((.0015, .0005, .004)[start]),
                   (10, 15, 0)[start], np.log(.04), np.log(.001), np.log(tau), np.log(.001)]
        if harmonic:
            initial.append(np.log(.008))
        calls = 0
        def residual(parameters):
            nonlocal calls
            calls += 1
            matrix = columns(parameters, seconds, harmonic) * weights[:, None]
            linear = np.linalg.lstsq(matrix, target, rcond=None)[0]
            return matrix @ linear - target
        started = time.monotonic()
        solution = least_squares(residual, initial, bounds=(lo, hi), x_scale='jac',
                                 max_nfev=experiment['max_nfev'], ftol=1e-10, xtol=1e-10, gtol=1e-10)
        matrix = columns(solution.x, seconds, harmonic) * weights[:, None]
        linear = np.linalg.lstsq(matrix, target, rcond=None)[0]
        runs.append(dict(start=start, converged=bool(solution.success), status=int(solution.status),
            message=solution.message, objective=float(2 * solution.cost), nfev=int(solution.nfev),
            njev=int(solution.njev), residual_calls=calls, optimality=float(solution.optimality),
            active_bounds=solution.active_mask.tolist(),
            seconds=time.monotonic() - started, weighted_matrix_condition=float(np.linalg.cond(matrix)),
            maximum_linear_coefficient_fs=float(np.max(abs(linear)))))
        solutions.append((solution.x, linear))
    selected = min(range(len(runs)), key=lambda i: runs[i]['objective'])
    nonlinear, linear = solutions[selected]
    prediction = columns(nonlinear, np.arange(fit808.FRAMES) / fit808.RATE, harmonic) @ linear
    viable = (runs[selected]['converged'] and runs[selected]['weighted_matrix_condition'] <= 1e8
              and runs[selected]['maximum_linear_coefficient_fs'] <= .25)
    return prediction, dict(nonlinear=nonlinear.tolist(), linear=linear.tolist(), selected_start=selected,
                             nonlinear_bounds=dict(lower=lo.tolist(), upper=hi.tolist()),
                             numerically_viable=viable, runs=runs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=fit808.CORPUS)
    parser.add_argument('--output', type=Path, default=fit808.ROOT / 'out/808-model/capacity')
    parser.add_argument('--candidate', choices=('fundamental', 'harmonic'), default='fundamental')
    args = parser.parse_args()
    if (args.output.resolve().is_relative_to(args.corpus.resolve()) or
            args.output.resolve().is_relative_to(fit808.FIXTURES.resolve())):
        parser.error('Write experiments outside the immutable corpus and protocol fixtures')
    config, events = fit808.protocol()
    hashes = fit808.verify_artifacts(args.corpus, config, events)
    experiment_path = fit808.FIXTURES / 'capacity.json'
    experiment = json.loads(experiment_path.read_text())
    chosen = []
    for pair in experiment['pairs']:
        event = next((e for e in events if [e['tone_cc'], e['decay_cc']] == pair), None)
        if event is None or event['partition'] != 'train':
            raise ValueError('Capacity settings must belong to the fitting partition')
        chosen.append(event)
    import numpy as np
    import scipy
    import soundfile as sf
    if scipy.__version__ != experiment['scipy']:
        raise ValueError('Use the pinned SciPy version through mise')
    output = args.output / args.candidate
    output.mkdir(parents=True, exist_ok=True)
    harmonic = args.candidate == 'harmonic'
    report = dict(candidate=args.candidate, scope='Fitting-only per-setting capacity diagnostic; no generalization claim.',
        source_sha256=hashes['808-corpus.wav'], driver_sha256=fit808.digest(Path(__file__)),
        benchmark_driver_sha256=fit808.digest(Path(fit808.__file__)), artifacts_verified=len(hashes),
        protocol_sha256=fit808.digest(fit808.FIXTURES / 'protocol.json'),
        subset_sha256=fit808.digest(experiment_path), environment=dict(python=platform.python_version(),
            numpy=np.__version__, scipy=scipy.__version__, soundfile=sf.__version__),
        objective='Quadrature of whole relative squared error plus 0.25 times each active short-window relative squared error. Raw target samples are unchanged.',
        resources=dict(estimate_only=True, nonlinear_parameters=9 if harmonic else 8,
            linear_parameters=7 if harmonic else 5, mutable_float_states=8 if harmonic else 7,
            estimated_voice_bytes_including_16_common_bytes=112 if harmonic else 96,
            host_transcendentals_per_sample=dict(exp_or_expm1=6 if harmonic else 5, sin_or_cos=4 if harmonic else 2),
            global_control_table_bytes=None, port_instruction_cost=None,
            notes='Closed-form host sin/exp are not sample-loop implementations. Recurrence/approximation, global table size, numerical formats and actual target costs remain unproved.'),
        records=[])
    with sf.SoundFile(args.corpus / '808-corpus.wav') as wav:
        for event in chosen:
            reference = fit808.read_slot(wav, event)
            prediction, fit = fit_one(reference, config, experiment, harmonic)
            name = f"t{event['tone_cc']:03}-d{event['decay_cc']:03}"
            row = dict(index=event['index'], tone_cc=event['tone_cc'], decay_cc=event['decay_cc'],
                       fit=fit, **fit808.measure(prediction, reference, config))
            report['records'].append(row)
            report['summary'] = fit808.summarize(report['records'], config)
            report['complete'] = len(report['records']) == len(chosen)
            report['capacity_passes'] = report['complete'] and all(r['fit']['numerically_viable'] for r in report['records']) and all(
                report['summary'][k]['passes_gates'] for k in ('all', 'interaction'))
            sf.write(output / (name + '-prediction.wav'), prediction, fit808.RATE, subtype='FLOAT')
            sf.write(output / (name + '-residual.wav'), prediction - reference, fit808.RATE, subtype='FLOAT')
            (output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
            print(name, f"L2={100 * row['relative_l2']:.4f}%", 'converged=' + str(fit['runs'][fit['selected_start']]['converged']), flush=True)
    print('Capacity passes:', report['capacity_passes'], output / 'report.json', flush=True)


if __name__ == '__main__':
    main()
