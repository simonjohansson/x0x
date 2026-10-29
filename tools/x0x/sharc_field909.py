"""Packed 909 coefficient tables for the handwritten SHARC kernel."""
import struct
import numpy as np
from . import field909


def write_tables(add, floats):
    model = field909.load()

    def packed(name, values, row_width=None):
        values = np.asarray(values)
        if row_width is not None:
            values = np.pad(values, ((0, 0), (0, row_width - values.shape[1])))
        raw = values.astype(values.dtype.newbyteorder('<')).tobytes()
        raw += bytes(-len(raw) % 4)
        add(name, list(struct.unpack('<' + 'I' * (len(raw) // 4), raw)))

    packed('f909_body', model['body_q'].reshape(5, 11, 30)[:, :, 1:].reshape(5, 319), 320)
    packed('f909_control', model['control_q'], 20)
    floats('f909_control_gain', model['control_scale'].astype(float) * model['body_scale'] * 4)
    packed('f909_onset_control', model['onset_control_q'], 122)
    floats('f909_onset_gain', model['onset_control_scale'].astype(float) * model['onset_scale'] * 4)
    packed('f909_onset', model['onset_q'].T)
    floats('f909_phase', model['phase_poly'])
    add('f909_frames', model['time_frames'].tolist())
    floats('f909_inverse', 1 / np.diff(model['time_frames'].astype(float)))
    packed('f909_time', model['time_poly_q'].transpose(0, 2, 1))
    floats('f909_reciprocal', [0, 1, .5, 1 / 3])
    floats('f909_q32', [2**32])
    floats('f909_inv4096', [1 / 4096])
    floats('f909_inv96', [1 / 96])
    step = round(float(model['frequency'][0]) / 48000 * 2**64)
    add('f909_step_hi', [step >> 32])
    add('f909_step_lo', [step & 0xffffffff])
