"""Fixture-specific comparisons; tolerances are supplied, never inferred.

Required tolerance keys and units:
  onset_samples: absolute raw onset difference in samples;
  peak_fs, dc_fs, rms_fs: absolute normalized-amplitude differences;
  waveform_rms_fs, waveform_peak_fs: absolute sample residual amplitude;
  frequency_cents: maximum interpolated tonal-trajectory error;
  decay_relative: relative positive/negative fitted time-constant error;
  band_power_fs2: maximum absolute Hann band-power difference.

Statistical mode records waveform residuals without gating on them. Alignment
is supplemental: every acceptance gate uses the original, unshifted samples.
"""

import bisect
from collections.abc import Mapping
import math

from .analysis import analyze


TOLERANCE_KEYS = frozenset({
    'onset_samples', 'peak_fs', 'dc_fs', 'rms_fs', 'waveform_rms_fs',
    'waveform_peak_fs', 'frequency_cents', 'decay_relative', 'band_power_fs2',
})


def _tolerances(values):
    if not isinstance(values, Mapping) or set(values) != TOLERANCE_KEYS:
        raise ValueError('tolerances must contain exactly: ' + ', '.join(sorted(TOLERANCE_KEYS)))
    result = {}
    for key, value in values.items():
        if isinstance(value, (bool, str, bytes)):
            raise ValueError(f'{key} must be finite and nonnegative')
        try:
            value = float(value)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(f'{key} must be finite and nonnegative') from error
        if not math.isfinite(value) or value < 0:
            raise ValueError(f'{key} must be finite and nonnegative')
        result[key] = value
    return result


def _waveform(actual, expected):
    residual = [a - e for a, e in zip(actual, expected)]
    energy = math.fsum(x * x for x in residual)
    if not math.isfinite(energy):
        raise ValueError('residual exceeds the measurement range')
    rms = math.sqrt(energy / len(actual))
    reference_rms = math.sqrt(math.fsum(x * x for x in expected) / len(expected))
    return {'rms_fs': rms, 'peak_fs': max(abs(x) for x in residual),
            'relative_rms': _ratio(rms, reference_rms)}


def _ratio(actual, expected):
    value = actual / expected if expected else None
    return value if value is None or math.isfinite(value) else None


def _gate(error, limit, unavailable=None):
    return {'status': 'unavailable' if unavailable else ('passed' if error is not None and error <= limit else 'failed'),
            'error': error, 'limit': limit, 'reason': unavailable or ('actual estimate unavailable' if error is None else None)}


def _pitch_error(actual, expected):
    if expected['median_hz'] is None:
        return None, 0
    expected_cycles = [x for x in expected['cycles'] if x['valid']]
    actual_cycles = [x for x in actual['cycles'] if x['valid']]
    times = [(x['start_sample'] + x['end_sample']) / 2 for x in expected_cycles]
    errors = []
    for cycle in actual_cycles:
        time = (cycle['start_sample'] + cycle['end_sample']) / 2
        index = bisect.bisect_left(times, time)
        if index < len(times) and times[index] == time:
            reference = expected_cycles[index]['frequency_hz']
        elif 0 < index < len(times):
            fraction = (time - times[index - 1]) / (times[index] - times[index - 1])
            low, high = expected_cycles[index - 1]['frequency_hz'], expected_cycles[index]['frequency_hz']
            reference = low + fraction * (high - low)
        else:
            continue
        errors.append(abs(1200 * math.log2(cycle['frequency_hz'] / reference)))
    return (max(errors) if len(errors) >= 3 and actual['median_hz'] is not None else None), len(errors)


