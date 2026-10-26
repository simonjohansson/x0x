import json
import math
import random
import unittest

from x0z.comparison import compare_backends, compare_samples


RATE = 48000
STRICT = dict(onset_samples=0, peak_fs=1e-6, dc_fs=1e-6, rms_fs=1e-6,
              waveform_rms_fs=1e-6, waveform_peak_fs=1e-6,
              frequency_cents=.1, decay_relative=.001, band_power_fs2=1e-6)


def tone(frequency=56, decay=.2, gain=.5, duration=.4):
    return [gain * math.exp(-i / RATE / decay) * math.sin(2 * math.pi * frequency * i / RATE)
            for i in range(round(duration * RATE))]


class ComparisonTests(unittest.TestCase):
    def test_identical_signal_passes_and_records_raw_metrics(self):
        signal = tone()
        result = compare_samples(signal, signal, RATE, STRICT)
        self.assertTrue(result['passed'])
        self.assertEqual(result['raw']['waveform']['rms_fs'], 0)
        self.assertEqual(result['raw']['peak_ratio'], 1)
        self.assertGreater(result['raw']['frequency']['compared_periods'], 3)
        json.dumps(result, allow_nan=False)

    def test_one_sample_delay_cannot_be_hidden_by_alignment(self):
        expected = tone()
        actual = [0.] + expected[:-1]
        report = compare_samples(actual, expected, RATE, STRICT, alignment_samples=1)
        self.assertFalse(report['passed'])
        self.assertEqual(report['gates']['onset_samples']['error'], 1)
        self.assertEqual(report['raw']['actual']['onset_sample'], report['raw']['expected']['onset_sample'] + 1)
        self.assertEqual(report['aligned']['waveform']['rms_fs'], 0)
        self.assertEqual(report['aligned']['overlap_samples'], len(expected) - 1)
        self.assertGreater(report['raw']['waveform']['rms_fs'], 0)
        self.assertFalse(report['aligned']['affects_acceptance'])

    def test_negative_alignment_preserves_raw_failure(self):
        actual = tone()
        expected = [0.] + actual[:-1]
        report = compare_samples(actual, expected, RATE, STRICT, alignment_samples=-1)
        self.assertFalse(report['passed'])
        self.assertEqual(report['aligned']['waveform']['rms_fs'], 0)

    def test_gain_pitch_decay_dc_and_clipping_defects_fail_their_gates(self):
        expected = tone()
        defects = [
            (tone(gain=.4), 'peak_fs'),
            (tone(frequency=58), 'frequency_cents'),
            (tone(decay=.1), 'decay_positive'),
            ([x + .05 for x in expected], 'dc_fs'),
            ([max(-.25, min(.25, x)) for x in expected], 'waveform_peak_fs'),
        ]
        for actual, gate in defects:
            with self.subTest(gate=gate):
                report = compare_samples(actual, expected, RATE, STRICT)
                self.assertFalse(report['passed'])
                self.assertEqual(report['gates'][gate]['status'], 'failed')

    def test_filled_zero_tail_truncation_fails(self):
        expected = tone()
        actual = expected[:RATE // 5] + [0.] * (len(expected) - RATE // 5)
        report = compare_samples(actual, expected, RATE, STRICT)
        self.assertFalse(report['passed'])
        self.assertGreater(report['raw']['band_power_errors_fs2']['tail'][1], STRICT['band_power_fs2'])

    def test_frequency_gate_compares_trajectory_at_matching_times(self):
        duration = .4
        def chirp(start, end):
            return [.5 * math.exp(-i / RATE / .2)
                    * math.sin(2 * math.pi * (start * i / RATE + (end - start) * (i / RATE) ** 2 / (2 * duration)))
                    for i in range(round(duration * RATE))]
        result = compare_samples(chirp(50, 70), chirp(70, 50), RATE, STRICT)
        self.assertEqual(result['gates']['frequency_cents']['status'], 'failed')
        self.assertGreater(result['raw']['frequency']['maximum_trajectory_cents'], 200)

    def test_matching_wrong_backends_still_fail_the_oracle(self):
        wrong = tone(frequency=58)
        result = compare_backends(tone(), RATE, STRICT, coldfire=wrong, sharc=wrong)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['cross_cpu']['status'], 'passed')
        self.assertEqual(result['backends']['coldfire']['status'], 'failed')
        self.assertEqual(result['backends']['sharc']['status'], 'failed')

    def test_unavailable_peer_does_not_fail_present_backend(self):
        oracle = tone()
        result = compare_backends(oracle, RATE, STRICT, coldfire=oracle)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['backends']['sharc']['status'], 'unavailable')
        self.assertIsNone(result['backends']['sharc']['passed'])
        self.assertEqual(result['cross_cpu']['status'], 'unavailable')
        self.assertEqual(compare_backends(oracle, RATE, STRICT)['status'], 'unavailable')
        self.assertIsNone(compare_backends(oracle, RATE, STRICT)['passed'])

    def test_silence_is_valid_and_relative_error_is_unavailable(self):
        signal = [0.] * 1000
        result = compare_samples(signal, signal, RATE, STRICT)
        self.assertTrue(result['passed'])
        self.assertIsNone(result['raw']['waveform']['relative_rms'])
        self.assertIsNone(result['raw']['peak_ratio'])
        self.assertEqual(result['gates']['frequency_cents']['status'], 'unavailable')
        self.assertEqual(result['gates']['decay_positive']['status'], 'unavailable')
        json.dumps(result, allow_nan=False)

    def test_unexpected_silence_fails_even_with_loose_numeric_limits(self):
        expected = tone()
        result = compare_samples([0.] * len(expected), expected, RATE, {key: 1e6 for key in STRICT})
        self.assertFalse(result['passed'])
        self.assertEqual(result['gates']['signal_present']['status'], 'failed')

    def test_statistical_noise_comparison_does_not_require_a_waveform_null(self):
        first, second = random.Random(17), random.Random(23)
        expected = [first.uniform(-.25, .25) for _ in range(RATE // 2)]
        actual = [second.uniform(-.25, .25) for _ in range(RATE // 2)]
        limits = dict(STRICT, peak_fs=.001, dc_fs=.01, rms_fs=.01, band_power_fs2=.006)
        statistical = compare_samples(actual, expected, RATE, limits, mode='statistical')
        self.assertTrue(statistical['passed'])
        self.assertGreater(statistical['raw']['waveform']['rms_fs'], .1)
        self.assertEqual(statistical['gates']['waveform_rms_fs']['status'], 'unavailable')
        self.assertFalse(compare_samples(actual, expected, RATE, limits)['passed'])

    def test_malformed_limits_alignment_samples_and_signals_fail(self):
        signal = [0., .1, 0., -.1]
        missing = dict(STRICT)
        missing.pop('peak_fs')
        for limits in (missing, dict(STRICT, typo=0), dict(STRICT, peak_fs=-1),
                       dict(STRICT, peak_fs=float('nan')), dict(STRICT, peak_fs=True)):
            with self.subTest(limits=limits):
                with self.assertRaises(ValueError):
                    compare_samples(signal, signal, RATE, limits)
        for actual, expected, rate, alignment in (([], [], RATE, 0), (signal, signal[:-1], RATE, 0),
                ([float('nan')], [0], RATE, 0), (signal, signal, 0, 0),
                (signal, signal, RATE, len(signal)), (signal, signal, RATE, True)):
            with self.subTest(actual=actual, rate=rate, alignment=alignment):
                with self.assertRaises(ValueError):
                    compare_samples(actual, expected, rate, STRICT, alignment_samples=alignment)


if __name__ == '__main__':
    unittest.main()
