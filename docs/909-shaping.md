# 909 antiparallel diode shaping

This historical `e55f3e9` checkpoint precedes the [current Tune/pitch
increment](909-tune.md); its measurements retain their original identities.

This #25/#79 increment adds the documented D10/D11 rounding stage between the
existing constant-amplitude triangle oscillator and its separate Decay/VCA
multiplier. It changes both actual ASM backends in the same combined mods.
The fixed 50 Hz audition pitch, START phase, unloaded C8 Decay approximation,
private two-word 909 state and approved controls/IDs/MODEL policy stay unchanged.
Tune, Attack/noise, the complete VCA and faithful retrigger remain later #25 work.

## Circuit boundary and operating assumptions

Roland service notes S02 p.4/p.11 and Whittle S05 p.3/p.12 show the IC13
triangle driving R52=10 kΩ, with antiparallel D10/D11 to ground. R53=2.2 kΩ
and R43=47 Ω provide the passive load before Q12. S05 describes the diodes
conducting around 0.5–0.6 V, rounding the triangle toward a sine; its added
Drive control is a modification and is not adopted here. Source files and
SHA256 identities remain in [the research manifest](../research/manifest.json).
The original PDFs were visually inspected, including their schematic nodes.

The shaper uses the following **explicit provisional operating assumptions**:

- The comparator swings to ±13 V on the drawn ±15 V supply. R49=100 kΩ and
  R50=47 kΩ then give an IC13 triangle peak of `13*47/147 = 4.15646 V`.
  This finite op-amp swing is an audition assumption, not a measured IC13 value.
- The two symmetric generic silicon diodes use the Shockley relation with
  `Is=1 nA` and `n*Vt=0.052 V` (ideality 2, thermal voltage 26 mV).
  These are not extracted original-diode parameters or a VST fit. Temperature,
  mismatch, finite op-amp impedance and junction capacitance remain unmodeled.
- The passive load is `R53+R43=2247 Ω`; Q12's signal-dependent loading is
  omitted with the rest of the incomplete VCA. This is a bounded shaper model,
  not a complete solved bass-drum circuit.

For triangle `x` in −1..1, source voltage `Vin=4.15646*x`, and node voltage `v`:

```
(Vin-v)/R52 = v/(R53+R43) + 2*Is*sinh(v/(n*Vt))
```

The model solves this monotone KCL equation independently by Newton iteration;
tests check the original branch currents and a separate bracketed root solve.
At positive peak the node is **0.594211 V**, within S05's stated conduction
region. This numerical consistency does not validate the assumed diode model.

The retained provisional audio unit divides `v` by the fixed open-diode linear
peak `4.15646*2247/12247 = 0.762601 V`. This removes the fixed passive divider
from the audition unit; it is **not measured output calibration or normalization
by the shaped peak**. With the diodes open the transfer would be exactly `x`.
The diode transfer instead peaks at 0.779190 in those units, so the unchanged
0.25 internal gain now gives an unenveloped peak about 0.194798 FS. The peak
compression is intentional; no corner-specific gain or reference alignment.
Native track level remains downstream.

## Both CPU implementations

The independent reference evaluates the physical root after a trigonometric
triangle. Both CPUs use the existing integer phase folding, followed by sixteen
positive-half cubic Hermite intervals and odd symmetry. Coefficients come from
the KCL roots and their implicit derivatives, not from recorded audio. A dense
0..1 check bounds interpolation error below 6e-6 in the shaper's linear units
(1.5e-6 FS at the existing maximum internal gain). Endpoint and derivative
continuity, monotonicity, odd symmetry and reduced third harmonic are checked.
Eight intervals would give about 2.044e-5 FS error, exceeding the existing
1e-5 FS numeric bound; sixteen avoid changing that bound.

ColdFire keeps its coefficients in a private read-only table; SHARC selects
inline constants, preserving the existing loader format. Both evaluate three
Horner products before the original envelope update/multiplication. The
shrinking envelope never drives the nonlinear diode curve: this stage keeps
its fixed oscillator operating point through the tail. No new dynamic state,
saved field, public SDK interface, machine registration or control is introduced.

## Validation and remaining gates

Seven focused host tests pass, including KCL/bisection agreement, the bounded
cubic approximation, source topology behavior, spectral rounding and continued
Decay history. The original raw-triangle analytical test remains a separate
oscillator foundation check.

