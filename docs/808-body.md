# First audible 808 body

This #9 increment is an uncalibrated damped sine, before the 808 excitation,
pitch sigh, feedback/Decay mapping, Tone network and output coupling. The saved
layout stays unchanged. TNTUN, DECAY and ATTK are still delivered but do not yet
change this fixed body. MODEL selects this body in 808 mode; 909 remains silent.

## Model and units

At 48,000 samples/second, the independent reference evaluates

`output[n] = 0.25 * exp(-(n+1)/(48000*0.25)) * sin(2*pi*55*(n+1)/48000)`.

A START at sample zero initializes x=0, y=0.25. Both ASM implementations advance
one damped rotation per output sample, using the old x and y on both right sides:

- `x_next = c*x + s*y`, and output `x_next`;
- `y_next = c*y - s*x`;
- `c = exp(-1/12000)*cos(2*pi*55/48000)`;
- `s = exp(-1/12000)*sin(2*pi*55/48000)`.

This gives a 55 Hz body with a 250 ms amplitude time constant and a fixed peak
below 0.25 digital full scale. These are first-body constants, not a calibrated
stock Decay-pot mapping or a timbre/fidelity target. Ordinary note pitch is not
used. Native AMP/velocity, filters and track level remain downstream.

START currently restarts phase and amplitude. Residual circuit-state excitation
and same-voice retrigger behavior remain later #9 work. A MODEL change clears
only that voice's old body. No additional saved values or public SDK API are used.

## Independent checks

`tools/x0x/body808.py` computes the analytical reference directly, without the
ASM recurrence. The host test checks its pitch, exponential decay and output
scale with the existing analyzer. Direct CPU tests stream actual assembled
blocks, compare unshifted samples to that reference, and check state/output
ownership and context preservation. The explicit waveform limit is 1e-5 full
scale, allowing accumulated Q31/float32 coefficient and arithmetic quantization;
there is no normalization, gain fitting or waveform alignment.

ColdFire uses Q1.31 c=2147249049 and s=15459350, nearest-even saturated EMAC
arithmetic and complete EMAC context preservation. Its first direct run renders
48,000 samples with maximum error 3.277e-7 FS, frequency 54.99999845 Hz and fitted
time constant 0.250000535 s. This is component evidence, not an OS audio capture.

SHARC and native DT/DN/DN2 audio checks are the next integration steps. #9 stays
open for those results and the remaining circuit stages. #2 reference captures
and hardware timing remain outside this increment.
