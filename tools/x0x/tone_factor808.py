"""Test a shared Tone filter using recorded Tone-127 inputs, not a kick generator."""
import argparse
import json
from pathlib import Path

from . import diagnose808, fit808

OUT = fit808.ROOT / 'out/808-model/tone-factor'


def poles(parameters, coordinates):
    import numpy as np
    p, t = np.asarray(parameters, dtype=float), np.asarray(coordinates, dtype=float)
    if (p.shape != (5,) or not np.isfinite(p).all() or p[0] <= 1 / (2 * fit808.RATE) or
            np.any(p[1:3] < 0) or np.any(p[3:] <= 0) or
            not np.isfinite(t).all() or np.any((t < 0) | (t > 1))):
        raise ValueError('Positive stable Tone parameters and coordinates in 0..1 are required')
    x = t ** p[4]
    tau = p[0] + p[1] * (1 - x) + p[2] * (1 - x) / (x + p[3])
    half_step = 1 / (2 * fit808.RATE)
    return (tau - half_step) / (tau + half_step)


def transfer(samples, parameters, tone_raw):
    """Fresh-state relative filter: H(Tone)/H(127), both with unity DC gain."""
    import numpy as np
    from scipy.signal import lfilter
    samples = np.asarray(samples, dtype=float)
    if samples.ndim != 1 or not np.isfinite(samples).all():
        raise ValueError('Expected finite mono input samples')
    pole = float(poles(parameters, fit808.native_coordinate(tone_raw)))
    zero = float(poles(parameters, 1.))
    gain = (1 - pole) / (1 - zero)
    return lfilter([gain, -gain * zero], [1., -pole], samples)


def fit_parameters(source, targets, tones):
    import numpy as np
    from scipy.optimize import least_squares
    source, targets = np.asarray(source), np.asarray(targets)
    if (source.ndim != 1 or targets.shape != (len(tones), len(source)) or
            not np.isfinite(source).all() or not np.isfinite(targets).all()):
        raise ValueError('Matching finite source and target waveforms are required')
    norms = np.linalg.norm(targets, axis=1)
    if np.any(norms == 0):
        raise ValueError('Silent targets cannot define relative fitting losses')
    def decode(value):
        return np.r_[np.exp(value[:4]), value[4]]
    def residual(value):
        parameters = decode(value)
        return np.concatenate([(transfer(source, parameters, t * 256) - y) / norm
                               for t, y, norm in zip(tones, targets, norms)])
    result = least_squares(residual, [*np.log([17e-6, 200e-6, 40e-6, .14]), .5],
        bounds=([*np.log([11e-6, 1e-7, 1e-8, .001]), .25],
                [*np.log([.001, .01, .01, 10.]), 2.]),
        x_scale='jac', max_nfev=100, ftol=1e-10, xtol=1e-10, gtol=1e-10)
    return decode(result.x), dict(converged=bool(result.success), status=int(result.status),
        message=result.message, nfev=int(result.nfev), objective=float(2 * result.cost),
        optimality=float(result.optimality), active_bounds=result.active_mask.tolist())


