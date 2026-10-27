# 808 companion excitation

Measurements below describe the historical companion-only build. The subsequent
[main-input increment](808-main-input.md) replaces its provisional main y drive;
the companion source and its qualifications remain in use.

This #9/#79 increment connects the source-separated C39/R161/D52 companion
pulse to both DSP backends. It follows the [isolated circuit reference](808-retrigger.md)
and [capacitor-state conversion](808-switch-state.md). It retains the current
1 ms main drive, calibrated pole frequencies/Decay and 6 ms working envelope.
The complete pulse shaper, loaded feedback, nonlinear leakage/pitch sigh,
accent and circuit-state retrigger remain open.

## Source, scale and forcing

Use the existing ideal positive 0.71 V D52 clamp, C39=33 nF and R161=1 MΩ.
A fresh nominal 15 V envelope therefore produces +0.71 V at its rise and
`0.71*exp(-.006/.033)-15 = -14.408035 V` at its fall. Both intervals decay
with the 33 ms RC time constant. The negative edge is not diode-clamped.
The S01 4 ms / S03 6 ms disagreement and independent-source loading
approximation remain explicit in the earlier derivation.

For this private DSP encoding, **15 V maps to 0.25 digital full scale**:
`VOLT_SCALE=GAIN/15=1/60`. This is a fixed encoding/headroom convention, not a
hardware/VST voltage calibration or a gain fitted to the recordings. The main
drive and output scale are unchanged. Native AMP/track level remains downstream.

With z=x+i*y, A=-sigma-i*omega and K=1/(R161*C42)=66.6667/s, the source enters as:

```
dz/dt = A*z + (-K + i*K*sigma/omega)*r(t)
r(t+dt) = r(t)*exp(-dt/.033)
```

This is the negative band-pass bridge channel. It is not a raw pulse added to
the current main y drive. For a constant-pole segment beginning with z0/r0:

```
B = -K + i*K*sigma/omega
z(t) = exp(A*t)*z0 + B*r0*(exp(A*t)-exp(-t/.033))/(A+1/.033)
```

The independent oracle evaluates that closed form at every output sample and
starts a new segment only at a frequency/Decay change. Both ASM implementations
instead advance the per-sample oscillator and RC state with the analytically
integrated one-step coefficient
`G=B*(exp(A/fs)-exp(-1/(fs*.033)))/(A+1/.033)`.
They interpolate G through the existing three Decay anchors; this remains a
numerical approximation checked against the exact continuous-forcing oracle.

At 6 ms, keep x continuous, convert y to retain capacitor voltage, then subtract
the encoded envelope voltage from the RC state. This affects the following
sample's forcing. START resets both main and companion states; the physically
correct interaction of repeated triggers with residual circuit state is deferred.

## Private integration and checks

One new volatile word stores the C39 node per voice: ColdFire has four words
per voice; SHARC uses a new 16-word bank at private offset 512 and 576 total
private bytes. C arrays, guard ranges, native observers and model/ownership
clears cover that word. The render callback, settings/events, saved controls,
IDs and MODEL behavior keep their existing boundaries.

ColdFire clears the RC state only when Q31 rounding would make its next value
identical to its current value. Seeded positive/negative one-LSB residues test
this natural precision floor; there is no fitted tail cutoff. The isolated main
oracle still tests the declared pole frequencies and damping. Full driven
waveform comparisons keep the same 1e-5 FS limit, and frequency/decay analyzer
checks retain their existing limits against the driven oracle: continuing C39
forcing means a finite-window exponential fit need not equal the bare pole.

Three new host tests check an independent inverse-Laplace response, a numerical
ODE solution with Decay edits around the 6 ms event, and composed headroom.
134 host tests and independent C/UI suites pass, including companion-state
retention/clear behavior. Both actual CPU suites pass with ownership, context,
invalid-input, interleaving/retrigger, fractional/live-control and existing
909 checks. SHARC exercises 9,012 calls with 1,708 code bytes and 576 private
bytes. Instruction counts remain informational, without a performance budget.

DN2's native settled Tone check now separates the homogeneous body mode from
the continuing RC-driven particular solution before applying the existing Tone
state transfer. This replaces the previous unforced-only prediction, preserving
its 1e-5 FS limit. Both Tone predictions agree with native state within
6.016e-9 FS in this run.

## Native and reference results

All three installed emulator scenarios completed. DT checks 39,298 callbacks
and 27,929 counter/coupling blocks, failing only known #78 resets. DN passes
100,784 callbacks, 92,403 observed blocks and all three exact-zero baselines;
this passing waveform does not resolve the historical #20 residue. DN2's tested
scenario passes 31,878 DSP frames with no reported halt/missing blocks. Controls,
locks/LFO, persistence, mixed models and existing 909 checks remain functional.
#80's distinct late MODEL path remains unqualified.

Fresh 96,000-sample CPU renders at the same five training settings pass the
unchanged numeric limit: maximum errors 1.380e-6 FS (ColdFire), 2.764e-6 FS
(SHARC), and 4.016e-6 FS between CPUs. Fifteen reference takes retain verified
hashes, repeat identity, settings and MIDI timing. Only the existing documented
reference multiplier x4 is applied; mod gain/timing are raw, with no alignment,
normalization or fitting.

| Setting | Whole-clip raw RMS FS, state-only / companion |
| --- | --- |
| Default | 0.065629 / 0.065463 |
| Dark, short | 0.023023 / 0.021744 |
| Bright, short | 0.024122 / 0.022874 |
| Dark, long | 0.070383 / 0.075368 |
| Bright, long | 0.071617 / 0.076637 |

First 25 ms error improves at all five settings, by roughly 5–6%. Whole-clip
short errors improve about 5%; default changes very little. Both long errors
worsen about 7%, including first-150-ms regressions. The older default/short
regressions against the pre-switch Decay build remain unresolved. This is
implementation progress, not a convincing full sound match.

Detailed windows, raw floats, executable/source hashes and original render
provenance are retained in `out/reference/808-companion/measurements.json`.
The first SHARC render inventory omitted the new oracle dependency; that
original inventory is preserved and its samples separately revalidated against
the fully hashed current oracle. No DSP-source mismatch is exempted.

The subsequent main-input increment supplies the pulse shaper and proper
bridge forcing. Full feedback/loading, nonlinear pitch sigh and calibrated
source/control behavior remain planned #9/#79 work.

Native firmware SHA256: DT
`ff4c9a49e25e5d73ab991204e192feee8f97a50f9058bab6d2e76c580a10f321`;
DN `9686812d1a72a8cdfb7dd4124aa1e2962304723755af99786450f5b64e1e8a2f`;
DN2 `c41876d34bdbba6b71ed0f9b4927c451e0459d74fb0def5b100536e7514898d1`.

HTML and held-out audio remain untouched. This does not close full attack,
circuit/fidelity or combined acceptance; #78/#20/#80 retain their own gates.
