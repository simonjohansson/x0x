"""Controlled fitting diagnosis and blind listening material for #84."""
import argparse
import base64
import io
import json
from pathlib import Path
import platform
import time

from . import capacity808, fit808

CORNERS = [(0, 0), (0, 127), (127, 0), (127, 127)]
OUT = fit808.ROOT / 'out/808-model/diagnosis'


def columns(parameters, seconds, extra_dc=False):
    import numpy as np
    matrix = capacity808.columns(parameters[:9], seconds, True)
    if extra_dc:
        # Ordered real decay modes avoid exchanging the two output time constants.
        tau = np.exp(parameters[7]) + np.exp(parameters[9])
        matrix = np.column_stack((matrix, np.exp(-seconds / tau)))
        # Eliminate the first real-mode amplitude so every basis column starts at zero.
        keep = [0, 1, 2, 3, 5, 6, 7]
        matrix = matrix[:, keep] - matrix[:, 4, None] * np.array([0, 1, 0, 1, 0, 1, 1])
    return matrix


def amplitudes(linear, extra_dc):
    import numpy as np
    if not extra_dc:
        return linear
    return np.insert(linear, 4, -sum(linear[i] for i in (1, 3, 5, 6)))


def objective_weights(reference, config, full_rate=False):
    import numpy as np
    if not full_rate:
        return capacity808.sample_objective(reference, config)
    weight2 = np.ones(len(reference)) / float(reference @ reference)
    for name, (lo, hi) in config['windows'].items():
        if name in ('whole', 'tail500ms_to_end'):
            continue
        region = reference[lo:hi]
        energy = float(region @ region)
        if np.sqrt(energy / len(region)) >= config['gates']['active_reference_rms_fs']:
            weight2[lo:hi] += .25 / energy
    return np.arange(len(reference)), np.sqrt(weight2)


def cycle_features(reference):
    """Same-polarity peak periods are descriptive; they do not identify circuit poles."""
    import numpy as np
    from scipy.signal import find_peaks
    result = {}
    for sign, name in ((1, 'positive'), (-1, 'negative')):
        peaks, _ = find_peaks(sign * reference, height=.0001, distance=300)
        peaks = peaks[(peaks > 336) & (peaks < 14400)]
        result[name] = dict(peak_seconds=(peaks / fit808.RATE).tolist(),
            peak_magnitude_fs=(sign * reference[peaks]).tolist(),
            frequency_seconds=((peaks[1:] + peaks[:-1]) / (2 * fit808.RATE)).tolist(),
            frequency_hz=(fit808.RATE / np.diff(peaks)).tolist())
    return result


def measured_seed(reference, old_parameters):
    import numpy as np
    features = cycle_features(reference)['positive']
    mid, frequency = np.array(features['frequency_seconds']), np.array(features['frequency_hz'])
    keep = (frequency > 48) & (mid < .12)
    bend, tau = 15., .04
    if np.count_nonzero(keep) >= 2:
        slope, intercept = np.polyfit(mid[keep], np.log(frequency[keep] - 47.65), 1)
        if slope < 0:
            tau, bend = float(np.clip(-1 / slope, .002, .2)), float(np.clip(np.exp(intercept), 0, 150))
    energy = np.cumsum(reference * reference)
    decay = np.clip(np.searchsorted(energy, .99 * energy[-1]) / fit808.RATE / 2.3026, .004, 1.)
    seeds = [np.array(old_parameters)]
    for fast_bend, fast_tau in ((0, .0005), (100, .001), (300, .003)):
        seeds.append(np.array([47.65, fast_bend, np.log(fast_tau), bend, np.log(tau),
                              np.log(.001), np.log(decay), np.log(.08), np.log(.03)]))
    return seeds, dict(bend_hz=bend, pitch_tau_seconds=tau, settled_seed_hz=47.65)


