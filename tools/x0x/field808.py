"""Fitter and host reference for the quantized 808 body field and Tone filter."""
import argparse
import json
from pathlib import Path

from . import listening808, fit808, tone_factor808

RANK = 8
OUT = fit808.ROOT / 'out/808-model/field'


def geometry():
    import numpy as np
    groups = [[.020, .025, .032, .040, .050, .065, .085, .110, .150, .200, .280,
               .400, .600, .900, 1.4, 2.2, 3.5, 5.5],
              [.020, .030, .050, .080, .120, .200, .350, .600, 1., 1.7, 3., 5.5],
              [.020, .050, .100, .200, .400, .800, 1.6, 3.2, 5.5],
              [.020, .080, .200, .500, 1., 2., 5.5]]
    return dict(raw_segments=np.array([[0, 96, 1], [104, 384, 8], [400, 1440, 16]], dtype='uint16'),
                envelope_knots=np.array(sum(groups, []), dtype='float32'),
                envelope_offsets=np.array([0, 18, 30, 39, 46], dtype='uint8'),
                carrier_hz=np.array([47.65], dtype='float32'),
                control_breaks=np.array([17], dtype='uint16'))


def spline(seconds, breaks):
    import numpy as np
    from scipy.interpolate import BSpline
    t, k = np.asarray(seconds), np.asarray(breaks, dtype=float)
    if (t.ndim != 1 or not np.isfinite(t).all() or k.ndim != 1 or len(k) < 2 or
            not np.isfinite(k).all() or np.any(np.diff(k) <= 0)):
        raise ValueError('Finite times and strictly increasing spline breaks are required')
    knots = np.r_[np.repeat(k[0], 4), k[1:-1], np.repeat(k[-1], 4)]
    return BSpline.design_matrix(np.clip(t, k[0], k[-1]), knots, 3).toarray()


def dictionary(model, seconds):
    import numpy as np
    t = np.asarray(seconds, dtype=float)
    if t.ndim != 1 or not np.isfinite(t).all() or np.any((t < 0) | (t > 5.5)):
        raise ValueError('The isolated-hit field covers finite times in 0..5.5 seconds')
    raw = np.concatenate([np.arange(a, b + 1, step) for a, b, step in model['raw_segments']]) / fit808.RATE
    fade = np.clip((t - .020) / .010, 0, 1)
    fade = fade * fade * (3 - 2 * fade)
    onset = spline(t, raw)[:, 1:] * ((1 - fade) * (t <= .030))[:, None]
    result = [onset]
    for h, start, end in zip((1, 2, 3, 0), model['envelope_offsets'][:-1], model['envelope_offsets'][1:]):
        envelope = spline(t, model['envelope_knots'][start:end]) * fade[:, None]
        if h:
            phase = 2 * np.pi * float(model['carrier_hz'][0]) * h * t
            result.extend([envelope * np.sin(phase)[:, None], envelope * np.cos(phase)[:, None]])
        else:
            result.append(envelope)
    return np.column_stack(result)


def encode_rows(values):
    import numpy as np
    x = np.asarray(values, dtype=float)
    if x.ndim != 2 or not np.isfinite(x).all():
        raise ValueError('Expected a finite coefficient matrix')
    scales = (np.max(abs(x), axis=1) / 32767).astype('float32')
    scales[scales == 0] = 1
    q = np.clip(np.rint(x / scales[:, None]), -32767, 32767).astype('int16')
    return q, scales


def decode_rows(model, name):
    import numpy as np
    q, scales = model[name], model[name + '_scale']
    if (q.dtype != np.dtype('int16') or q.ndim != 2 or scales.shape != (len(q),) or
            not np.isfinite(scales).all() or np.any(scales <= 0)):
        raise ValueError('Invalid quantized coefficient matrix: ' + name)
    return q.astype(float) * scales[:, None]


def put_rows(model, name, values):
    model[name], model[name + '_scale'] = encode_rows(values)


def body_basis(model):
    import numpy as np
    blocks = []
    for block in range(4):
        name = 'block' + str(block)
        values = decode_rows(model, name)
        if block < 2:
            values = decode_rows(model, name + '_mix').T @ values
        blocks.append(values)
    result = np.column_stack(blocks)
    if result.shape != (RANK, dictionary(model, [0.]).shape[1]):
        raise ValueError('Body table dimensions do not match the field geometry')
    return result


def control_weights(model, decay_raw):
    import numpy as np
    coordinate = fit808.native_coordinate(decay_raw)
    breaks = np.linspace(0, 1, int(model['control_breaks'][0]))
    return (spline([coordinate], breaks) @ decode_rows(model, 'control').T)[0]


