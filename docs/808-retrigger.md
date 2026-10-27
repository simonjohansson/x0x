# C39 companion-pulse reference

This #9/#79 checkpoint establishes an isolated **host-only** reference for
C39/R161/D52. It does not change production DSP, resolve the current initial
pitch regressions, or qualify a new native/reference comparison.
The subsequent [state conversion](808-switch-state.md) and
[companion integration](808-companion.md) apply these results on both CPUs.
Measurements and host-only scope below describe this earlier foundation.

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

## Bridge forcing and physical state — host only

The pulse must enter the appropriate bridge channel. With the other sources
held at zero, nodal analysis gives a negative band-pass numerator proportional
to `-s/(R161*C42)`, with C42=15 nF and factor 66.6667/s. This is consistent with
S03's distinction between the main pulse, feedback and companion inputs.

The current modal body instead injects into y, giving a constant-numerator
response proportional to `omega/((s+sigma)^2+omega^2)`. Adding raw node volts
to that input would not implement the companion transfer. For the modal state
matrix `[-sigma,omega; -omega,-sigma]`, the desired `-K*s/D(s)` input requires
a forcing vector `[-K, K*sigma/omega]`, with consistent voltage/output units.
The isolated physical state representation below now derives the main and
companion channels; the loaded feedback and complete circuit remain open.

Take `u=V+`, `r=Vrp`, `c=Vcomm`, `b=Vbt`, and capacitor-voltage states
`q1=u-c` across C41 and `q2=c-b` across C42. Ground the feedback voltage
source, retaining R170=470 kΩ as a load. S01 gives R167=1 MΩ and
C41=C42=15 nF. Write `a=1/(R167*C41)` and
`G=1/R161 + 1/R170 + 1/Rg`, where Rg is 6.8 kΩ during the 6 ms working
attack and 53.8 kΩ afterward. Ideal op-amp input KCL and common-node KCL give:

```
dq1/dt = -a*(q1+q2)
dq2/dt = (G/C42-a)*q1 - a*q2 - (G/C42)*u + r/(R161*C42)
b = u-q1-q2
```

Every state and source is in volts. In particular, the main input has direct
feedthrough; the companion does not. Their independent transfer functions are:

```
D(s) = s*s + 2*a*s + a*G/C42
Hmain(s) = 1 + (G/C42)*s/D(s)
Hcompanion(s) = -s/(R161*C42*D(s))
```

The main channel recovers S03 Eq.5. The companion uses the R161/R170
interchange described after Eq.7. **The printed Eq.7 has an apparent error:**
its `alpha2=Rk*R167*C41*C42` omits R170. The other printed coefficients have
units of resistance after multiplication by their powers of s; that alpha2
does not. Nodal analysis instead gives
`alpha2=Rk*R170*R167*C41*C42`, retaining the printed numerator, alpha1 and
alpha0. This restores their common denominator with Eq.5's loaded bridge.
Use that independently derived expression, not a literal transcription of the
inconsistent coefficient. The paper/source PDF is preserved unchanged.

For constant inputs, the equilibrium capacitor voltages are `(e,-e)`, where
`e=u-r/(R161*G)`. `bridge_reference()` solves the two-state deviation from
that equilibrium with an exact matrix exponential over each held sample.
Both capacitor voltages remain continuous at the resistance switch; retaining
the existing modal y value would not preserve that physical state when the
frequency changes. No reset or extra kick is added at the switch.

With these nominal, open-feedback components, natural frequencies are
130.0302/49.4435 Hz during/after attack; damped frequencies are
129.5966/48.2916 Hz. The damping time constant is 15 ms. These are isolated
bridge results, **not** replacements for production's calibrated pitch/Decay,
nor evidence that the closed stock circuit or captured VST has those poles.

The C39 node and this bridge still use independently driven source
approximations: ground-loading C39, then holding its sampled output at the
bridge input, does not solve their mutual loading. Feedback shelf, main pulse
shaper, rail behavior, Q43 leakage and the final volts-to-audio scale remain
open. The next port can retain explicitly labeled approximations, but must use
consistent physical forcing/state and a documented fixed voltage-to-audio scale.
It need not wait for every remaining circuit block. Do not select a per-hit
gain, time shift or arbitrary y kick to hide the first
25/150 ms regressions. No training or held-out recording was used for this
source derivation.

## Validation and scope

`tools/x0x/retrigger808.py` uses capacitor voltage as state and exact
zero-order-hold intervals. Five tests cover both edges and their polarity,
closed-form RC decay, the below-clipping linear response, charge history,
48/96 kHz physical-time equivalence and invalid-input rejection. Five additional
bridge tests independently check inverse-Laplace step responses for both source
channels, a piecewise second-order ODE across the switch, equal held waveforms
at 48/96 kHz, source superposition and invalid inputs. 130 host tests and
independent C/UI suites pass. The local result/provenance snapshots are
`out/reference/808-retrigger/reference.json` (earlier C39-only checkpoint) and
`out/reference/808-retrigger/bridge.json` (current isolated bridge).

This host-only checkpoint changed no production C/ASM, private voice layout,
public API, saved format or control. Its production baseline was the historical
[initial-switch evidence](808-initial-pitch.md), including reference regressions;
see the subsequent state-conversion evidence above for the current DSP.
Held-out audio and the HTML report are untouched.
#9/#79 retain DSP integration and complete circuit work; #2 retains fidelity;
#78/#20/#80 keep their existing acceptance status.