def make_plots(output, parameters, rows, references, predictions):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout='constrained')
    tones = list(range(128))
    axes[0].plot(tones, poles(parameters, [fit808.native_coordinate(t * 256) for t in tones]))
    axes[0].set(xlabel='Tone CC', ylabel='Stable filter pole', title='One shared Tone law')
    for decay in sorted({r['decay_cc'] for r in rows}):
        selected = sorted((r for r in rows if r['decay_cc'] == decay), key=lambda r: r['tone_cc'])
        axes[1].plot([r['tone_cc'] for r in selected], [100 * r['relative_l2'] for r in selected], '.-', label=str(decay))
    axes[1].set(xlabel='Tone CC', ylabel='Whole-waveform error (%)', title='Recorded-input Tone stage, by Decay')
    axes[1].legend(title='Decay', ncol=3, fontsize=8)
    for ax in axes:
        ax.grid(alpha=.2)
    fig.savefig(output / 'tone-law.png', dpi=140)
    plt.close(fig)
    fig, axes = plt.subplots(4, 2, figsize=(12, 10), layout='constrained')
    for row, pair in enumerate(((0, 0), (0, 127), (119, 0), (119, 127))):
        ref, pred = references[pair], predictions[pair]
        ms = np.arange(2400) / 48
        axes[row, 0].plot(ms, ref[:2400], color='black', label='Recorded target')
        axes[row, 0].plot(ms, pred[:2400], '--', color='#00838c', label='Filtered recorded input')
        axes[row, 0].set_ylabel(f'Tone {pair[0]}, Decay {pair[1]}\nCapture FS')
        axes[row, 1].plot(ms, (pred - ref)[:2400], color='#00838c')
        for ax in axes[row]:
            ax.set_xlabel('Time (ms)')
            ax.grid(alpha=.2)
    axes[0, 0].legend(fontsize=8)
    axes[0, 1].set_title('Residual; independent vertical scale')
    fig.suptitle('Conditional Tone-stage test — not a synthesized kick')
    fig.savefig(output / 'corners.png', dpi=140)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=fit808.CORPUS)
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    if (args.output.resolve().is_relative_to(args.corpus.resolve()) or
            args.output.resolve().is_relative_to(fit808.FIXTURES.resolve())):
        parser.error('Write experiments outside the immutable corpus and protocol fixtures')
    config, events = fit808.protocol()
    hashes = fit808.verify_artifacts(args.corpus, config, events)
    first = {}
    for event in events:
        first.setdefault((event['tone_cc'], event['decay_cc']), event)
    training = [e for (tone, decay), e in sorted(first.items())
                if e['partition'] == 'train' and decay == 0 and tone != 127]
    import numpy as np
    import scipy
    import soundfile as sf
    if scipy.__version__ != '1.18.0' or len(training) != 64:
        raise ValueError('Use the pinned runtime and original fitting partition')
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    fit_frames = 12000
    with sf.SoundFile(args.corpus / '808-corpus.wav') as wav:
        source = fit808.read_slot(wav, first[127, 0])
        targets = np.array([fit808.read_slot(wav, e)[:fit_frames] for e in training])
        parameters64, optimizer = fit_parameters(source[:fit_frames], targets, [e['tone_cc'] for e in training])
        parameters = parameters64.astype('float32')
        report = dict(scope='Conditional Tone-stage test using measured Tone-127 inputs; not a kick generator or full-model generalization result.',
            parameters=parameters.tolist(), optimizer=optimizer, fitting_settings=64, fit_frames=fit_frames,
            parameters_order=['minimum_tau_s', 'linear_tau_s', 'rational_tau_s', 'rational_offset', 'control_exponent'],
            artifacts_verified=len(hashes), source_sha256=hashes['808-corpus.wav'],
            driver_sha256=fit808.digest(Path(__file__)), benchmark_driver_sha256=fit808.digest(Path(fit808.__file__)),
            protocol_sha256=fit808.digest(fit808.FIXTURES / 'protocol.json'),
            listening_helper_sha256=fit808.digest(Path(diagnose808.__file__)),
            listening_template_sha256=fit808.digest(Path(diagnose808.__file__).with_suffix('.html')),
            environment=dict(numpy=np.__version__, scipy=scipy.__version__, soundfile=sf.__version__),
            resources=dict(encoded_parameter_bytes=parameters.nbytes, relative_filter_states_direct_form_i=2,
                relative_filter_states_transposed=1,
                direct_filter_states=1, target_instructions_or_cycles=None), records=[], identity_checks=[],
            perceptual_acceptance='untested', maximum_float32_encoding_difference_fs=0.)
        references, predictions = {}, {}
        for pair, event in sorted(first.items()):
            canonical = first.get((127, event['decay_cc']))
            if event['partition'] != 'train' or canonical is None or canonical['partition'] != 'train':
                continue
            source = fit808.read_slot(wav, canonical)
            reference = fit808.read_slot(wav, event)
            prediction = transfer(source, parameters, event['tone_cc'] * 256)
            ideal = transfer(source, parameters64, event['tone_cc'] * 256)
            report['maximum_float32_encoding_difference_fs'] = max(report['maximum_float32_encoding_difference_fs'],
                                                                  float(np.max(abs(prediction - ideal))))
            row = dict(index=event['index'], tone_cc=pair[0], decay_cc=pair[1], **fit808.measure(prediction, reference, config))
            if pair[0] == 127:
                report['identity_checks'].append(row)
            else:
                report['records'].append(row)
            references[pair], predictions[pair] = reference, prediction
    if len(report['records']) != 128 or len(report['identity_checks']) != 9:
        raise ValueError('Unexpected paired training coverage')
    cross_decay = [row for row in report['records'] if row['decay_cc'] != 0]
    report['summary'] = fit808.summarize(report['records'], config)
    report['cross_decay_summary'] = fit808.summarize(cross_decay, config)
    report['cross_decay_settings'] = len(cross_decay)
    grid = np.array([fit808.native_coordinate(raw) for raw in range(32513)])
    pole_grid = poles(parameters, grid)
    report['native_control_sanity'] = dict(minimum_pole=float(pole_grid.min()), maximum_pole=float(pole_grid.max()),
        monotone=bool(np.all(np.diff(pole_grid) <= 0)), finite=bool(np.isfinite(pole_grid).all()))
    np.savez(output / 'model.npz', parameters=parameters, metadata=json.dumps({k: v for k, v in report.items() if k not in ('records', 'identity_checks')}))
    listening = [first[tone, decay] for tone in (0, 17, 68, 119) for decay in (0, 17, 68, 127)]
    manifest = {k: v for k, v in report.items() if k.endswith('_sha256')}
    manifest['scope'] = 'Tone-stage test only: the input is a recorded Tone-127 kick, not a synthesized oscillator.'
    manifest['cohort_note'] = 'The curve was fitted at Decay zero. Other Decay settings here test the filter using recorded inputs, not full-generator generalization.'
    report['listening_gain'] = diagnose808.listening_report(output, listening, references, predictions, manifest)
    make_plots(output, parameters, report['records'], references, predictions)
    (output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print('Tone filter converged:', optimizer['converged'], 'parameter bytes:', parameters.nbytes, flush=True)
    for label, summary in [('all 128 nonidentity pairs', report['summary']), ('64 new-Decay pairs', report['cross_decay_summary'])]:
        print(label, {k + '_percent': 100 * v for k, v in summary['all']['relative_l2'].items()}, flush=True)
    print('Component-only listening report:', output / 'index.html', flush=True)


if __name__ == '__main__':
    main()