def render(model, tone_raw, decay_raw, frames=fit808.FRAMES):
    import numpy as np
    if type(frames) is not int or not 1 <= frames <= fit808.FRAMES:
        raise ValueError('Expected 1..264000 frames for one fresh isolated hit')
    fit808.native_coordinate(tone_raw)
    coefficients = control_weights(model, decay_raw) @ body_basis(model)
    canonical = np.concatenate([dictionary(model, np.arange(i, min(i + 8192, frames)) / fit808.RATE) @ coefficients
                                for i in range(0, frames, 8192)])
    return tone_factor808.transfer(canonical, model['tone'], tone_raw)


def fit_body(targets, decays, config, model):
    """Compress in waveform energy, rather than in ill-conditioned coefficient units."""
    import numpy as np
    targets = np.asarray(targets)
    if (targets.shape != (len(decays), fit808.FRAMES) or not np.isfinite(targets).all() or
            len(set(decays)) != len(decays) or any(type(d) is not int for d in decays)):
        raise ValueError('Distinct integer Decay positions and complete finite targets are required')
    coordinates = [fit808.native_coordinate(d * 256) for d in decays]
    if np.any(np.linalg.norm(targets, axis=1) == 0):
        raise ValueError('Silent targets cannot define an equal-setting relative loss')
    indices, _ = fit808.sample_objective(np.ones(fit808.FRAMES), config)
    widths = np.diff(np.r_[indices, fit808.FRAMES])
    matrix = dictionary(model, indices / fit808.RATE)
    _, singular, vectors = np.linalg.svd(matrix * np.sqrt(widths)[:, None], full_matrices=False)
    retained = singular > singular[0] * 1e-9
    root = singular[retained, None] * vectors[retained]
    inverse = vectors[retained].T / singular[retained]
    coefficients, norms, solves = [], [], []
    for target in targets:
        _, weights = fit808.sample_objective(target, config)
        c, _, rank, spectrum = np.linalg.lstsq(matrix * weights[:, None], target[indices] * weights, rcond=1e-7)
        coefficients.append(c)
        norms.append(np.linalg.norm(target))
        solves.append(dict(retained_rank=int(rank), retained_condition=float(spectrum[0] / spectrum[rank - 1])))
    coefficients, norms = np.array(coefficients), np.array(norms)
    if np.any(norms == 0):
        raise ValueError('Silent targets cannot define an equal-setting relative loss')
    _, values, vectors = np.linalg.svd(coefficients @ root.T / norms[:, None], full_matrices=False)
    basis = vectors[:RANK] @ inverse.T
    weights = coefficients @ root.T @ vectors[:RANK].T
    # Waveform-weighted compression keeps the shared onset without cancellation-driven ranks.
    bounds = [0, 96, 136, 200, matrix.shape[1]]
    for block, (start, end, rank) in enumerate(zip(bounds[:-1], bounds[1:], (2, 4, RANK, RANK))):
        a = basis[:, start:end]
        if block < 2:
            _, s, v = np.linalg.svd(matrix[:, start:end] * np.sqrt(widths)[:, None], full_matrices=False)
            keep = s > s[0] * 1e-10
            block_root, block_inverse = s[keep, None] * v[keep], v[keep].T / s[keep]
            _, _, modes = np.linalg.svd((weights / norms[:, None]) @ a @ block_root.T, full_matrices=False)
            mix = a @ block_root.T @ modes[:rank].T
            a = modes[:rank] @ block_inverse.T
            put_rows(model, 'block' + str(block) + '_mix', mix.T)
        put_rows(model, 'block' + str(block), a)
    breaks = np.linspace(0, 1, int(model['control_breaks'][0]))
    mapping = np.linalg.lstsq(spline(coordinates, breaks), weights, rcond=None)[0].T
    put_rows(model, 'control', mapping)
    return dict(field_singular_values=values.tolist(), dictionary_columns=matrix.shape[1],
                dictionary_retained_rank=int(np.sum(retained)), dictionary_rcond=1e-9,
                per_setting_rcond=1e-7, per_setting_solves=solves,
                field_rank=RANK, onset_block_ranks=[2, 4], control_breaks=int(model['control_breaks'][0]))


def listening_subset(events):
    """Four fitting corners and twelve stratified validation settings, all distinct."""
    chosen = [next(e for e in events if (e['tone_cc'], e['decay_cc']) == pair) for pair in listening808.CORNERS]
    for tone in (0, 42, 85, 127):
        for decay in (8, 59, 119):
            candidates = [e for e in events if e['partition'] == 'validation' and e not in chosen]
            chosen.append(min(candidates, key=lambda e: ((e['tone_cc'] - tone) ** 2 + (e['decay_cc'] - decay) ** 2, e['index'])))
    if len({(e['tone_cc'], e['decay_cc']) for e in chosen}) != 16:
        raise ValueError('Listening settings must be distinct')
    return chosen


