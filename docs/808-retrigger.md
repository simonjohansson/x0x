# C39 companion-pulse reference

The next #9/#79 increment establishes an isolated **host-only** reference for
C39/R161/D52. It does not change production DSP, resolve the current initial
pitch regressions, or qualify a new native/reference comparison.

## Circuit and explicit assumptions

S01 p.9 and S03 §8.1/Figure8 show C39=0.033 µF, R161=1 MΩ and D52
clamping the positive edge at their node. Following Figure8, approximate Vcomm
as ground. The RC time constant is therefore 33 ms. Use an ideal envelope
voltage source and a fixed 0.71 V positive diode clamp, with capacitor charge
updated when the diode conducts. The diode voltage is a provisional silicon
approximation, following S03's diode treatment, not a measured D52 calibration.

The test envelope is a nominal 15 V rectangle, high for the current 6 ms working
baseline. S01's roughly 4 ms description and S03's 6 ms timing still disagree;
this reference does not resolve that difference. Q41/Q42, finite source/diode
impedance, loading from Vcomm and nonlinear leakage remain unmodeled.

For input voltage E and stored capacitor voltage Vc, the node immediately
after an input edge is `v = min(E - Vc, Vd)`. During the following constant-input
interval, solve the RC decay exactly and update the charge:

```
v(t + dt) = v(t) * exp(-dt/(R161*C39))
Vc(t + dt) = E - v(t + dt)
```

This is a limiting ideal-diode circuit model, not a clipping operation applied
after an otherwise unchanged linear filter. The clamp changes capacitor charge.
It must not clamp the falling edge to -0.71 V: D52 has the opposite polarity to
that interpretation.

For a fresh 15 V pulse of duration T=6 ms, the reference predicts:

- Rising node voltage: +0.710 V, followed by RC decay.
- Falling node voltage: `0.71*exp(-T/.033)-15 = -14.408035 V`.
- Negative tail: the falling voltage times `exp(-(t-T)/.033)`.

An unclamped linear high-pass core, followed only by positive output clipping,
would give about -2.494 V at the fall and retain a different capacitor charge.
These are distinct approximations. The charge-state candidate is not claimed
to reproduce the real transistor/diode network or the VST's hidden internal node.

## Forcing is the next integration boundary

The pulse must enter the appropriate bridge channel. With the other sources
held at zero, nodal analysis gives a negative band-pass numerator proportional
to `-s/(R161*C42)`, with C42=15 nF and factor 66.6667/s. This is consistent with
S03's distinction between the main pulse, feedback and companion inputs.

The current modal body instead injects into y, giving a constant-numerator
response proportional to `omega/((s+sigma)^2+omega^2)`. Adding raw node volts
to that input would not implement the companion transfer. For the modal state
matrix `[-sigma,omega; -omega,-sigma]`, the desired `-K*s/D(s)` input requires
a forcing vector `[-K, K*sigma/omega]`, with consistent voltage/output units.
The switched physical state representation and the other input channels still
need derivation before that can be called the original circuit.

Do that coupling/scale work before connecting this reference to the two ASM
backends. Do not select a per-hit gain, time shift or arbitrary y kick to hide
the first 25/150 ms regressions. The ground-loading assumption here also excludes
the R161/Q43 interaction that creates pitch sigh.

## Validation and scope

`tools/x0x/retrigger808.py` uses capacitor voltage as state and exact
zero-order-hold intervals. Five tests cover both edges and their polarity,
closed-form RC decay, the below-clipping linear response, charge history,
48/96 kHz physical-time equivalence and invalid-input rejection. 125 host tests
and independent C/UI suites pass. The local result/provenance snapshot is
`out/reference/808-retrigger/reference.json`.

No production C/ASM, private voice layout, public API, saved format or control
changes. No new emulator run or VST pass is claimed: the unchanged production
revision remains the [initial-switch evidence](808-initial-pitch.md), including
its reference regressions. Held-out audio and the HTML report are untouched.
#9/#79 retain DSP integration and complete circuit work; #2 retains fidelity;
#78/#20/#80 keep their existing acceptance status.
