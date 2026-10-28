# 808 body, finite excitation and Decay control

The #9 prototype now drives a damped mode with a
[1 ms trigger and shaped main input](808-main-input.md), followed by
[Q43 leakage and pitch sigh](808-leakage.md). Full nonlinear diode/transistor behavior,
stock feedback/Decay mapping and the complete loaded output network
remain missing. The settled body pitch is now 47.65 Hz, rounded from the
initial five-setting software-reference measurements; see [pitch calibration](808-pitch.md).
This is a provisional calibration, not complete circuit alignment. The saved layout
stays unchanged. DECAY changes feedback retention on every block, and TNTUN now
drives the [passive Tone RC stage](808-tone.md). ATTK is ignored in 808 mode.
The [continuing-pitch investigation](808-pitch-sigh-investigation.md) identifies
Q43 as the late-error source and records the corrections rejected before porting.
The subsequent [effective feedback calibration](808-feedback-calibration.md)
changes the two internal Q43 coefficients together; its CPU/native qualification
and retained early/short-setting regressions are recorded separately.
Current bounded numeric/reference/native qualification is the
[main-pulse timescale correction](808-main-pulse-time.md), `9e78ca9`, following
the [Tone control-shape calibration](808-tone-shape.md). Both retain the
remaining fidelity and historical native limitations.
The [first 909 body](909-body.md) follows separately. The [reference-informed Decay increment](808-decay.md) shortens the
previously excessive tails. The raw-body equations below
describe the 808 oscillator before Tone and the [C47 coupling filter](808-coupling.md).
The source-separated [C39 companion excitation](808-companion.md) now enters
the negative band-pass bridge channel on both CPUs.

## Model and units

At 48,000 samples/second, START resets the oscillator and both source nodes.
The main trigger drives the R162/R163/C40 shelf for 48 samples, then D53's ideal
negative clamp supplies its falling edge. The C39 companion has its separate
6 ms envelope. Each source uses the fixed encoding 15 V = .25 FS.

Both ASM implementations advance the same calibrated modal pole pair, with
integrated main/companion forcing. Stored x/y exclude the main source's direct
feedthrough; the rendered body adds that source after each interval. The
[main-input derivation](808-main-input.md) gives the transfer, gains and current
approximations. At 6 ms, both CPUs and the oracle convert the modal state to
retain C41/C42 voltage. No per-hit normalization or alignment is introduced.

The independent oracle solves the pre-switch shaped inputs analytically and
integrates the post-switch nonlinear ODE with eight RK4 substeps per sample.
The CPU ports instead use symmetric leakage/linear splitting; the oracle does
not copy that recurrence. The old fixed sum
of 48 y kicks is historical; it is no longer the current main-input model.

The earlier formula `0.25*exp(-(n+1)/12000)*sin(2*pi*55*(n+1)/48000)` describes
the historical instantaneous-state prototype, before finite excitation.

The [initial frequency-switch stage](808-initial-pitch.md) uses about 131.006 Hz
for the first 6 ms; the underlying settled pole then stays at 47.65 Hz.
Amplitude-dependent Q43 leakage temporarily raises the measured pitch after
that switch, without an imposed pitch envelope. Tested fixed-control body peaks remain below 0.25 digital full scale.
The subsequent coupling stage has a separately derived half-scale transient bound.
Ordinary note pitch is not used. Native AMP/velocity, filters and track level
remain downstream.

## Provisional Decay mapping

For the exact delivered raw word `d` in 0..32512, preserve three anchors with
a join at the approved default 16384:

- `r_min = exp(-1/(48000*.0333))`;
- `r_default = exp(-1/(48000*.143))`;
- `r_max = exp(-1/(48000*.366))`.

Below the default, use `s=d/16384`, `q=s*s+1.5*s*s*(1-s)` and
`tau=.0333+(.143-.0333)*q`, then convert that time constant to retention. Above it, retain the original interpolation
between default and maximum using `(d-16384)/16128`. The raw-body amplitude
time constant is `-1/(48000*log(r(d)))`.
These anchors bring the short/default/long output fits near the fixed-Tone
training recordings; the unloaded coupling stage changes the short fit.
This changes feedback loss, not a separate output envelope. It is a reference
calibration, not stock VR6 feedback/pot modeling or full-curve qualification.
See the [initial calibration](808-decay.md) and the measured
[original lower-half correction](808-decay-lower-half.md). The subsequent
[lower-interior shape correction](808-decay-shape.md) preserves all three
anchors at fixed gain; its component/reference qualification is recorded
separately. Full-device evidence remains at the prior integration checkpoint.

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

#9's first body is integrated in all three emulators. The three-point Decay response is now reference-informed but
provisional; full stock feedback/pot mapping, finite excitation/transistor
behavior, full output loading, calibrated scale and circuit-state retrigger
remain open. Tone filtering now uses the reference-calibrated control shape;
see [current Tone evidence](808-tone-shape.md).
[#79](https://github.com/simonjohansson/x0x/issues/79) owns reference-implementation
and schematic alignment; its [source/code audit](reference-alignment.md) records
the current gaps and pinned source baselines. #2 has the
[full 81-setting training comparison](808-grid-comparison.md) and successive
paired corrections, without consuming held-out settings. Full calibrated fidelity
and physical-device timing remain unqualified.
