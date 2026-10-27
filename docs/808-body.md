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

SHARC uses float32 `a=c-1` and `s`, advancing the equivalent small rotation
increments `x_next=x+(a*x+s*y)` and `y_next=y+(a*y-s*x)`. This avoids bias from
rounding the near-one coefficient c directly. Its 24,000-sample direct run has
maximum error 2.675e-7 FS, frequency 54.99999754 Hz and fitted time constant
0.250000204 s. All 944 callback cases pass with 560 code bytes, 256 state bytes
and at most 649 instructions under the unchanged 1,000-instruction bound.
The first 128 state bytes retain the selector metadata; sixteen x/y pairs occupy
the next 128. This is private DSP RAM, not a saved-sound layout.

Matching unshifted CPU samples differ by at most 3.968e-7 FS over 24,000 samples.
Run `mise run test:808:body` for both components and the cross-CPU comparison.

## Native integration

The existing native runners now execute the production 808 body and retain
909 silence, control/lock/LFO delivery, MODEL latching, persistence and owned
output checks. The old `:silent` command names remain compatibility aliases.

| Device | First-body evidence | Full native regression |
| --- | --- | --- |
| DT OS 1.54 | Nonzero owned Q31 output and stereo PCM; peak 4526/32768 in `out/dt/silent/native-808.wav` | 21,783 callbacks; only the known parameter/page resets in #78 fail |
| DN OS 1.44 | 9,174 nonzero 808 blocks; stereo PCM peak 6478/32768 in `out/dn/silent/808-native.wav` | 13,951 callbacks; all checks pass, including 4,777 silent 909 blocks |
| DN2 OS 1.12 | Native first-body check in progress | Pending |

The captures are actual emulator output without normalization. Their different
levels include each device's native downstream processing. Direct CPU comparisons
above use the same raw internal scale and omit that processing. No duplicate
velocity or saved LEVEL gain is applied by the body.

#9 stays open for DN2 native evidence and the remaining circuit stages. #2
reference captures and physical-device timing remain outside this increment.
