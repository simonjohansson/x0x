"""Shared Tone law, relative filter and parameter fitting for the 808 model."""
from . import fit808


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