def compare_samples(actual, expected, sample_rate, tolerances, alignment_samples=0,
                    mode='deterministic'):
    """Compare equal-length mono signals with explicit fixture-specific limits.

    Positive alignment means actual is late: remove that many leading actual
    samples and trailing expected samples for the supplemental residual only.
    Neither raw timing nor any acceptance gate is modified by alignment.
    """
    limits = _tolerances(tolerances)
    if mode not in ('deterministic', 'statistical'):
        raise ValueError('mode must be deterministic or statistical')
    try:
        actual, expected = list(actual), list(expected)
    except TypeError as error:
        raise ValueError('signals must be finite mono sequences') from error
    if len(actual) != len(expected) or not actual:
        raise ValueError('signals must have the same nonzero sample count')
    if isinstance(alignment_samples, bool) or not isinstance(alignment_samples, int) or abs(alignment_samples) >= len(actual):
        raise ValueError('alignment_samples must be an integer smaller than the sample count')
    actual_report, expected_report = analyze(actual, sample_rate), analyze(expected, sample_rate)
    actual, expected = [float(x) for x in actual], [float(x) for x in expected]
    waveform = _waveform(actual, expected)
    onset_a, onset_e = actual_report['onset_sample'], expected_report['onset_sample']
    onset_error = abs(onset_a - onset_e) if onset_a is not None and onset_e is not None else (0 if onset_a == onset_e else None)
    gates = {'onset_samples': _gate(onset_error, limits['onset_samples'])}
    raw = {'actual': {key: actual_report[key] for key in ('onset_sample', 'peak_fs', 'dc_fs', 'rms_fs', 'energy_fs2_s', 'full_scale_samples', 'flat_peak_samples')},
           'expected': {key: expected_report[key] for key in ('onset_sample', 'peak_fs', 'dc_fs', 'rms_fs', 'energy_fs2_s', 'full_scale_samples', 'flat_peak_samples')},
           'waveform': waveform,
           'peak_ratio': _ratio(actual_report['peak_fs'], expected_report['peak_fs']),
           'rms_ratio': _ratio(actual_report['rms_fs'], expected_report['rms_fs'])}
    for key in ('peak_fs', 'dc_fs', 'rms_fs'):
        gates[key] = _gate(abs(actual_report[key] - expected_report[key]), limits[key])
    for field in ('rms', 'peak'):
        key = 'waveform_' + field + '_fs'
        gates[key] = _gate(waveform[field + '_fs'], limits[key],
                           'waveform null not required in statistical mode' if mode == 'statistical' else None)
    unexpected_silence = expected_report['peak_fs'] > 0 and actual_report['peak_fs'] == 0
    gates['signal_present'] = {'status': 'failed' if unexpected_silence else 'passed',
                               'reason': 'unexpected silence' if unexpected_silence else None}
    frequency_error, periods = _pitch_error(actual_report['frequency'], expected_report['frequency'])
    raw['frequency'] = {'actual_median_hz': actual_report['frequency']['median_hz'],
                        'expected_median_hz': expected_report['frequency']['median_hz'],
                        'maximum_trajectory_cents': frequency_error, 'compared_periods': periods}
    gates['frequency_cents'] = _gate(frequency_error, limits['frequency_cents'],
                                     'reference pitch unavailable' if expected_report['frequency']['median_hz'] is None else None)
    raw['decay'] = {}
    for polarity in ('positive', 'negative'):
        key = 'decay_' + polarity
        a, e = actual_report[key]['time_constant_s'], expected_report[key]['time_constant_s']
        relative = abs(a / e - 1) if a is not None and e is not None else None
        raw['decay'][polarity] = {'actual_s': a, 'expected_s': e, 'relative_error': relative}
        gates[key] = _gate(relative, limits['decay_relative'], 'reference decay unavailable' if e is None else None)
    band_errors = {}
    raw['spectral_windows'] = {}
    for window in ('onset', 'body', 'tail'):
        a, e = actual_report['spectra'][window], expected_report['spectra'][window]
        band_errors[window] = [abs(av['mean_square_fs'] - ev['mean_square_fs'])
                               for av, ev in zip(a['bands'], e['bands'])]
        raw['spectral_windows'][window] = {
            key: e[key] for key in ('start_sample', 'end_sample', 'window', 'fft_length',
                                    'bin_width_hz', 'normalization')}
        raw['spectral_windows'][window]['bands_hz'] = [[x['low_hz'], x['high_hz']] for x in e['bands']]
    all_bands = [value for window in band_errors.values() for value in window]
    raw['band_power_errors_fs2'] = band_errors
    gates['band_power_fs2'] = _gate(max(all_bands) if all_bands else None,
                                   limits['band_power_fs2'], 'spectral windows too short' if not all_bands else None)
    if alignment_samples >= 0:
        aligned_actual, aligned_expected = actual[alignment_samples:], expected[:len(expected) - alignment_samples]
    else:
        aligned_actual, aligned_expected = actual[:len(actual) + alignment_samples], expected[-alignment_samples:]
    passed = all(gate['status'] != 'failed' for gate in gates.values())
    return {'status': 'passed' if passed else 'failed', 'passed': passed, 'mode': mode,
            'sample_rate': sample_rate, 'sample_count': len(actual), 'tolerances': limits,
            'raw': raw, 'gates': gates,
            'aligned': {'alignment_samples': alignment_samples, 'overlap_samples': len(aligned_actual),
                        'waveform': _waveform(aligned_actual, aligned_expected),
                        'affects_acceptance': False}}


def compare_backends(oracle, sample_rate, tolerances, coldfire=None, sharc=None):
    """Judge each present backend against the oracle, then against its peer.

    An unavailable peer does not fail an otherwise passing available backend.
    A report with no available backend is unavailable, never passed. Pairwise
    comparison uses the supplied limits, without silently doubling budgets.
    """
    oracle = list(oracle)
    analyze(oracle, sample_rate)
    _tolerances(tolerances)
    reports, present = {}, {}
    for name, samples in (('coldfire', coldfire), ('sharc', sharc)):
        if samples is None:
            reports[name] = {'status': 'unavailable', 'passed': None, 'reason': 'backend output not supplied'}
        else:
            present[name] = list(samples)
            reports[name] = compare_samples(present[name], oracle, sample_rate, tolerances)
    peer = (compare_samples(present['coldfire'], present['sharc'], sample_rate, tolerances)
            if len(present) == 2 else {'status': 'unavailable', 'passed': None, 'reason': 'both backend outputs required'})
    passed = (all(reports[name]['passed'] for name in present)
              and peer['status'] != 'failed') if present else None
    return {'status': ('passed' if passed else 'failed') if present else 'unavailable',
            'passed': passed, 'backends': reports, 'cross_cpu': peer}
