# 808 body, finite excitation and Decay control

The #9 prototype now drives a damped mode with a
[nominal 1 ms rectangular excitation](808-excitation.md). Pulse-edge shaping,
pitch sigh, stock feedback/Decay mapping and the complete loaded output network
remain missing. The settled body pitch is now 47.65 Hz, rounded from the
initial five-setting software-reference measurements; see [pitch calibration](808-pitch.md).
This is a provisional calibration, not complete circuit alignment. The saved layout
stays unchanged. DECAY changes feedback retention on every block, and TNTUN now
drives the [passive Tone RC stage](808-tone.md). ATTK is ignored in 808 mode.
The [first 909 body](909-body.md) follows separately. The raw-body equations below
describe the 808 oscillator before Tone and the [C47 coupling filter](808-coupling.md).

## Model and units

At 48,000 samples/second, START clears x/y and injects `u=0.25/48` into y
before each rotation for exactly 48 samples. Both ASM implementations compute:

- `x_next = c*x + s*(y+u)` and output `x_next`;
- `y_next = c*(y+u) - s*x`.

The fixed internal drive sum is 0.25; there is no per-hit normalization. At the
default DECAY=64, `c=exp(-1/12000)*cos(2*pi*47.65/48000)` and
`s=exp(-1/12000)*sin(2*pi*47.65/48000)`. Other Decay values use the existing live
feedback retention. The independent oracle convolves analytical impulse
responses with the finite drive, integrating log retention over timed changes.
It does not copy the ASM recurrence. [Source boundary, equations and current
checks](808-excitation.md) distinguish the duration-only trigger approximation
from the still-missing pulse shaper and full bridged-T forcing.

The earlier formula `0.25*exp(-(n+1)/12000)*sin(2*pi*55*(n+1)/48000)` describes
the historical instantaneous-state prototype, before finite excitation.

The body stays at 47.65 Hz with a fixed internal peak below 0.25 digital full scale.
The subsequent coupling stage has a separately derived half-scale transient bound.
Ordinary note pitch is not used. Native AMP/velocity, filters and track level
remain downstream.

## Provisional Decay mapping

For the exact delivered raw word `d` in 0..32512, use
`r(d) = r_min + (r_max-r_min)*d/32512`, where:

- `r_max = exp(-1/48000)`;
- `r_default = exp(-1/12000)`;
- `r_min = (r_default-(64/127)*r_max)/(1-64/127)`.

The resulting amplitude time constant is `tau(d) = -1/(48000*log(r(d)))`.
The endpoints are approximately 142 ms and 1 second; the approved default 64
retains 250 ms. This changes feedback loss rather than adding an independent
output envelope. The curve is deliberately provisional, not the stock VR6
potentiometer/circuit model or a timbre-fidelity claim.

Coefficients update once per delivered 32-sample block without clearing body
state. Native smoothing/fractions, parameter locks and LFO delivery therefore
reach the same Decay input; only MODEL remains START-latched. DT forwards the
native raw value. DN forwards the existing bounded exact-position numerator,
so an above-UI native endpoint is safely bounded to 32512. DN2 reads callback
parameter 1 directly in SHARC ASM. No saved layout or control was added.

START currently clears the body and restarts the full 48-sample drive. Residual circuit-state excitation
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

The initial fixed-body results below are historical evidence from before Decay
was connected. ColdFire used Q1.31 c=2147249049 and s=15459350, nearest-even
saturated EMAC arithmetic and complete EMAC context preservation. Its first direct run renders
48,000 samples with maximum error 3.277e-7 FS, frequency 54.99999845 Hz and fitted
time constant 0.250000535 s. This is component evidence, not an OS audio capture.

SHARC uses float32 `a=c-1` and `s`, advancing the equivalent small rotation
increments `x_next=x+(a*x+s*y)` and `y_next=y+(a*y-s*x)`. This avoids bias from
rounding the near-one coefficient c directly. Its 24,000-sample direct run has
maximum error 2.675e-7 FS, frequency 54.99999754 Hz and fitted time constant
0.250000204 s. All 944 callback cases pass with 560 code bytes, 256 state bytes
and at most 649 observed instructions.
The first 128 state bytes retain the selector metadata; sixteen x/y pairs occupy
the next 128. This is private DSP RAM, not a saved-sound layout.