The isolated actual ColdFire suite passes six corner/fractional Decay renders,
24,000 samples each, with maximum independent-model error **1.402e-6 FS**.
Live Decay, phase wrap/extrema, retrigger/interleaving, state/output/stack guards,
callee registers and the full EMAC context pass. The existing four-second
quantization-tail check still reaches exact zero. The default measured frequency
is 49.999997 Hz and the envelope time constant is 0.18180972 s. Numeric waveform
acceptance remains the existing **1e-5 FS**, without alignment or fitted gain.

The existing shared SHARC suite passes **9,012 calls**, with 4,302 code bytes
and unchanged 1,024 private bytes. Its six matching 24,000-sample 909 renders
have maximum model error **1.399e-6 FS**; live Decay error is 1.392e-6 FS. The
maximum cross-CPU difference is **4.229e-7 FS**. All retain the original 1e-5
FS limit, without gain or time fitting. Shared invalid-input, ownership,
MODEL/retrigger/interleaving and complete SDK context guards pass.

The min/default/max 808 outputs, 24,000 samples each, are **byte-identical** to
the prior `d3ba46f` actual SHARC renders. Its fractional/live Tone/Decay and
mixed-model checks also pass in the same suite. No 808 source algorithm or
audio behavior is changed by this shaper increment.

Local isolated evidence is in `out/909-shaping/{coldfire,sharc}/report.json` and
`out/909-shaping/comparison.json`, including actual image/source hashes and
the three preserved 808 sample hashes. No standard or frozen #80 artifact is
replaced by these component runs. Instruction counts remain informational;
there is no instruction budget. No Cargo build or new test sweep was needed.

These are model/CPU component checks. Parent integration owns the current
installed-emulator matrix; a component pass does not qualify native controls,
downstream PCM or missing native stages. Known DT reset #78, historical DN
baseline #20 and DN2 MODEL/input #80 retain their own gates. The available 909
reference recordings have not been used to tune this increment; #2 still owns
the recording comparison. Held-out audio and the HTML report remain untouched.
Stock pitch/trigger calibration, real diode operating points, transistor loading,
VCA/Decay taper, antialiasing, Attack/noise and complete stock fidelity remain open.

## Integrated native and recording evidence

The coordinated full host/C UI run passes 145 tests; the three new 909 comparison
tests also pass. DT OS 1.54 runs 39,102 callbacks and retains only known #78 reset
failures. DN OS 1.44 passes 100,814 callbacks, native 909 endpoints/PCM, controls,
locks/LFO, reload and mixed models. Its current zero baselines do not resolve
#20's historically reproduced downstream residue.

DN2 OS 1.12 passes the complete installed 909 diode scenario on the isolated
Digikit INTC-fix candidate, including both nonlinear 808 Tone checks and final 909
endpoints. This is candidate-runtime evidence, not a claim that the unchanged
vendor pin already fixes #80. The exact already-passed 9,012-call SHARC component
bytes/report were verified and reused for packaging, rather than rerunning
unchanged component tests. The original late MODEL gate is qualified separately
against unchanged 808-leakage firmware; its report does not substitute for this
new diode firmware run.

Native firmware SHA256 values:

- DT: `7cba9082ea7d448971bf81fd472764615cb0fe3c95715c45e7bc3a6a86cfcf6f`.
- DN: `a52ee50236f39d99beede0176fd77f443a8c02a38f4e5920f9b663aaa4542592`.
- DN2: `c36be58e58116fa572f8bc7e0c00b6c6cbda91d4196a72b4bc3acc04ad888232`.

Reports/captures and the effective candidate binary/source provenance are under
`out/909-shaping/native/`. The first [909 training comparison](909-reference-baseline.md)
uses the actual half-second CPU outputs against 15 fresh grid takes at default
and four Tune/Decay corners, retaining all three repetitions and documented
reference×4/as-recorded residuals. Current Tune/Attack are explicitly unused,
so reused equal-Decay renders are not parameter-delivery proof. It finds
50 Hz versus about 52.58 Hz settled pitch and substantially excessive default/long
audio decay. That evidence prioritizes the existing Tune/pitch then loaded
ENV1/Q12 increments; no generic pitch envelope or fitted global C8 multiplier.
Held-out audio and HTML remain untouched.
