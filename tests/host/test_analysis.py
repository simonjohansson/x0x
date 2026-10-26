import json
import math
import unittest

from x0z.analysis import analyze


RATE = 48000


def tone(frequency=56, decay=.2, gain=.5, duration=.5, delay=0, dc=0):
    return [0.] * delay + [dc + gain * math.exp(-i / RATE / decay)
                          * math.sin(2 * math.pi * frequency * i / RATE)
                          for i in range(round(duration * RATE))]


class AnalysisTests(unittest.TestCase):
    def test_known_damped_tones_and_decay(self):
        for frequency in (49.5, 56, 80):
            with self.subTest(frequency=frequency):
                report = analyze(tone(frequency), RATE)
                self.assertAlmostEqual(report['frequency']['median_hz'], frequency, delta=.001)
                for name in ('decay_positive', 'decay_negative'):
                    fit = report[name]
                    self.assertTrue(fit['valid'])
                    self.assertAlmostEqual(fit['time_constant_s'], .2, delta=1e-5)
                    self.assertGreater(fit['r_squared'], .999999)
                    self.assertLess(fit['log_amplitude_rms_residual'], 1e-5)
                json.dumps(report, allow_nan=False)

    def test_raw_gain_energy_and_one_sample_delay_survive_analysis(self):
        original = analyze(tone(), RATE)
        changed = analyze(tone(gain=.25, delay=1), RATE)
        self.assertEqual(changed['onset_sample'], original['onset_sample'] + 1)
        self.assertAlmostEqual(changed['peak_fs'] / original['peak_fs'], .5)
        self.assertAlmostEqual(changed['energy_fs2_s'] / original['energy_fs2_s'], .25)
        self.assertAlmostEqual(changed['frequency']['median_hz'], original['frequency']['median_hz'], delta=.001)

    def test_known_frequency_and_decay_defects_change_metrics(self):
        original = analyze(tone(), RATE)
        changed = analyze(tone(frequency=58, decay=.1), RATE)
        self.assertGreater(changed['frequency']['median_hz'] - original['frequency']['median_hz'], 1.99)
        self.assertAlmostEqual(changed['decay_positive']['time_constant_s'], .1, delta=1e-5)

    def test_silence_is_valid_with_unavailable_pitch_and_decay(self):
        report = analyze([0.] * 2000, RATE)
        self.assertEqual(report['peak_fs'], 0)
        self.assertEqual(report['rms_fs'], 0)
        self.assertIsNone(report['onset_sample'])
        self.assertIsNone(report['frequency']['median_hz'])
        self.assertIsNone(report['decay_positive']['time_constant_s'])
        self.assertFalse(report['spectra']['tail']['valid'])
        json.dumps(report, allow_nan=False)

    def test_short_tone_does_not_claim_reliable_frequency(self):
        report = analyze(tone(duration=.025), RATE)
        self.assertIsNone(report['frequency']['median_hz'])
        self.assertFalse(report['decay_positive']['valid'])

    def test_quiet_tail_cycles_are_explicitly_masked(self):
        report = analyze(tone(decay=.03), RATE)
        self.assertTrue(any(x['reason'] == 'below amplitude floor'
                            for x in report['frequency']['cycles']))

    def test_dc_and_clipping_are_visible_without_normalization(self):
        samples = tone(gain=2, decay=1000)
        clipped = [max(-1., min(1., x)) for x in samples]
        report = analyze(clipped, RATE)
        self.assertGreater(report['full_scale_samples'], 0)
        self.assertGreater(report['flat_peak_samples'], 0)
        self.assertEqual(report['peak_fs'], 1)
        below_full_scale = analyze([max(-.25, min(.25, x)) for x in tone()], RATE)
        self.assertEqual(below_full_scale['full_scale_samples'], 0)
        self.assertGreater(below_full_scale['flat_peak_samples'], 0)
        shifted = analyze([x + .125 for x in tone()], RATE)
        baseline = analyze(tone(), RATE)
        self.assertAlmostEqual(shifted['dc_fs'] - baseline['dc_fs'], .125)

    def test_click_changes_onset_and_high_frequency_energy(self):
        samples = tone(delay=48)
        base = analyze(samples, RATE)
        samples[0] = .9
        clicked = analyze(samples, RATE)
        self.assertEqual(clicked['onset_sample'], 0)
        self.assertGreater(clicked['spectra']['onset']['energy_fs2_s'],
                           base['spectra']['onset']['energy_fs2_s'])
        # The Hann endpoint is zero; use an interior click for spectral detection.
        samples[240] += .9
        clicked = analyze(samples, RATE)
        self.assertGreater(clicked['spectra']['onset']['bands'][-1]['mean_square_fs'],
                           base['spectra']['onset']['bands'][-1]['mean_square_fs'] * 100)

    def test_hann_spectral_power_normalization_and_band_partition(self):
        signal = [.5 * math.sin(2 * math.pi * 100 * i / RATE) for i in range(RATE // 2)]
        report = analyze(signal, RATE)
        body = report['spectra']['body']
        self.assertAlmostEqual(body['mean_square_fs'], .5 ** 2 / 2, delta=1e-6)
        self.assertAlmostEqual(sum(x['mean_square_fs'] for x in body['bands']),
                               body['mean_square_fs'], places=12)
        self.assertGreater(body['bands'][1]['mean_square_fs'] / body['mean_square_fs'], .999)
        self.assertEqual(body['fft_length'], 16384)

    def test_tail_spectrum_uses_last_bounded_window(self):
        report = analyze(tone(duration=.8), RATE)
        tail = report['spectra']['tail']
        self.assertEqual(tail['start_sample'], round(.6 * RATE))
        self.assertEqual(tail['end_sample'], round(.8 * RATE))

    def test_invalid_input_fails(self):
        for samples, rate in (([], RATE), ([float('nan')], RATE), ([float('inf')], RATE),
                              ([[0, 1]], RATE), (['0'], RATE), ([True], RATE),
                              ([0], 0), ([0], 48000.), ([0], True)):
            with self.subTest(samples=samples, rate=rate):
                with self.assertRaises(ValueError):
                    analyze(samples, rate)


if __name__ == '__main__':
    unittest.main()
