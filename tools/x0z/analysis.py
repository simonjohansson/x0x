"""Raw mono measurements for deterministic kick fixtures, using only the stdlib.

The frequency estimate is intended for a tonal body, not a noisy attack. It uses
positive zero-crossing periods, checks peak periods independently, excludes the
first 10 ms after onset, and masks amplitudes below -80 dB relative to the peak
or 1e-9 FS. It does not subtract DC, align time, or normalize gain.
"""

import cmath
import math
import statistics


def _extrema(samples, sign):
    peaks = []
    for i in range(1, len(samples) - 1):
        left, center, right = (sign * samples[j] for j in (i - 1, i, i + 1))
        if center > 0 and center > left and center >= right:
            curvature = left - 2 * center + right
            offset = (left - right) / (2 * curvature)
            amplitude = center - (left - right) * offset / 4
            peaks.append((i + offset, amplitude))
    return peaks


def _decay(peaks, rate, onset, floor):
    selected = [(sample / rate, math.log(amplitude)) for sample, amplitude in peaks
                if sample >= onset + .01 * rate and amplitude >= floor]
    result = {"valid": False, "points": len(selected), "time_constant_s": None,
              "slope_db_per_s": None, "log_amplitude_rms_residual": None,
              "r_squared": None}
    if len(selected) < 3 or selected[-1][0] - selected[0][0] < .03:
        result["reason"] = "fewer than three peaks spanning 30 ms above the floor"
        return result
    xs, ys = zip(*selected)
    xm, ym = statistics.fmean(xs), statistics.fmean(ys)
    slope = math.fsum((x - xm) * (y - ym) for x, y in selected) / math.fsum(
        (x - xm) ** 2 for x in xs)
    residual = math.fsum((y - ym - slope * (x - xm)) ** 2 for x, y in selected)
    variance = math.fsum((y - ym) ** 2 for y in ys)
    result.update(valid=True, reason=None, start_s=xs[0], end_s=xs[-1],
                  time_constant_s=-1 / slope if slope < -1e-9 else None,
                  slope_db_per_s=slope * 20 / math.log(10),
                  log_amplitude_rms_residual=math.sqrt(residual / len(xs)),
                  r_squared=1 - residual / variance if variance > 1e-20 else None)
    return result


def _frequency(samples, rate, onset, floor):
    crossings = [i - 1 - samples[i - 1] / (samples[i] - samples[i - 1])
                 for i in range(1, len(samples))
                 if samples[i - 1] <= 0 < samples[i]]
    cycles = []
    peak_times = []
    for first, last in zip(crossings, crossings[1:]):
        start, stop = math.ceil(first), math.floor(last) + 1
        high_index = max(range(start, stop), key=samples.__getitem__)
        low = min(samples[start:stop])
        high = samples[high_index]
        peak_time = float(high_index)
        if 0 < high_index < len(samples) - 1:
            left, right = samples[high_index - 1], samples[high_index + 1]
            curvature = left - 2 * high + right
            if curvature:
                peak_time += (left - right) / (2 * curvature)
        amplitude = (high - low) / 2
        cycles.append({"start_sample": first, "end_sample": last,
                       "frequency_hz": rate / (last - first),
                       "amplitude_fs": amplitude, "valid": True,
                       "reason": None, "peak_period_hz": None})
        peak_times.append(peak_time)
    for i, cycle in enumerate(cycles):
        reason = None
        if cycle["start_sample"] < onset + .01 * rate:
            reason = "onset exclusion"
        elif cycle["amplitude_fs"] < floor:
            reason = "below amplitude floor"
        elif not 10 <= cycle["frequency_hz"] <= min(2000, rate / 4):
            reason = "outside tonal-body range"
        elif i + 1 == len(cycles):
            reason = "no following peak for cross-check"
        else:
            distance = peak_times[i + 1] - peak_times[i]
            if distance <= 0:
                reason = "invalid peak period"
            else:
                peak_frequency = rate / distance
                cycle["peak_period_hz"] = peak_frequency
                if abs(peak_frequency / cycle["frequency_hz"] - 1) > .02:
                    reason = "crossing and peak periods disagree by more than 2%"
        cycle.update(valid=reason is None, reason=reason)
    reliable = [x["frequency_hz"] for x in cycles if x["valid"]]
    return {"method": "positive zero crossings, cross-checked with peak periods",
            "onset_exclusion_s": .01, "amplitude_floor_fs": floor,
            "minimum_cycles": 3, "reliable_cycles": len(reliable),
            "median_hz": statistics.median(reliable) if len(reliable) >= 3 else None,
            "cycles": cycles}