def solve(reference, config, seeds, lower, upper, extra_dc=False, full_rate=False, max_nfev=800):
    import numpy as np
    from scipy.optimize import least_squares
    indices, weight = objective_weights(reference, config, full_rate)
    seconds = indices / fit808.RATE
    target = reference[indices] * weight
    runs = []
    for start, seed in enumerate(seeds):
        initial = np.clip(seed, lower + 1e-8, upper - 1e-8)
        calls = 0
        def residual(parameters):
            nonlocal calls
            calls += 1
            matrix = columns(parameters, seconds, extra_dc) * weight[:, None]
            linear = np.linalg.lstsq(matrix, target, rcond=None)[0]
            return matrix @ linear - target
        began = time.monotonic()
        fit = least_squares(residual, initial, bounds=(lower, upper), x_scale='jac', max_nfev=max_nfev,
                            ftol=1e-10, xtol=1e-10, gtol=1e-10)
        matrix = columns(fit.x, seconds, extra_dc) * weight[:, None]
        linear = np.linalg.lstsq(matrix, target, rcond=None)[0]
        condition, peak = float(np.linalg.cond(matrix)), float(np.max(abs(amplitudes(linear, extra_dc))))
        runs.append(dict(start=start, initial=initial.tolist(), nonlinear=fit.x.tolist(), linear=linear.tolist(),
            objective=float(2 * fit.cost), converged=bool(fit.success), status=int(fit.status), message=fit.message,
            nfev=int(fit.nfev), njev=int(fit.njev), residual_calls=calls, optimality=float(fit.optimality),
            active_bounds=fit.active_mask.tolist(), condition=condition, maximum_coefficient_fs=peak,
            expanded_amplitudes=amplitudes(linear, extra_dc).tolist(),
            numerically_viable=bool(fit.success and condition <= 1e8 and peak <= .25),
            seconds=time.monotonic() - began))
    eligible = [i for i, run in enumerate(runs) if run['numerically_viable']] or list(range(len(runs)))
    selected = min(eligible, key=lambda i: runs[i]['objective'])
    best = runs[selected]
    prediction = columns(best['nonlinear'], np.arange(fit808.FRAMES) / fit808.RATE, extra_dc) @ best['linear']
    full_indices, full_weight = objective_weights(reference, config, True)
    full_objective = float(np.sum(((prediction - reference)[full_indices] * full_weight) ** 2))
    return prediction, dict(selected_start=selected, runs=runs, full_objective=full_objective,
        quadrature_relative_difference=None if full_rate else best['objective'] / full_objective - 1,
        bounds=dict(lower=lower.tolist(), upper=upper.tolist()), full_rate=full_rate,
        numerically_viable=best['numerically_viable'])


def fitted_row(event, prediction, reference, config, fit):
    return dict(index=event['index'], tone_cc=event['tone_cc'], decay_cc=event['decay_cc'], fit=fit,
                **fit808.measure(prediction, reference, config))


def polish(reference, config, prediction, fit, extra_dc):
    import numpy as np
    selected = fit['runs'][fit['selected_start']]
    refined, evidence = solve(reference, config, [selected['nonlinear']], np.array(fit['bounds']['lower']),
        np.array(fit['bounds']['upper']), extra_dc, full_rate=True, max_nfev=60)
    use = evidence['numerically_viable'] and evidence['full_objective'] < fit['full_objective']
    if use:
        evidence['quadrature_fit'] = fit
        evidence['polish_adopted'] = True
        return refined, evidence
    fit['full_rate_polish'] = dict(adopted=False, evidence=evidence)
    return prediction, fit


