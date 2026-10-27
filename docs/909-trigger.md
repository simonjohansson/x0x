# 909 finite trigger reset and output polarity

This #25/#79 correction combines finite Q11/R51 reset with the source-correct
negative tonal output polarity. C9 Tune and the [loaded C8 VCA](909-vca.md)
remain intact. Saved controls, IDs, MODEL policy and private state/argument
layout are unchanged. The missing Attack branch remains separate work.

## Source correction

S02's bass-drum schematic and S05's annotated circuit draw **Q10 as PNP**.
With IC13b forced high, Q10 is off; negative IC12a CV reaches follower IC12b,
so the inverting IC13a integrator rises. This is the direction that can reach
the positive Schmitt threshold and sustain the oscillator. The earlier NPN
reading instead drove it away from that threshold. Two independent source
checks verified the symbol and current path before selecting the correction.

D10/D11 and R53/R43 retain that signal sign. Q12 supplies signal current to
IC11a's inverting summing node, giving a **negative small-signal body output**.
This establishes polarity, not complete transistor gain/compression. Apply the
inversion after diode shaping and the C8-controlled gain; do not invert the
physical capacitor history or treat polarity as a fitted reference parameter.

Q11 does not directly short C14 to an ideal zero. R51=2.2kΩ is in series with
the switch across C14=0.033µF, giving a72.6µs feedback time constant during the
existing2ms electrical trigger. Q7's coupled drive keeps the switch active
through that pulse. For phase-like integrator state p and the C9-driven VCO:

```
p' = f(C9) − p/(R51*C14)     while the trigger is active
p' = f(C9)                  after release
```

The prior ideal zero-hold trial and wrong-sign finite-reset trial remain
historical failures in `out/909-trigger/`; neither is silently adopted.

## Numeric implementation and ownership

The C9 charge and C14 reset flows are integrated together. Independent
closed-form convolution and RK4 checks cover the switched circuit. With
`x=dt/tau_C9`, `y=dt/tau_reset`, `mR=(1-exp(-y))/y`, use
`M=(exp(-x)-exp(-y))/(y-x)` and `D=(mR-M)/x`. A regular beta-integral moment
series evaluates D without small-difference division, then `M=mR-x*D`.
The existing ON-phase cache stores the resulting gains; C9 voltage updates,
C8 quarter steps, private banks and callback contracts are unchanged.

Both ports retain the existing explicit START clears of phase, C9 and C8.
The independent physical helper can model retained charge, but that capability
is not permission to infer native ownership from a reused numeric slot.
Faithful same-sound retrigger remains unqualified until voice identity and
switch operating history are established. No generation API is invented here.

## Actual CPU and training evidence

169 relevant host cases and the independent C/UI suites pass, including eight
focused trigger tests. Both complete actual-CPU suites pass the unchanged
1e-5FS waveform bound: ColdFire maximum1.210e-6, SHARC3.191e-6. The shared
SHARC suite runs14,298 guarded callbacks with5,672code/1,664private bytes;
all nine808 baseline renders remain byte-identical. Context, state/stack guards,
live controls, model interleaving and existing START policy remain checked.
ColdFire's four-second audio output is zero while C8 retains positive below-knee
charge; those are separate observations.

Five actual half-second renders from each CPU are compared against the same
15 verified training takes. Peer difference is at most2.605e-6FS. Raw scheduled
timing/gain and the audited reference×4 are retained, with as-recorded residuals
alongside; no fitted gain, phase shift, delay or normalization.

| Setting | Previous VCA | Finite reset/negative body |
| --- | ---: | ---: |
| Default | .072872 | .069849 |
| Low Tune, short Decay | .063790 | .059688 |
| High Tune, short Decay | .060564 | .058365 |
| Low Tune, long Decay | .097754 | .075203 |
| High Tune, long Decay | .095055 | .078052 |

These first-repetition whole-window errors improve at all five settings;
all first6ms and first150ms residuals also improve. **Default first25/50ms
regress**, .107785→.136398 and.176037→.184512FS. The modeled body starts
negative at sample0; the complete reference starts positive at sample6.
Missing Attack does not justify assigning every residual to that branch.
Peak/level calibration, full transistor behavior and onset remain unqualified.

The default positive-peak audio-envelope estimate is55.046ms against57.323ms
reference; long estimates76.366/74.109ms remain below about98.5ms reference.
Low-Tune/short now resolves at5.743ms against17.666ms, while high-Tune/short
remains unresolved. C8 physics is unchanged: these phase-sensitive audio
estimates are not new capacitor time constants or short-tail acceptance.

Full reports are `out/909-trigger/final/{coldfire-suite,sharc-suite}/report.json`,
`paired-cpu.json` and `808-byte-identity.json`. Current-source paired measurements
are `out/reference/909-trigger/measurements.json` and `comparison-to-vca.json`.
The four-way rejected-sign diagnostics remain separate from actual final ports.

## Installed-emulator evidence

| Device | Result | Remaining gate |
| --- | --- | --- |
| DT 1.54 | 47,135callbacks; five909 cases, raw/native audio, controls, locks/LFO/reload and mixed models complete | Only deferred #78 resets |
| DN 1.44 | 110,123callbacks,72same-frame mixed blocks; five909 cases and10,793C8 continuation checks pass; no DSP violations | Historical #20 bright baseline remains one PCM16 count in all sixty windows;909 baseline zero |
| DN2 1.12 | Original full regression passes37,815audio/37,816DSPframes, no halt/missing blocks/ColdFire error; all808/control/mixed/909 cases complete | New early-trigger observation was initially unqualified; a separate focused same-firmware probe qualifies it below |

The first DN2 observer used frame-target jobs that advanced a complete emulator
chunk, skipping the2ms charging prefix. The original report remains marked
unqualified for that witness, with its regression checks passing. A focused
probe uses the existing exact instruction-step command, with no firmware rebuild,
new transport, guest delay or retry. At four of the same24allowedDSPframes it
observes a fresh selected909 voice with remaining64: exactly32rendered samples.
Independent phase/C9/C8 errors are1.86e-9cycles,1.12e-7normalized and
1.24e-6encoded units, below their unchanged1e-5bounds. This complements the full
report; neither is relabeled as the other. The future combined observer adopts
that stepping method with the original120s wall watchdog and24/750frame targets;
its revised whole-script run is not claimed here.

Evidence: `out/909-trigger/native/qualification.json`, nativeDT/DN report folders,
and `native/dn2/{native-boot-report.json,first-trigger-focused/report.json}`.
Firmware SHA256:

- DT: `f633a77695581b55d5440390d219732936ec1a025677aca6fbb5b798afa122b9`.
- DN: `68dee9aeebba4d79900940ca25ec5624630f6bd1ae22bffccd7920ad72c92c34`.
- DN2: `671e544ffb04d1b536a25ccde831565592d9089597bf972f1ebd6078d90378ff`.

No physical devices, held-out recordings or HTML changes. The next existing
work is Attack pulse/noise and the remaining circuit/calibration/retrigger gates.