Matching unshifted CPU samples differ by at most 3.968e-7 FS over 24,000 samples.
Run `mise run test:808:body` for both components and the cross-CPU comparison.

Historical Decay-only checks cover raw 0/16384/32512, fractional 1/16385/32511 and
live changes without START. Both implementations retain their state/output and
context guards. Maximum analytical waveform error is 1.009e-6 FS on ColdFire
and 8.23e-7 FS on SHARC. Matching endpoint/default renders differ by at most
6.357e-7 FS. All use the unchanged 1e-5 FS limit, with no alignment or gain fit.
ColdFire uses 252 code bytes and at most 503 instructions including its test
wrapper; SHARC uses 606 code bytes and at most 662 observed instructions. Those runs predate Tone. Current component
costs, the additional Tone state and composed-output errors are recorded in
[808-tone.md](808-tone.md).

## Native integration

The native runners below executed the first production 808 body while 909 was
still silent, retaining control/lock/LFO delivery, MODEL latching, persistence
and owned output checks. The old `:silent` command names remain compatibility
aliases. Current mixed-engine integration is recorded in [909-body.md](909-body.md).

| Device | Historical first-body evidence | Historical full native regression |
| --- | --- | --- |
| DT OS 1.54 | Nonzero owned Q31 output and stereo PCM; peak 4526/32768 in `out/dt/silent/native-808.wav` | 21,783 callbacks; only the known parameter/page resets in #78 fail |
| DN OS 1.44 | 9,174 nonzero 808 blocks; stereo PCM peak 6478/32768 in `out/dn/silent/808-native.wav` | 13,951 callbacks; all checks pass, including 4,777 silent 909 blocks |
| DN2 OS 1.12 | Nonzero owned float output and stereo PCM; peak 0.021733 FS in `out/dn2/silent/native-808.wav` | 15,626 DSP frames; native controls, locks/LFO, project reload and stock coexistence pass; no halt/missing blocks |

The captures are actual emulator output without normalization. Their different
levels include each device's native downstream processing. Direct CPU comparisons
above use the same raw internal scale and omit that processing. No duplicate
velocity or saved LEVEL gain is applied by the body.

## Native Decay checks

Native endpoint edits now produce short and long 808 tails. Captures keep the
same note, velocity and downstream settings; audio is not normalized.

| Device | Historical Decay proof | Regression at that increment |
| --- | --- | --- |
| DT | Actual ASM receives exact 0/32512; raw late/early energy ratios 0.01457/0.54881; captured downstream ratios 0.14332/0.65833 | Only the deferred #78 reset checks fail |
| DN | Native knob endpoints reach exact 0/32512; raw late/early RMS ratios 0.018249/0.563319 and downstream ratios 0.012681/0.510993 | All checks pass across 16,591 callbacks |
| DN2 | Exact 0/32512 delivery; actual DSP-state tau 0.141888/1.000006 s; downstream late/early energy ratios 0.04551/0.50802 | All checks pass across 18,032 DSP frames; no halt/missing blocks |

Decay is now verified through each native control path and actual audio output.
DT captures are `out/dt/silent/decay-{short,long}-{raw,native}.wav`; DN captures
are `out/dn/silent/808-decay-{short,long}-{raw,native}.wav`; DN2 captures are
`out/dn2/silent/decay-{short,long}-native.wav`. The DT/DN tests observe actual
rendered samples; DN2 also observes the two body state variables at two callback
counts, measuring their squared-energy loss without assuming native wall time.

Raw/direct and downstream measurements have different windows and host effects;
compare short against long within each test, not the ratios across devices.

#9's first body is integrated in all three emulators. The Decay response is
provisional; stock feedback/pot mapping, shaped excitation/pitch sigh, full output loading,
calibrated scale and circuit-state retrigger behavior remain open. Tone filtering
is now implemented with a provisional resistance-linear control mapping; see
[the current Tone evidence](808-tone.md).
[#79](https://github.com/simonjohansson/x0x/issues/79) owns reference-implementation
and schematic alignment; its [source/code audit](reference-alignment.md) records
the current gaps and pinned source baselines. #2 now has an initial five-setting
software-reference comparison; the [pitch increment](808-pitch.md) uses that
training evidence without consuming held-out settings. Full calibrated fidelity
and physical-device timing remain unqualified.