def make_plots(output, references, predictions, features):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(4, 4, figsize=(18, 12), layout='constrained')
    for row, pair in enumerate(CORNERS):
        reference, prediction = references[pair], predictions[pair]
        ms = np.arange(fit808.FRAMES) / 48
        axes[row, 0].plot(ms[:2400], reference[:2400], color='black', label='Recorded')
        axes[row, 0].plot(ms[:2400], prediction[:2400], color='#00838c', alpha=.85, label='Candidate')
        axes[row, 1].plot(ms[:24000], (prediction - reference)[:24000], color='#00838c')
        for name, color in (('positive', '#3775a9'), ('negative', '#bd4c4c')):
            data = features[pair][name]
            candidate = cycle_features(prediction)[name]
            axes[row, 2].plot(np.array(data['frequency_seconds']) * 1000, data['frequency_hz'], '.-', color=color, label=name + ' recorded')
            axes[row, 2].plot(np.array(candidate['frequency_seconds']) * 1000, candidate['frequency_hz'], '--', color=color, label=name + ' candidate')
            axes[row, 3].plot(np.array(data['peak_seconds']) * 1000, data['peak_magnitude_fs'], '.-', color=color, label=name + ' recorded')
            axes[row, 3].plot(np.array(candidate['peak_seconds']) * 1000, candidate['peak_magnitude_fs'], '--', color=color, label=name + ' candidate')
        axes[row, 0].set_ylabel(f'Tone {pair[0]}, Decay {pair[1]}\nCapture FS')
        axes[row, 2].set_ylim(35, 85)
        for ax in axes[row]:
            ax.grid(alpha=.2)
            ax.set_xlabel('Time (ms)')
    for ax, title in zip(axes[0], ('Waveform, first 50 ms', 'Residual, first 500 ms',
                                  'Cycle frequency (diagnostic)', 'Peak magnitudes (diagnostic)')):
        ax.set_title(title)
    for ax in (axes[0, 0], axes[0, 2], axes[0, 3]):
        ax.legend(fontsize=8)
    fig.suptitle('808 corner diagnosis — two output decays with zero-start constraint', fontsize=18)
    fig.savefig(output / 'corners.png', dpi=140)
    plt.close(fig)