def _fft(values):
    """Unnormalized radix-2 FFT for the bounded spectral measurement windows."""
    n = len(values)
    result = [complex(x) for x in values]
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            result[i], result[j] = result[j], result[i]
    size = 2
    while size <= n:
        step = cmath.exp(-2j * math.pi / size)
        for start in range(0, n, size):
            factor = 1 + 0j
            for i in range(start, start + size // 2):
                even = result[i]
                odd = factor * result[i + size // 2]
                result[i], result[i + size // 2] = even + odd, even - odd
                factor *= step
        size *= 2
    return result


def _spectrum(samples, rate, start, stop):
    start, stop = min(start, len(samples)), min(stop, len(samples))
    count = stop - start
    result = {"start_sample": start, "end_sample": stop, "window": "symmetric Hann",
              "hop_samples": None, "sample_count": count, "fft_length": None,
              "bin_width_hz": None, "normalization": "one-sided window-weighted mean square FS",
              "valid": count >= 3, "mean_square_fs": None, "bands": [],
              "energy_fs2_s": math.fsum(x * x for x in samples[start:stop]) / rate}
    if count < 3:
        return result
    window = [.5 - .5 * math.cos(2 * math.pi * i / (count - 1)) for i in range(count)]
    fft_length = 1 << (count - 1).bit_length()
    transformed = _fft([x * w for x, w in zip(samples[start:stop], window)]
                       + [0.] * (fft_length - count))
    divisor = fft_length * math.fsum(w * w for w in window)
    power = [(abs(value) / math.sqrt(divisor)) ** 2 * (1 if i in (0, fft_length // 2) else 2)
             for i, value in enumerate(transformed[:fft_length // 2 + 1])]
    edges = [0, 30, 150, 1000, rate / 2]
    edges = sorted(set(min(rate / 2, edge) for edge in edges))
    for low, high in zip(edges, edges[1:]):
        total = math.fsum(p for i, p in enumerate(power)
                          if low <= i * rate / fft_length < high
                          or (high == rate / 2 and i == fft_length // 2))
        result["bands"].append({"low_hz": low, "high_hz": high,
                                "mean_square_fs": total})
    result.update(fft_length=fft_length, bin_width_hz=rate / fft_length,
                  mean_square_fs=math.fsum(power))
    return result


def analyze(samples, sample_rate):
    """Measure finite mono normalized samples without alignment or gain changes.

    Spectra cover [0,20 ms), [20,200 ms), and the last <=200 ms after
    200 ms. These are explicit measurement windows, not assumed circuit stages.
    Full-scale samples flag possible clipping; their presence alone does not
    prove a clipped waveform. Short/unreliable pitch and decay return None.
    """
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, int) or sample_rate <= 0:
        raise ValueError("sample_rate must be a positive integer")
    try:
        samples = list(samples)
        if any(isinstance(x, (bool, str, bytes)) for x in samples):
            raise ValueError("samples must be finite mono numbers")
        samples = [float(x) for x in samples]
    except (TypeError, OverflowError) as error:
        raise ValueError("samples must be finite mono numbers") from error
    if not samples or not all(math.isfinite(x) for x in samples):
        raise ValueError("samples must be nonempty and finite")
    count = len(samples)
    peak = max(abs(x) for x in samples)
    onset_threshold = max(1e-12, peak * 1e-6)
    onset = next((i for i, x in enumerate(samples) if abs(x) > onset_threshold), None)
    floor = max(1e-9, peak * 1e-4)
    positive, negative = _extrema(samples, 1), _extrema(samples, -1)
    energy = math.fsum(x * x for x in samples)
    if not math.isfinite(energy):
        raise ValueError("sample magnitudes exceed the measurement range")
    return {"sample_rate": sample_rate, "sample_count": count, "duration_s": count / sample_rate,
            "peak_fs": peak, "minimum_fs": min(samples), "maximum_fs": max(samples),
            "dc_fs": statistics.fmean(samples), "rms_fs": math.sqrt(energy / count),
            "energy_fs2_s": energy / sample_rate,
            "full_scale_samples": sum(abs(x) >= 1 for x in samples),
            "flat_peak_samples": sum(samples[i] == samples[i - 1] and abs(samples[i]) == peak
                                     for i in range(1, count)) if peak else 0,
            "onset_sample": onset, "onset_threshold_fs": onset_threshold,
            "onset_polarity": (1 if samples[onset] > 0 else -1) if onset is not None else None,
            "frequency": _frequency(samples, sample_rate, onset or 0, floor),
            "decay_positive": _decay(positive, sample_rate, onset or 0, floor),
            "decay_negative": _decay(negative, sample_rate, onset or 0, floor),
            "spectra": {
                "onset": _spectrum(samples, sample_rate, 0, round(.02 * sample_rate)),
                "body": _spectrum(samples, sample_rate, round(.02 * sample_rate), round(.2 * sample_rate)),
                "tail": _spectrum(samples, sample_rate, max(round(.2 * sample_rate), count - round(.2 * sample_rate)), count),
            }}