def make_plots(output, references, predictions, summaries):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(4, 2, figsize=(12, 10), layout='constrained')
    for row, pair in enumerate(listening808.CORNERS):
        ref, pred = references[pair], predictions[pair]
        axes[row, 0].plot(np.arange(2400) / 48, ref[:2400], color='black', label='Recorded')
        axes[row, 0].plot(np.arange(2400) / 48, pred[:2400], '--', color='#00838c', label='Quantized candidate')
        axes[row, 0].set(ylabel=f'Tone {pair[0]}, Decay {pair[1]}\nCapture FS', xlabel='Time (ms)')
        axes[row, 1].plot(np.arange(24000) / 48, (pred - ref)[:24000], color='#00838c')
        axes[row, 1].set(xlabel='Time (ms)', ylabel='Residual; separate vertical scale')
        for ax in axes[row]:
            ax.grid(alpha=.2)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle('Complete 808 candidate — shared spline/carrier body and Tone filter')
    fig.savefig(output / 'corners.png', dpi=140)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4), layout='constrained')
    for name, rows in summaries.items():
        pairs = {(r['tone_cc'], r['decay_cc']) for r in rows}
        values = np.sort([100 * np.mean([r['relative_l2'] for r in rows if (r['tone_cc'], r['decay_cc']) == pair]) for pair in pairs])
        ax.plot(values, np.linspace(0, 100, len(values)), label=name)
    ax.set(xlabel='Whole-waveform error (%)', ylabel='Settings (%)', title='Decoded quantized model, full 5.5-second slots')
    ax.legend()
    ax.grid(alpha=.2)
    fig.savefig(output / 'errors.png', dpi=140)
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
    import numpy as np
    import scipy
    import soundfile as sf
    from scipy.signal import lfilter
    if scipy.__version__ != '1.18.0':
        raise ValueError('Use the pinned SciPy runtime through mise')
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    model = geometry()
    with sf.SoundFile(args.corpus / '808-corpus.wav') as wav:
        axis = sorted((e for e in first.values() if e['partition'] == 'train' and e['decay_cc'] == 0 and e['tone_cc'] != 127), key=lambda e: e['tone_cc'])
        source = fit808.read_slot(wav, first[127, 0])
        targets = np.array([fit808.read_slot(wav, e)[:12000] for e in axis])
        tone, optimizer = tone_factor808.fit_parameters(source[:12000], targets, [e['tone_cc'] for e in axis])
        if not optimizer['converged'] or len(axis) != 64:
            raise ValueError('The shared Tone fit did not converge on the original training axis')
        model['tone'] = tone.astype('float32')
        decays = sorted(e['decay_cc'] for e in first.values() if e['partition'] == 'train' and e['tone_cc'] == 0)
        canonical, provenance = [], []
        p0, p127 = (float(tone_factor808.poles(model['tone'], value)) for value in (0., 1.))
        gain = (1 - p127) / (1 - p0)
        for decay in decays:
            event = first.get((127, decay))
            measured = event is not None and event['partition'] == 'train'
            event = event if measured else first[0, decay]
            target = fit808.read_slot(wav, event)
            if not measured:
                target = lfilter([gain, -gain * p0], [1., -p127], target)
            canonical.append(target)
            provenance.append(dict(decay_cc=decay, source_index=event['index'], recorded_tone127=measured))
        if len(decays) != 65 or sum(p['recorded_tone127'] for p in provenance) != 9:
            raise ValueError('Unexpected canonical-body training coverage')
        evidence = fit_body(canonical, decays, config, model)
    np.savez(output / 'model.npz', **model)
    # Every delivered stimulus is rendered from the saved integer tables and float32 scales.
    with np.load(output / 'model.npz', allow_pickle=False) as saved:
        model = {name: saved[name] for name in saved.files}
    basis = body_basis(model)
    dense = np.concatenate([dictionary(model, np.arange(i, min(i + 8192, fit808.FRAMES)) / fit808.RATE) @ basis.T
                            for i in range(0, fit808.FRAMES, 8192)])
    report = dict(scope='Complete quantized host 808 candidate; four fitting and twelve validation listening settings. Validation guided complexity selection; no fresh acceptance or target-DSP claim.',
        acceptance_policy='Audible fidelity takes priority; numerical source gates remain diagnostics.',
        perceptual_acceptance='untested', model='Eight-component spline/carrier body field followed by the shared Tone filter',
        source_sha256=hashes['808-corpus.wav'], artifacts_verified=len(hashes),
        driver_sha256=fit808.digest(Path(__file__)), benchmark_driver_sha256=fit808.digest(Path(fit808.__file__)),
        tone_driver_sha256=fit808.digest(Path(tone_factor808.__file__)),
        objective_driver_sha256=fit808.digest(Path(fit808.__file__)),
        listening_driver_sha256=fit808.digest(Path(listening808.__file__)),
        listening_template_sha256=fit808.digest(Path(listening808.__file__).with_suffix('.html')),
        protocol_sha256=fit808.digest(fit808.FIXTURES / 'protocol.json'), model_sha256=fit808.digest(output / 'model.npz'),
        environment=dict(numpy=np.__version__, scipy=scipy.__version__, soundfile=sf.__version__),
        fitting=dict(tone_optimizer=optimizer, canonical_provenance=provenance, **evidence),
        resources=dict(array_payload_bytes=sum(a.nbytes for a in model.values()),
            arrays={k: dict(shape=list(a.shape), dtype=str(a.dtype), bytes=a.nbytes) for k, a in model.items()},
            note='Payload only; metadata, code, mutable state, alignment and initialized-data packaging require a new linked budget. Use the normal linked build receipt for target resource limits.',
            target_instruction_cost=None, target_mutable_state_bytes=None, combined_budget_qualified=False),
        records=dict(train=[], validation=[]))
    references, predictions = {}, {}
    chosen = listening_subset(list(first.values()))
    with sf.SoundFile(args.corpus / '808-corpus.wav') as wav:
        for event in events:
            if event['partition'] not in report['records']:
                continue
            pair = event['tone_cc'], event['decay_cc']
            reference = fit808.read_slot(wav, event)
            prediction = tone_factor808.transfer(dense @ control_weights(model, event['decay_cc'] * 256), model['tone'], event['tone_cc'] * 256)
            report['records'][event['partition']].append(dict(index=event['index'], tone_cc=pair[0], decay_cc=pair[1], **fit808.measure(prediction, reference, config)))
            if any(e['index'] == event['index'] for e in chosen):
                references[pair], predictions[pair] = reference, prediction
                # Independently exercise the scalar-control path used by callers.
                np.testing.assert_allclose(render(model, pair[0] * 256, pair[1] * 256), prediction, rtol=1e-9, atol=1e-11)
    report['summary'] = {key: fit808.summarize(rows, config) for key, rows in report['records'].items()}
    weights = spline([fit808.native_coordinate(raw) for raw in range(32513)],
                     np.linspace(0, 1, int(model['control_breaks'][0]))) @ decode_rows(model, 'control').T
    anchors = [0, 1, 12345, 32512]
    np.testing.assert_array_equal(weights[anchors], [control_weights(model, raw) for raw in anchors])
    poles = tone_factor808.poles(model['tone'], [fit808.native_coordinate(raw) for raw in range(32513)])
    report['native_control_sanity'] = dict(words=32513, finite_weights=bool(np.isfinite(weights).all()),
        maximum_weight=float(abs(weights).max()), maximum_adjacent_weight_change=float(abs(np.diff(weights, axis=0)).max()),
        stable_tone=bool(np.all((poles > 0) & (poles < 1))), exact_zero_start=bool(np.all(dense[0] == 0)))
    if not (report['native_control_sanity']['finite_weights'] and report['native_control_sanity']['stable_tone'] and report['native_control_sanity']['exact_zero_start']):
        raise ValueError('The candidate failed its continuous-control/initial-state sanity checks')
    report['listening_settings'] = [{k: e[k] for k in ('index', 'tone_cc', 'decay_cc', 'partition')} for e in chosen]
    manifest = {k: v for k, v in report.items() if k.endswith('_sha256')}
    manifest['scope'] = report['scope']
    manifest['cohort_note'] = 'Four fitting corners plus twelve stratified validation settings. Validation was used for complexity selection; this is a development listening test, not fresh independent acceptance.'
    report['listening_gain'] = listening808.listening_report(output, chosen, references, predictions, manifest)
    make_plots(output, references, predictions, report['records'])
    (output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    for name, summary in report['summary'].items():
        print(name, {key + '_percent': 100 * value for key, value in summary['all']['relative_l2'].items()}, flush=True)
    print('Array payload bytes:', report['resources']['array_payload_bytes'], flush=True)
    print('Complete candidate; listening remains untested:', output / 'index.html', flush=True)


if __name__ == '__main__':
    main()