def listening_report(output, events, references, predictions, manifest):
    import numpy as np
    import soundfile as sf
    peak = max(float(np.max(abs(y))) for y in [*references.values(), *predictions.values()])
    gain = min(4., .95 / peak)
    stimuli = []
    for event in events:
        pair = event['tone_cc'], event['decay_cc']
        data = dict(tone=pair[0], decay=pair[1])
        for name, samples in (('recorded', references[pair]), ('candidate', predictions[pair])):
            stream = io.BytesIO()
            # Native media playback needs no Web Audio gain node or float-WAV decoder.
            sf.write(stream, samples * gain, fit808.RATE, format='WAV', subtype='PCM_24')
            data[name] = base64.b64encode(stream.getvalue()).decode('ascii')
            filename = f't{pair[0]:03}-d{pair[1]:03}-{name}-playback.wav'
            (output / filename).write_bytes(stream.getvalue())
            data[name + '_download'] = filename
        stimuli.append(data)
    payload = json.dumps(dict(stimuli=stimuli, gain=gain, gain_applied=True,
                             playback_encoding='PCM_24', manifest=manifest), allow_nan=False).replace('<', '\\u003c')
    template = Path(__file__).with_suffix('.html').read_text()
    (output / 'index.html').write_text(template.replace('__LISTENING_DATA__', payload))
    return gain


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=fit808.CORPUS)
    parser.add_argument('--baseline', type=Path, default=fit808.ROOT / 'out/808-model/capacity/harmonic/report.json')
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    if (args.output.resolve().is_relative_to(args.corpus.resolve()) or
            args.output.resolve().is_relative_to(fit808.FIXTURES.resolve())):
        parser.error('Write diagnosis outside the immutable corpus and protocol fixtures')
    config, events = fit808.protocol()
    hashes = fit808.verify_artifacts(args.corpus, config, events)
    baseline = json.loads(args.baseline.read_text())
    if (not baseline['complete'] or baseline['source_sha256'] != hashes['808-corpus.wav'] or
            baseline['driver_sha256'] != fit808.digest(Path(capacity808.__file__)) or
            baseline['benchmark_driver_sha256'] != fit808.digest(Path(fit808.__file__))):
        raise ValueError('Regenerate the matching baseline with mise run research:808:capacity')
    subset = json.loads((fit808.FIXTURES / 'capacity.json').read_text())
    chosen = [next(e for e in events if [e['tone_cc'], e['decay_cc']] == pair) for pair in subset['pairs']]
    if len(chosen) != 16 or any(e['partition'] != 'train' for e in chosen):
        raise ValueError('Use the unchanged 16-setting fitting subset')
    import numpy as np
    import scipy
    import soundfile as sf
    if scipy.__version__ != subset['scipy']:
        raise ValueError('Use the pinned SciPy runtime through mise')
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    report = dict(scope='Fitting-only host diagnosis. No generalization, audible-equivalence or DSP qualification claim.',
        acceptance_policy='User prioritizes audible fidelity. Original numerical gates are reported diagnostics; listening acceptance is pending.',
        perceptual_acceptance='untested', artifacts_verified=len(hashes), baseline_sha256=fit808.digest(args.baseline),
        source_sha256=hashes['808-corpus.wav'], driver_sha256=fit808.digest(Path(__file__)),
        benchmark_driver_sha256=fit808.digest(Path(fit808.__file__)),
        original_model_driver_sha256=fit808.digest(Path(capacity808.__file__)),
        listening_template_sha256=fit808.digest(Path(__file__).with_suffix('.html')),
        protocol_sha256=fit808.digest(fit808.FIXTURES / 'protocol.json'),
        subset_sha256=fit808.digest(fit808.FIXTURES / 'capacity.json'),
        environment=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__, soundfile=sf.__version__),
        model='Harmonic carrier, two real output decays, zero-start constraint',
        resources=dict(estimate_only=True, nonlinear_parameters=10, linear_parameters=7, expanded_amplitudes=8, mutable_float_states=9,
            estimated_voice_bytes_including_16_common_bytes=124, extra_recurrence_cost='One real decay: one multiply/add per sample',
            global_table_bytes=None, prospective_map_bytes=[408, 1088],
            map_assumption='17 free parameter functions with 6–16 float32 coefficients each; metadata excluded; required complexity untested',
            target_instruction_cost=None),
        restart_records=[], output_decay_records=[])
    references, predictions, features = {}, {}, {}
    with sf.SoundFile(args.corpus / '808-corpus.wav') as wav:
        for event in chosen:
            pair = event['tone_cc'], event['decay_cc']
            reference = fit808.read_slot(wav, event)
            old = next(r for r in baseline['records'] if (r['tone_cc'], r['decay_cc']) == pair)
            lower, upper = (np.array(old['fit']['nonlinear_bounds'][k]) for k in ('lower', 'upper'))
            seeds, initialization = measured_seed(reference, old['fit']['nonlinear'])
            # The old 30 ms output-decay ceiling was active on a long-Decay corner.
            upper[7] = np.log(1.)
            restart, control = solve(reference, config, seeds, lower, upper)
            control['measured_initialization'] = initialization
            if pair in CORNERS:
                print(pair, 'full-rate control polish', flush=True)
                restart, control = polish(reference, config, restart, control, False)
            report['restart_records'].append(fitted_row(event, restart, reference, config, control))
            seed = np.array(control['runs'][control['selected_start']]['nonlinear'])
            dc_seeds = [np.r_[seed, np.log(max(.005, tau - np.exp(seed[7])))] for tau in (.04, .1, .4)]
            prediction, fitted = solve(reference, config, dc_seeds, np.r_[lower, np.log(.005)],
                                        np.r_[upper, np.log(2.)], extra_dc=True)
            if pair in CORNERS:
                print(pair, 'full-rate output-decay polish', flush=True)
                prediction, fitted = polish(reference, config, prediction, fitted, True)
            report['output_decay_records'].append(fitted_row(event, prediction, reference, config, fitted))
            report['complete'] = len(report['output_decay_records']) == len(chosen)
            report['restart_summary'] = fit808.summarize(report['restart_records'], config)
            report['output_decay_summary'] = fit808.summarize(report['output_decay_records'], config)
            (output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
            references[pair], predictions[pair], features[pair] = reference, prediction, cycle_features(reference)
            name = f't{pair[0]:03}-d{pair[1]:03}'
            sf.write(output / (name + '-prediction.wav'), prediction, fit808.RATE, subtype='FLOAT')
            sf.write(output / (name + '-residual.wav'), prediction - reference, fit808.RATE, subtype='FLOAT')
            print(name, f"restart L2={100 * report['restart_records'][-1]['relative_l2']:.4f}%",
                  f"output-decay L2={100 * report['output_decay_records'][-1]['relative_l2']:.4f}%", flush=True)
    make_plots(output, references, predictions, features)
    manifest = {k: v for k, v in report.items() if k.endswith('_sha256')}
    report['listening_gain'] = listening_report(output, chosen, references, predictions, manifest)
    report['corner_features'] = {str(pair): features[pair] for pair in CORNERS}
    (output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print('Listening remains untested:', output / 'index.html', flush=True)


if __name__ == '__main__':
    main()
