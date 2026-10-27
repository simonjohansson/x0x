# Reference implementations and circuit alignment

Source/code audit for [#79](https://github.com/simonjohansson/x0x/issues/79),
27 October 2026. The initial audit inspected runtime `a05912e`; the inventory
below includes the subsequent [Tone RC implementation](808-tone.md),
[isolated C47 coupling](808-coupling.md), [finite excitation](808-excitation.md) and
[first 909 triangle body](909-body.md).
Saved controls remain unchanged. This is an alignment inventory, not evidence
that either engine reproduces original hardware or a reference VST.

## Selected source baselines

Source IDs, retrieval URLs, hashes and local archive paths are recorded in
[`research/manifest.json`](../research/manifest.json). Downloaded PDFs/code stay
ignored; the manifest can reconstruct the source set after a fresh clone.

| Instrument | Source baseline | How it is used |
| --- | --- | --- |
| 808 | Roland service notes S01, printed pp.4–5 and p.9 BD schematic | Component identities, wiring, stock controls and trigger behavior |
| 808 | Werner/Abel/Smith 2014 S03, §§3–9; Werner dissertation S04 as a cross-check | Published circuit equations and stated approximations, not an assumption that our oscillator already implements them |
| 808 | Original Plaits `AnalogBassDrum`, S43 with S45/S46 | Readable implementation reference for excitation, resonator, transient and tone stages; stock parameter mapping still needs independent derivation |
| 909 | Roland service notes S02, pp.4–5, waveform sheet p.9, BD schematic p.11 | Nominal stock circuit; the snare explanation on p.6 is not the BD model |
| 909 | Whittle S05, pp.2–3 and original schematic p.12 | Circuit explanation and distinction between stock controls and modifications |
| 909-like comparison only | Plaits `SyntheticBassDrum`, S44 | An implementation candidate to study, not the stock-909 authority |

For the 909 baseline, use the original schematic's drawn component population,
including nominal R495=150 kΩ, and retain its serial/surface-mount annotation.
This selects a nominal model for subsequent derivation; it does not assert that
every production revision has identical components. Do not mix alternate
populations silently when implementing the attack branch.

## Reference code provenance and limits

The four Plaits sources are pinned to original-author repository revision
[`f4cfa7697095a28d292bff758beb51deb49b5a86`](https://github.com/pichenettes/eurorack/tree/f4cfa7697095a28d292bff758beb51deb49b5a86),
with their in-file MIT notices retained. The matching `stmlib` dependency is
`e3bd7c9cc00e4364166f9905c0509b6ffd0535ec`. These are research snapshots, not a
new production dependency. The initial audit inspected these snapshots only;
the classes now have [executable host reference renders](reference-renders.md)
with pinned archive dependencies S47/S48, deterministic initialization and
ASan/UBSan checks. This does not establish stock circuit or VST fidelity.

- [AnalogBassDrum](https://github.com/pichenettes/eurorack/blob/f4cfa7697095a28d292bff758beb51deb49b5a86/plaits/dsp/drums/analog_bass_drum.h)
  describes itself as a revisited 808 model. It includes finite excitation,
  diode shaping, FM/retrigger pulses, a resonator and tone filtering. Sustain,
  free frequency, FM amounts and its own control curves are extensions or
  approximations; copying its parameters would not establish stock behavior.
- [SyntheticBassDrum](https://github.com/pichenettes/eurorack/blob/f4cfa7697095a28d292bff758beb51deb49b5a86/plaits/dsp/drums/synthetic_bass_drum.h)
  calls itself an oscillator/FM/envelope model and describes its 909 resemblance
  as incidental. It uses a distorted sinusoid, pitch/body/transient envelopes,
  a VCA approximation and noise/click paths. It is not a circuit-exact 909 port.
- [Engine wiring](https://github.com/pichenettes/eurorack/blob/f4cfa7697095a28d292bff758beb51deb49b5a86/plaits/dsp/engine/bass_drum_engine.cc)
  and [DSP definitions](https://github.com/pichenettes/eurorack/blob/f4cfa7697095a28d292bff758beb51deb49b5a86/plaits/dsp/dsp.h)
  distinguish the drum classes' 48 kHz constants from the Plaits hardware-clock
  tuning compensation. A host reference should call the classes with explicit
  settings rather than inherit an unrelated hardware note correction.

The executable harness pins required dependencies, initializes whole objects
with static zero initialization before `Init()`, seeds noise explicitly, and
uses a fresh process for every capture. S44's `Init()` does not assign its two
transient-envelope fields, so calling it on an otherwise uninitialized object
would not give a reproducible reference. Comparison code stays outside production
DSP; original notices remain in the ignored source archives.

## 808 source-to-code inventory

Current production paths are
[ColdFire ASM](../targets/coldfire/body808.s),
[ColdFire Tone ASM](../targets/coldfire/tone808.s),
[SHARC+ ASM](../targets/sharc/body808.s), the
[analytical body oracle](../tools/x0x/body808.py), and device C adapters under
[`machines/`](../machines/). The same ColdFire source serves DT and DN; DN2 calls
its SHARC payload directly through the SDK bridge.

| Block | Source target | Current implementation | Alignment status |
| --- | --- | --- | --- |
| Trigger/excitation | S01 p.4/p.9; S03 §§3–4, approximately 1 ms accent-dependent pulse and R162/R163/C40/D53 shaping | START clears x/y and drives the provisional mode for 48 samples, with independent convolution and both ASM implementations | Nominal 1 ms rectangle implemented; shaping/diode, physical forcing/gain and accent remain missing |
| Resonator | S03 §5 Eq.5 and §7 Eq.7; S01 p.9 bridged-T around IC12/C41/C42/R165–R167 | `x0x_808_body` / SHARC `body_sample`: two-state damped rotation at fixed 55 Hz with a finite rectangular drive | Provisional isolated mode/forcing; circuit numerator, physical input transfer and full topology absent |
| Decay | S03 §6 Eq.6 and Fig.7; VR6 changes a frequency-dependent R164/R169/C43 feedback shelf returned through R170 | `retention()` and each ASM coefficient setup linearly interpolate radius versus delivered B | Audible and numerically checked, but not the stock shelf/pot response |
| Initial pitch shift | S01 p.5 and S03 §8.1: Q41–Q43 switched resistance during attack | Rotation frequency stays fixed | Missing; retain the service-note/paper timing difference instead of silently choosing one |
| Internal retrigger/pitch sigh | S03 §§8.1–8.2: C39/R161/D52 event and Q43 leakage behavior | No transient or nonlinear feedback state | Missing |
| Tone | S01 p.9; S03 §9 Table1 and Eq.11 passive low-pass | TPT RC filter on both CPUs, checked against independent capacitor voltage/current integration; TNTUN changes it live | Nominal RC response implemented; bright-up resistance-linear knob mapping is provisional, C taper/direction calibration remains |
| Coupling/output | S03 §9 Table1 (VR4 correction); S01 p.9; S04 §1.7 | Isolated C47=.47µF / VR4=100k HP at fixed full level, after isolated Tone | C47 RC implemented; full loading, C49/R176/R177, transistor buffer and C50 remain missing. Native level remains downstream |
| Accent | S01 trigger logic and S03 §3 | Fixed integrated rectangular drive; device AMP/velocity remains downstream | Intrinsic accent/excitation absent; do not add the native gain twice |
| Same-voice retrigger | S03 §11/Fig.12: new excitation interacts with residual circuit state | START replaces the oscillator state | Provisional restart, not circuit-state retrigger behavior |

MODEL/state ownership, exact Decay delivery, output guards, host controls and
native integration already have tests. Those tests prove our declared simplified
model and plumbing; they do not close the missing circuit rows above.

## 909 source-to-code inventory

The first 909 slice adds an unshaped triangle on both CPUs. Its fixed 50 Hz,
gain and zero-crossing START remain explicitly provisional. Live Decay now uses
the unloaded C8/VR5/R58 discharge path with a provisional resistance-linear taper;
the sources establish the VCO topology, not those complete-circuit parameters.
The stock pitch/shaper and complete envelope/VCA networks remain missing.

| Block | Source target | Current implementation | Alignment status |
| --- | --- | --- | --- |
| VCO/shaper | S02 p.4/p.11; S05 p.3/p.12: triangle oscillator IC13, D10/D11 and R52 rounding | Independent triangle model and separate CPU phase/fold implementations | Triangle foundation implemented; circuit VCO/control calibration and diode rounding missing |
| Tune/pitch path | S02 ENV3/VR2/C9; S05 p.3 distinguishes stock Tune from added Pitch/Tune Depth | Fixed 50 Hz; TNTUN delivered but ignored in this slice | Stock pitch-envelope/time mapping missing; do not reinterpret stock Tune as chromatic transpose |
| Tonal Decay/VCA | S02 p.11 / S05 p.12 ENV1→Q12: C8=0.33 µF, VR5=1 MΩ(A), R58=47 kΩ | Live unloaded RC time constant; independent continuous exponential and both ASM backends | Partial: resistance-linear taper provisional; D8/R36/R22, R54/Q12 loading, charging/accent and complete VCA missing. See [909 model](909-body.md) |
| Attack pulse/noise | S02 p.4/p.11, ENV2→Q6; S05 p.12, VR3 and C12 | ATTK routed | Pulse, filtered continuous noise and VCA absent; Attack is branch level, not ADSR rise time |
| Trigger/accent/retrigger | S02 pp.4–5 and BD Q11 clamp; separate accent and approximately 2 ms/5 V trigger | START restarts triangle phase/amplitude | Provisional restart, no circuit excitation/clamp-release or residual-state behavior |
| Output sum/calibration | S02 p.4/p.11; S05 p.12 | Provisional 0.25 internal gain and native track volume | No calibrated tonal/attack sum or 909 internal scale yet |

## Resolved readings and explicit assumptions

A visual check of S01 p.9 confirms **R164=47 kΩ**, rather than the dissertation
Table4.2's conflicting 4.7 kΩ. The same schematic identifies **VR4 Level,
VR5 Tone and VR6 Decay**; S03 Table1's level-control VR6 identifier is a typo.
Use the original schematic when implementing those rows.

For Tone, S01 p.9 gives R171=220 Ω, R172=10 kΩ, VR5=10 kΩ marked C, and
C45=0.1 µF. S03 Eq.11 gives

`Req = R171 + (R172*VR5*l)/(R172+VR5*l)`

and its Table1 gives `H(s)=1/(1+s*Req*C45)`. Resistance fraction `l` from 0 to 1
gives endpoint cutoffs of approximately 7.23 kHz and 305 Hz. The implemented
native mapping provisionally uses `l=1-raw/32512`, making higher TNTUN brighter.
This is resistance-linear, not a calibrated stock C taper or verified physical
knob direction. The [Tone checks](808-tone.md) establish the nominal RC response,
including rich diagnostic input; a pure 55 Hz sine shows only a modest difference
until excitation supplies richer content.

Other boundaries remain visible: nominal values are not unit calibration;
stock versus modified 909 controls must stay separate; and the 909 R495
annotation must accompany the selected nominal population.

The C47/VR4 stage uses the published unloaded decomposition with VR4 fixed
wide open. S04 §1.7 warns that cascaded isolated stages omit loading and can
introduce significant differences; this is an incremental approximation, not
the complete output model. C49/R176/R177 and the buffer must be derived with
their connections intact rather than silently assuming the 2014 table's
numerator/resistor naming describes the unloaded node exactly.

## Next increments and remaining gates

1. Tone RC response and both CPU implementations are complete for the declared
   nominal network and provisional knob mapping. Preserve the independent
   step/rich-input checks while deriving the stock C taper/direction later.
2. The nominal finite trigger duration is implemented. Derive the pulse-shaper
   edge/diode and physical input transfer, then add the internal transient and
   deliberate residual-state retrigger as each stage lands. Then replace provisional Decay radius control with the
   source-derived feedback network. Keep the distinctions in the table current.
3. The first unshaped 909 triangle runs on both CPUs and all three devices in
   #25, now with live unloaded RC Decay and the separate late DN2 transition retained
   in #80. Add diode shaping, then
   derive the stock pitch/envelope/attack paths using the schematic baseline;
   use S44 as a secondary comparison, not an excuse to declare stock fidelity.
4. The pinned Plaits classes now have reproducible executable host renders and
   measured control/retrigger differences. Continue the stock-circuit models
   and record matched physical settings before calling either engine source-aligned;
   the synthetic class is not a stock-909 reference.
5. Compare those aligned engine revisions to VST captures later in #2. Missing
   VST access does not block the source audit, analytical models or ASM work.

#79 remains open for the missing stock circuit models, corrections and alignment report.
#9/#25 remain the implementation owners. Host, component, native-emulator and
physical/VST evidence stay separate. Tone component/native evidence is recorded
in [808-tone.md](808-tone.md); the initial source audit itself added no audio
qualification.
