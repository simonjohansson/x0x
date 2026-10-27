# Research: faithful TR-808 and TR-909 bass drums

Research snapshot: 26 October 2026. This document records the circuit evidence
and modeling decisions. The [development guide](development.md) records subsequent
scaffolding and emulator checks; neither engine is implemented or qualified.

The intended product targets **Digitakt, Digitone and Digitone II**, using **C
for native controls and other plumbing, ColdFire assembly for Digitakt/Digitone
audio, and SHARC+ assembly for Digitone II audio**. Digitakt II is outside the
active scope. Each drum has one shared behavioral model and independent offline
reference, implemented separately for the two CPU architectures.

Prioritize the **808**. Its published circuit models make it the better bounded
first project, even though faithful transient and retrigger behavior are not
simple. Aim for an audible, independently tested 808 slice before the more
complex 909 work; this priority does not block an independent ready cell.
Stock behavior comes first;
tunable 808 basslines, distortion, extended decay and circuit bending are later
product decisions.

The user has identified faithful VSTs as the initial comparison sources. Selecting
and validating those references is an early deliverable. Plugin agreement,
circuit-model agreement, emulator execution and physical-device operation are
different claims and must have separate results.

## 1. Decisions and evidence boundaries

| Decision | Research conclusion |
| --- | --- |
| First engine | 808: strongest directly applicable published analysis and a useful small resonator milestone. This is a project recommendation, not a measured effort estimate. |
| Modeling approach | Circuit-informed models, starting with independently verifiable subcircuits; simplify only against measured errors. Retain a higher-accuracy offline reference. |
| Production languages | C for registration/UI/device integration; ColdFire ASM and SHARC+ ASM for their respective render paths, including conversion of delivered controls into audio coefficients. |
| Offline reference | A readable, double-precision mathematical model is permitted as test equipment; Python managed through mise is a suitable initial choice. It is not a second production DSP implementation. |
| Reference sound | Versioned, dry VST captures first. Original hardware evidence remains desirable but is not required to begin. |
| Platform assumption | Use the existing Digitakt/Digitone custom-engine paths. For Digitone II, assume Elekloader PRs [197][U197] and [200][U200] merge. Pin and revalidate each target's headers, adapter and behavior before implementation. |
| Sharing boundary | One model per drum, two CPU backends, three C device adapters; Digitakt and Digitone reuse each ColdFire engine kernel. Select targets at build time. |
| Product packaging | One x0x mod per supported device contains both engines behind a saved per-sound/track MODEL selector. Mixed 808/909 voices coexist in the same installed build. The six cells are test slices, not separate mods or one-engine variants. |
| Memory | Record current code/data usage. The user explicitly allows upstream memory expansion if needed; current limits must not silently dictate fidelity compromises. |
| Progress | Establish shared interfaces/tests and each target's harness/adapter first. Then advance six device/engine cells independently through small audible slices, with independent C UI and ASM DSP suites. No final all-at-once integration milestone. |

Evidence terms used below:

- **Documented:** directly supported by a named schematic, manufacturer document
  or published experiment. A service note can still contain an error.
- **Derived:** a calculation or interpretation of those sources; verify it against
  the circuit and reference captures.
- **Proposed:** a project decision or acceptance criterion, not an observed result.
- **Unresolved:** the sources or current platform do not establish the behavior.

Downloaded papers, manuals, extracted text, images and upstream snapshots are in
the root **research/** directory. The tracked [source manifest](../research/manifest.json)
and [component manifest](../research/manifest-components.json) record source URLs,
retrieval date, local filenames, SHA-256 and acquisition failures. Paths in each
manifest are relative to research/. Use download_url where supplied, otherwise
url; inspect fetch_method for upstream snapshots. Sizes/hashes identify the
archived version, not a guarantee that a mutable remote URL will stay identical.
status records this research session's acquisition outcome, not whether the file
exists on a fresh clone. Fetch needed entries individually and verify the result;
no downloader is included. All other research material remains ignored. The bibliography
below remains usable without that local archive. Third-party source files and
future proprietary reference audio are not part of the tracked documentation.

## 2. Original instruments: control and circuit map

Roland lists LEVEL, TONE and DECAY for the original 808 bass drum, with a shared
accent control. The original 909 bass drum has LEVEL, TUNE, ATTACK and DECAY.
Do not inherit every extra knob from a modern plugin as original hardware
behavior. In particular, a stock 808 has no front-panel bass-drum tuning knob.
[S30], [S31]

| Aspect | 808 | 909 |
| --- | --- | --- |
| Tonal source | Excited bridged-T resonator with active feedback | Voltage-controlled triangle oscillator, followed by diode shaping |
| Start of note | Shaped excitation and an internal frequency-switch/retrigger circuit | Pitch-control envelope, tonal amplitude envelope, and separate attack branch |
| Decay | Changes the resonator feedback network | Controls tonal amplitude decay |
| Spectral control | Passive output tone network | Attack level mixes the separate transient branch |
| Pitch behavior | Brief initial shift plus amplitude-dependent later behavior | Dedicated falling pitch control; stock Tune influences its time course |
| Noise | A generic added white-noise click is not a documented stock BD stage | Filtered shared pseudo-random noise participates in the attack branch |
| Calibration difficulty | Coupled feedback, trigger shaping and residual state | Oscillator/shaper, several envelopes, attack noise and accent interactions |

This functional comparison is grounded in the 808 paper, the 909 manufacturer
block diagram and original modifier notes. It does not assert that those blocks
can be disconnected without loading effects. [S03], [S02], [S05]

### 2.1 The 808 evidence

Roland's service notes describe roughly 1 ms voice excitation, with accent
affecting excitation amplitude. The bass-drum explanation identifies IC12,
feedback decay control VR6, and Q41–Q43 switching the resonator at the attack.
It describes an approximately 4 ms switched interval followed by an internal
retrigger pulse. Inspect printed pages 4–5 and the BD schematic on page 9;
the rear-panel trigger-output specification is not the voice excitation.
[S01]

Werner, Abel and Smith partition the circuit into trigger shaping, resonator,
feedback, frequency effects and output stages. Their central useful distinction
is between the initial frequency shift and the later pitch sigh associated with
the R161/Q43 path. Their output-stage approximation includes tone filtering,
level and coupling, rather than just scaling a sinusoid. The simplified core's
approximately 49.5 Hz result and the manual's nominal 56 Hz chart should not be
turned into a universal measured tuning specification. [S03, §§4–9][S03]

The dissertation develops more complete WDF models and identifies numerical
problems in the pulse shaper. Its whole-circuit experiment uses eight times
44.1 kHz, a finer SPICE reference step and finite trigger rise/fall times.
Subcircuits behaving well separately at 44.1 kHz did not establish acceptable
whole-circuit accuracy there. Its semiconductor substitutions also mean that
agreement with its SPICE experiment is not an original-unit calibration.
[S04, §§3.3, 4.4 and conclusion p.181][S04]

**Implication for x0x:** first make the body decay analytically testable, then add
the excitation, internal attack event, nonlinear coupling and output network one
at a time. Each addition needs a waveform/feature comparison and a small audible
integration check. A single oscillator with two unrelated exponential envelopes
is a useful baseline, but is not sufficient evidence of a faithful stock 808.

### 2.2 The 909 evidence

Roland's block diagram separates the tonal path, controlled by ENV1 through Q12,
from the attack path, controlled by ENV2 through Q6. The latter combines a pulse
generator with filtered shared noise. The control-voltage generator and ENV3
feed the oscillator. The service notes describe a 5 V, 2 ms trigger and a
separate latched accent value. The BD schematic is printed page 11; page 9 is
the waveform sheet. The detailed analog explanation on page 6 uses **snare**
component references, so its numerical examples must not be copied into the BD
model. [S02, pp.4–6, 9, 11][S02]

Whittle's bass-drum notes explicitly distinguish the stock Tune control, which
changes the pitch-envelope decay, from an added static Pitch control. They also
describe triangle-to-rounded-wave shaping with opposing diodes. His extended
decay, Drive and pitch-depth modifications are useful experiments explaining
the circuit, but are outside our first stock target. The appended schematic is
the original circuit, not a schematic of his modified instrument. [S05, pp.2–3,
12][S05]

**Implication for x0x:** independently validate oscillator frequency, waveform
shaping, pitch control, tonal amplitude and attack contribution. Build the
tonal branch first. A sine oscillator can be a test scaffold, but replacing the
documented triangle/shaper path needs an explicit comparison before acceptance.
Likewise, Attack is not an ADSR attack-time control.

### 2.3 The 909 noise source

Electric Druid's circuit tracing finds an effective 31-stage feedback register,
taps numbered 31 and 13, with an additional output delay. That disagrees with
the service-note prose describing 32 stages. The article estimates a clock
around 300 kHz with component-dependent variation, and describes the power-up
initialization that avoids a zero-state lock. This is circuit analysis, not a
calibration of the unit we will emulate. [S06]

Proposed implementation research must resolve bit numbering and shift direction
with a small independently generated sequence before writing optimized ASM.
Compare the filtered attack spectrum and repeated-hit variation, not a raw
bitstream against an unrelated plugin. A 48 kHz white-noise draw and an analog
filtered high-rate LFSR are not automatically interchangeable. Do not run a
shared noise generator once per voice callback: that would make its rate depend
on polyphony. Determine a block-time ownership strategy or document and measure
a per-voice approximation before using it.

## 3. Source reconciliation and component data

### 3.1 Conflicts that must remain visible

| Subject | Source conflict or limitation | Required treatment |
| --- | --- | --- |
| 808 attack interval | Service notes describe about 4 ms; the 2014 analysis discusses about 6 ms | Treat as a calibration range/measurement question, not two competing hardcoded truths. |
| 808 output level identifier | 2014 Table 1 uses VR6 for level; schematic and prose identify VR4, while VR6 is decay | Use the original schematic and rederive the output network. |
| 808 R164 | Dissertation Table 4.2 says 4.7 kΩ; Table 2.3 and original schematic say 47 kΩ | Preserve the discrepancy; verify 47 kΩ from the schematic before entering a netlist. |
| 808 SPICE parts | Dissertation substitutes 1N4148 and 2N3904 for vintage parts | Log substitutions and fit sensitivity; never call this measured original hardware. |
| 909 Tune | Owner's manual calls it pitch; circuit modifier explains envelope-time action | Preserve the stock user label, model the actual circuit relationship. |
| 909 noise register | Manufacturer prose says 32 stages; schematic tracing says 31 | Reconstruct from schematic and chip pin functions, with an independent sequence test. |
| 909 detailed service explanation | General analog discussion uses snare circuitry | Do not borrow its frequencies, reset times or envelope constants for BD. |
| M5218 download naming | A PDF served from an M5218L URL is headed M5218AL/P/FP | Treat it as a later family variant; use the 1984 data book for the period M5218L/P. |
| Modern reference plugins | Extra tuning, gain, distortion, aging or humanization controls may exist | Record and neutralize extensions; verify the chosen stock baseline empirically. |

The discrepancies above come from comparing [S01], [S03], [S04], [S02], [S05],
[S06], [S26], [S33] and the owner/plugin manuals. None was silently corrected in
the archived originals.

### 3.2 What datasheets can and cannot establish

| Document | Use in this project | Evidence limit |
| --- | --- | --- |
| UPC258/UPC4558 [S23] | Op-amp finite gain/bandwidth, output swing, slew and input-current sensitivity | Current revision; does not establish the installed vintage lot's behavior. |
| 2SA733 [S24] | PNP switch/envelope polarity and plausible transistor behavior | Datasheet ranges are not a fitted SPICE model. |
| 2SC945A [S25] | Related NPN characteristics for sensitivity studies | A variant; not an exact identity claim for the original 2SC945(P). |
| M5218L/P, 1984 book [S33] | Period dual-op-amp electrical data for 909 modeling | Device tolerances and actual board operating points still matter. |
| M5218AL/P/FP [S26] | Compare a later family member; detect misleading archive filenames | Must not silently substitute it as the period part. |
| 2SC2603 [S27] | 909 NPN device characteristics | Gain grade and actual VCA operating point need verification. |
| 1SS133 [S28] | Diode I–V and switching behavior sensitivity | Part choice and parameters must be checked against the original BD parts list. |
| CD4006B [S29] | Understand shift-register stage groups and output taps | Related TI/Harris device, not the original Hitachi HD14006 datasheet. |
| ADSP-2156x [S20] | Numeric modes, memory architecture and processor context | Maximum chip speed and total SRAM are not the mod's available audio budget. |

An exact original 1S2473 model and every vintage device grade were not established
in this research. This does not block the first behavioral model. It does block
claims of transistor-for-transistor calibrated equivalence. Start ideal where
appropriate, make substitutions explicit, and add a nonideality when its
observable effect exceeds the reference repeatability or selected error budget.

### 3.3 Parameter extraction workflow

1. Trace the original schematic into named subcircuits. Check units, decimal
   notation, capacitor polarity, reference voltages and pot wiring visually.
2. Record each component value with a page/circuit locator and confidence.
   Keep original values, substituted parts and fitted effective values separate.
3. Derive or simulate the subcircuit before fitting the whole kick. Retain
   internal signals: excitation, pitch control, tonal output, attack contribution
   and final output.
4. Vary tolerances and parameter extremes. A stable mid-knob fit is insufficient.
5. Fit against training captures; evaluate on held-out settings and trigger
   sequences. Document parameter identifiability: different circuits can yield
   similar output waveforms.

This is a proposed investigation workflow, not an already transcribed netlist.

Useful schematic anchors for that transcription are listed below. These are
nominal drawing values, not fitted values or a complete bill of materials.

| Circuit | Verified anchors | Locator |
| --- | --- | --- |
| 808 excitation | R162 4.7 kΩ; R163 100 kΩ; C40 15 nF | [S01], p.9 BD |
| 808 resonator/coupling | R161 1 MΩ; R165 47 kΩ; R166 6.8 kΩ; R167 1 MΩ; C41/C42 15 nF | [S01], p.9 BD |
| 808 attack and decay | C38 100 nF; C39 33 nF; C43 33 µF; VR6 500 kΩ | [S01], p.9 BD |
| 808 output controls | VR4 Level 100 kΩ; VR5 Tone 10 kΩ | [S01], p.9 BD |
| 909 VCO/shaping | C4 33 nF; D10/D11 opposing diodes; R52 10 kΩ | [S02], p.11 BD; [S05], p.12 enlargement |
| 909 control/envelopes | VR2 Tune 100 kΩ(A); C9 330 nF; C8 330 nF; VR5 Decay 1 MΩ(A); C12 33 nF | Same BD schematic |
| 909 attack/level | VR3 Attack 500 Ω(B); VR4 Level 100 kΩ(B) | Same BD schematic |

Keep the A/B taper markings as drawing data until their exact response is
verified. The 909 drawing has a serial-number-dependent R495 note: choose and
record the modeled revision rather than silently combining revisions.

## 4. Mathematical models to investigate

### 4.1 An analytically checkable resonator baseline

For an isolated damped mode, use the continuous model

    d²y/dt² + 2σ dy/dt + ω₀² y = b u(t).

For an underdamped mode, ωd = sqrt(ω₀² − σ²). A discrete homogeneous response
has poles r exp(±jθ), with r = exp(−σ/Fs) and θ = ωd/Fs:

    y[n] = 2 r cos(θ) y[n−1] − r² y[n−2].

The amplitude time constant is τ = 1/σ. Its theoretical 60 dB amplitude decay
time is T60 = ln(1000) τ. These identities provide independent frequency and
decay tests without using implementation output as its own expected result.
The excitation input and initial states must be derived separately; resetting
the output to an arbitrary peak does not reproduce a shaped trigger.

**Proposed use:** a first 808 body oracle and ASM exercise. This is not the full
bridged-T circuit. For very low frequencies and long decay, float32 coefficients
approach cancellation-sensitive values. Fixed-point coefficients also need
explicit scaling: the coefficient 2 r cos(θ) approaches 2 and cannot simply be
stored in Q1.31. Compare direct-form recurrence with a state-space or quadrature
realization before selecting each CPU's ASM form. Test zero
input, long tails and modulation explicitly. Require monotonic decay of the
appropriate state energy only for the unforced, fixed-parameter linear baseline;
driven, modulated and nonlinear stages can legitimately exchange energy.

### 4.2 From circuit to discrete model

A subcircuit can be written as a state equation, with capacitor voltages in x:

    dx/dt = f(x, u, p),     y = g(x, u, p).

For a linear block with constant parameters, exact state propagation is an
offline reference option. For a nonlinear block, compare a high-accuracy ODE or
SPICE solution against the proposed real-time discretization. Initial capacitor
states and event times are part of the input, not hidden tuning variables.

| Method | Suitable role | Main tradeoff to measure |
| --- | --- | --- |
| Reduced resonator + explicit transient stages | First audible 808 slice | Few states and clear tests; omissions must remain visible. |
| Circuit-derived state space / nodal equations | Independent circuit oracle; possibly selected real-time blocks | Strong circuit connection; stiffness, iteration and coefficient changes require care. |
| WDF | Passive networks and selected nonlinear circuit blocks | Useful physical structure; active/multiport nonlinear networks are not automatically trivial or unconditionally stable. |
| Behavioral oscillator/envelopes/shaper | Initial 909 branch model | Easy to isolate; arbitrary exponentials may miss charging, accent and loading behavior. |
| Full nonlinear reference at a high internal rate | Accuracy baseline | Expensive reference equipment; no presumption it is the first embedded implementation. |
| Sample playback / opaque learned model | Optional comparison baseline only | Does not meet the intended circuit-informed synth progression by itself. |

The WDF literature supports modeling arbitrary topologies and multiple
nonlinearities, but the RT-WDF paper is not a target-CPU performance result. Its
framework is a methodological reference, not a proposed new dependency. [S13]
Non-iterative circuit solvers offer another research option when iterative cost
is problematic; whether their assumptions apply to these active circuits must
be checked block by block. [S15]

### 4.3 Trigger discontinuities and stiff switching

Germain's 2021 paper specifically examines the 808 pulse shaper. Ordinary
trapezoidal discretization can produce a spurious falling-edge response when
the diode switches; the paper compares alternative Möbius-transform parameters
against a high-resolution ODE reference. Its reported coefficient is tied to
that experiment's sample rate and stimulus. It is not a ready-made 48 kHz
constant for this engine. [S14, §4.1][S14]

Proposed tests therefore cover the rising edge, pulse plateau and falling edge
separately. Include input amplitude extremes and finite rise/fall times. Sweep
internal rate until the reference converges before deciding that a disagreement
comes from the reduced model. Oversampling alone is not a proof of numerical
correctness, and adding a unit delay to break a nonlinear feedback loop can
change pitch, damping and transient behavior.

### 4.4 A decomposed 909 model

Use the following as a proposed test decomposition, with circuit-derived
relationships replacing placeholders as evidence improves:

    pitch control → oscillator state → triangle → nonlinear shaping → tonal VCA
    pulse + filtered continuous noise → attack VCA
    tonal branch + attack branch → output network and level

For a behavioral oscillator experiment, integrate instantaneous frequency:

    phase[n+1] = wrap(phase[n] + f[n]/Fs).

A common exploratory control law is f(t) = f_base + Δf E_pitch(t), but neither
that linear relationship nor an exponential E_pitch is assumed to be the exact
909 circuit. Trace the trigger-driven Q11/C4 oscillator reset/clamp and test
initial polarity, phase and release from the trigger pulse; steady-state
frequency alone cannot validate that path. Its exact timing remains unmeasured.
Test the CV-to-frequency relationship independently. Keep Tune's
effect distinct from a hypothetical static transpose control.

For a memoryless symmetric diode-shaper approximation, the Shockley relation
provides a physically motivated nonlinear curve. A generic tanh curve may be
fitted as a reduced approximation, but it is not itself evidence of the original
shaper. Compare fundamental amplitude, harmonic ratios and behavior over the
actual triangle amplitude range. Put the shaper and VCA in their documented
order; moving a nonlinearity across an envelope changes the sound.

### 4.5 Antialiasing and control-rate behavior

Low fundamental frequency does not make a kick alias-free. Trigger edges,
triangle corners, diode shaping and rapid coefficient changes can generate
energy above Nyquist.

Parker et al. derive antiderivative antialiasing (ADAA) for memoryless
waveshaping. For a first antiderivative F of f, the first-order form averages
the nonlinear function along the interval between consecutive inputs:

    y[n] = (F(x[n]) − F(x[n−1])) / (x[n] − x[n−1]).

Near equal inputs, a stable limiting expression is needed. ADAA changes the
effective filtering/delay and does not make an arbitrary feedback circuit
alias-free. [S10] Holters extends the discussion to stateful systems; this is
evidence that the surrounding dynamics must be considered, not permission to
insert memoryless ADAA into every feedback loop. [S12]

Proposed evaluation: compare native rate, 2× and 4× processing, extending to 8×
where necessary, against a converged high-rate reference. Account for the
decimator's delay and passband response. Oversample the smallest interacting
nonlinear subsystem that preserves the comparison; measure whole-voice cost
before choosing. No oversampling factor or alias threshold has been validated
for x0x yet.

Delivered controls are block snapshots. Interpolating raw values, physical
parameters and filter coefficients produces different trajectories. Test a
fixed parameter jump first, then a ramp and modulation sequence. Choose the
mapping based on circuit meaning and observed stability; avoid adding smoothing
on top of the OS's smoothing without measuring the combined result.

## 5. Reference VSTs and reproducible measurements

### 5.1 Select the reference before fitting the timbre

Candidate selection is an early task, not an assumed purchase or installation.
The manufacturer identifies Roland's software instruments as circuit-modeling
emulations; that claim makes them candidates, not independent proof of accuracy.
D16's products provide a separately implemented comparison. [V808], [V909], [VD16]

| Candidate | First experiment | Confounders to pin |
| --- | --- | --- |
| Roland TR-808 Software Rhythm Composer | One dry BD render, then repeated identical hits | Extra Tune/Gain, output path, total accent versus MIDI velocity, quality mode, version |
| D16 Nepheton 2 | Repeat the same small original-control experiment | Added effects/dynamics, output routing, extended parameters, demo behavior |
| Roland TR-909 Software Rhythm Composer | Dry BD, isolate Tune/Attack/Decay effects | Extra controls, accent mechanism, note mapping, mixer path, quality mode |
| D16 Drumazon 2 | Cross-check the same 909 features | Extended Pitch/Tune Depth, processing, version-specific defaults |

The archived Roland 808 plugin manual documents extra bass-drum tuning and
gain controls. Its 909 manual documents individual outputs and MIDI operation.
Those details are useful for capture setup, but the installed version must be
checked. [S32], [S34] Do not equate the middle of a plugin knob with the midpoint
resistance of an analog potentiometer.

Select one primary reference per engine based on repeatable access, isolated
outputs, known parameter state and usable stock settings. Use a second reference
for selected cross-checks if available. Record disagreements; do not average two
plugins into a fictional original. Check applicable capture/use terms during
reference selection. Keep binaries, presets and reference audio local unless
their redistribution is explicitly permitted.

### 5.2 Minimum capture record

Each reference set must identify:

- Plugin name, version/build, binary hash, format and architecture; host name and
  version; operating system; sample rate and host block size.
- Saved complete plugin state plus readable parameters. Record individual-output
  versus master-output routing, pan, gain, effects, quality and randomization.
- MIDI note/channel/velocity, note-on and note-off sample positions, transport,
  tempo and accent mechanism. Compare MIDI velocity with pattern accent rather
  than assuming they are equivalent.
- Preroll, warm-up and instance-reset procedure; elapsed time since the last hit;
  render mode; reported and observed latency; capture length and sample format.
- Original unnormalized audio, content hashes, capture script/session revision,
  and any excluded or failed runs. Verify non-silence and absence of demo mutes.

Start with one baseline setting and at least five repeats, using both a fresh
instance and an already-running one. Classify output as bit-repeatable or
variable. If variable, determine which features remain stable. Keep randomized
or free-running noise in that classification rather than hiding it through
automatic normalization or reseeding.

### 5.3 Grow a small corpus

Start with isolated hits separated by enough time to observe the full tail:

| Set | 808 | 909 |
| --- | --- | --- |
| Baseline | Stock-oriented controls and nominal accent | Same, with documented Tune/Attack settings |
| One control at a time | Decay and Tone at min/mid/max; Level sweep | Decay, Tune and Attack at min/mid/max; Level sweep |
| Accent | At least low/mid/high plus repeated baseline | Same, with amplitude and pitch paths inspected separately |
| Interactions | Decay × accent; Tone × accent | Tune × decay; Attack × accent; decay × accent |
| History | Paired hits, alternating accents and rolls | Same; preserve continuous-noise state |
| Held out | Intermediate settings and unseen sequences | Same, including mixed control corners |

Choose a sparse interaction set before a full cross-product. For history tests,
proposed inter-onset spacings are 1, 2, 5, 10, 20, 50, 100 and 250 ms, plus a
normal musical sequence. Some extremely short spacings may be unsupported by
the target event path; record that result instead of silently rounding them.
Keep offline sample-accurate event tests separate from what each device's event
path can deliver.

Freeze fit/evaluation membership and metric limits after reference repeatability
is known, before optimizing against the held-out set. Later threshold changes
need a documented reason and a rerun of the evaluation corpus.

### 5.4 Measurements and their limits

| Measurement | Detects | Required qualification |
| --- | --- | --- |
| Trigger-to-onset delay; first-cycle polarity and peak | Scheduling, reset and excitation errors | Preserve raw timing. An aligned comparison must report the applied shift. |
| Peak and fixed-window energy | Level/accent transfer | Do not normalize away gain errors. Report windows and units. |
| Log-amplitude slopes; positive/negative envelopes | Decay, asymmetry, VCA effects | Exclude the noise floor and transient region; report fit residuals. |
| Late-body frequency in cents | Tuning error | Use enough cycles and an amplitude-confidence mask. |
| Cycle periods / instantaneous-phase trajectory | Pitch sweep and sigh | Reject unreliable onset/near-zero estimates; cross-check with another method. |
| Onset/body/tail spectra and band energies | Click, harmonic shaping, noise | State window, hop, FFT length, floor and normalization. |
| Waveform residual / normalized RMS error | ASM-to-oracle numerical errors | Only strict for matched timing and deterministic inputs/noise. |
| Mean/DC, extrema, finite-state checks | Bias, clipping, instability | Check long runs and silent tails, not just one hit. |
| High-rate-reference comparison | Discretization and aliasing error | Account for anti-alias filter response and latency. |

Frequency-estimation literature explains why spectral interpolation and window
choice matter. It does not justify estimating a single stationary pitch from
the first few milliseconds of a swept kick. [S16] Test the analyzer on known
damped sinusoids and deliberate frequency, decay, gain, delay, DC and clipping
defects before using it to accept an engine. Include NaN, unexpected silence
for a known-audible fixture, truncation and incorrect channel routing as failures.
Intentional silence is valid: report its pitch and relative-error metrics as
unavailable rather than producing NaN results or rejecting the renderer.

Use blinded, randomized, level-controlled listening alongside objective results.
Include a hidden reference and a deliberately degraded control where practical.
BS.1116 is a useful methodological source; an informal developer listening
session must not be described as a compliant BS.1116 study. [S17]

**Proposed gate policy:** exact checks for identity, output coverage, deterministic
repetition and memory isolation; experimentally set numerical tolerances for
ASM/oracle agreement; reference-repeatability-based tolerances for timbre.
Do not invent a universal “inaudible” dB/cents threshold before obtaining data.
The ticket that establishes the corpus must deliver numeric tolerances and
measurement uncertainty before timbre-fitting tickets can close.

## 6. Shared models, CPU backends and device boundaries

### 6.1 Modular CPU targets

The shared definition owns circuit equations, physical parameter meanings,
trigger/retrigger policy, normalization and fidelity criteria. An independent
high-precision host renderer supplies expected behavior. The two assembly
backends own numeric formats, state representations, coefficient encodings,
rounding/saturation, approximations and instruction scheduling. They may use
different stable realizations of the same model; they must not become separately
fitted instruments.

The MCF5441x has an EMAC and no hardware FPU, making fixed point the natural
ColdFire path. Its accumulators are 48 bits; the fractional product is reduced
to 40 bits before accumulation. SHARC+ supports fixed and floating point;
float32 is a starting implementation choice, not an accuracy guarantee.
[UCF, Table 3-9 and §5.3][UCF], [S20]

Use two build-selected backend implementations per engine, with three thin C
device adapters. Share the ColdFire kernel between Digitakt and Digitone rather
than copying it into each device directory. Adapters translate firmware events,
controls and voice identity, and handle output integration. Common settings mean
the same physical values and event times, not necessarily identical raw knob
words or binary state layouts. No portable assembly translator, per-operation
dispatch layer or mandatory cross-CPU bit identity is proposed.

| Device | DSP path | Verified integration boundary |
| --- | --- | --- |
| Digitakt | ColdFire ASM | Eight track buffers, 32 Q1.31 samples each at 48 kHz; custom rendering follows sample playback and precedes overdrive. [UDT], [UDTRENDER] |
| Digitone | Shared ColdFire ASM backend | Eight voice buffers, 32 Q1.31 samples each at 48 kHz; custom rendering runs on the main ColdFire and replaces audio produced by the second FM processor. [UDN] |
| Digitone II | SHARC+ ASM | Assuming PRs 197/200, a per-voice callback supplies 32 mono float samples at 48 kHz, followed by stock processing. [UVOICE] |

Digitone's raw replacement hook overwrites audio that already contained the
stock AMP envelope. Its machine companion reapplies AMP/velocity unless
`DNM_OWN_ENV` is selected. Digitone II applies stock AMP processing downstream.
Keep the kick's intrinsic decay separate from host AMP shaping, and test each
adapter's routing explicitly. Digitone's second processor does not automatically
provide CPU time for this main-CPU custom-engine path. [UDNAMP], [UVOICE]

Code/data expansion can remove an allocation constraint but cannot establish
audio-deadline compliance. Measure CPU use, stack, state capacity and sustainable
voices on each device. No such workload measurements exist yet.

### 6.2 Conditional Digitone II baseline

The PRs were inspected while open. This research follows the user's assumption
that they will merge. Snapshots are [197 at 65cfa950][U197] and [200 at
2ab5f424][U200]; the [pinned voice documentation][UVOICE] and headers [UHEADER]
are archived locally. Development now uses the user's requested PR #200 revision
`2ab5f424c4721e4277d2112a5ae755d9938f50d6` as a pinned submodule, including its
matching header and adapter. A later merge/revision change requires revalidation;
a matching textual ABI name alone is insufficient.

| Proposed upstream behavior | Consequence for the plan |
| --- | --- |
| Digitone II OS 1.12 | DN2-specific baseline from the referenced PRs; Digitakt and Digitone use their own pinned adapters. |
| One custom SHARC synth registration/program per build | The user selected one ID-20 synth with an 808/909 selector; see the [approved saved-control contract](dn2-packaging-proposal.md). No multiple-registration extension is needed for that direction. |
| 32 mono float samples at 48 kHz | Persist audio and trigger states across calls. Block duration is 0.6667 ms, not the available execution budget. |
| Allocated slots 0–15 | State belongs to slots; never use slot as a track number. |
| Silent trigger-edge block, then START | Account for this latency separately from the acoustic attack. START is an event, not an analog pulse width. |
| 40 unsigned-8.8 parameter words, 0–32512 | Consume declared knobs only; preserve fractional values where meaningful. |
| OS applies locks, smoothing and modulation before delivery | The DSP must interpret delivered per-voice values; UI-only coefficient computation would miss this path. |
| Stock AMP/filter/pan/sends/mixer remain downstream | Compare raw kernel audio separately from end-to-end firmware output. Control the downstream path during calibration. |
| No independent accent/velocity field in the inspected input | Plan an explicit trigger-strength/accent mapping and test its relation to native velocity modulation and AMP gain. |
| Current author code 6,080 B; data 7 KiB; declared stack ≤128 B | Report usage and measured stack/runtime. If inadequate, create a concrete upstream allocation dependency; preserve the sound-quality target. |

The current allocation is not the DSP's total capacity. Likewise, package
validation is not a proof of instruction safety, actual stack use or deadline
compliance. ADI's data sheet and optimization note explain the architecture and
memory/cache costs; they do not measure this firmware workload. [S20], [S22]

The current voice header changes from the earlier PR while retaining the ABI
name. Match the header, adapter and packaging implementation by revision/hash.
The pinned upstream documentation also describes a Selache negative-immediate
shift encoding defect. Verify generated instruction encodings independently
and follow the validated upstream workaround; emulator success alone does not
rule out an illegal instruction on silicon. [UVOICE]

### 6.3 Independently runnable tests

| Layer | Inputs | Test result it owns | Does not require |
| --- | --- | --- | --- |
| C page/control tests | Each device's native-service fakes and a fake DSP-facing receiver | Labels, defaults, declared/empty slots, stock-control semantics and value mapping | A working sound engine or physical device |
| Mathematical oracle tests | Explicit event/parameter fixtures and initial states | Analytic checks, circuit behavior and discretization comparisons | UI or firmware |
| ASM kernel tests | Shared logical fixtures adapted to each CPU's actual instruction harness | Actual assembled output, ABI preservation, state bounds, numeric failures and oracle residuals | Native pages or knob input |
| Cross-CPU comparison | Raw ColdFire/SHARC output for identical physical settings, state and timed events | Pitch, decay, onset, gain and deterministic waveform agreement within established tolerances | Device UI or matching binary arithmetic |
| Parameter transport integration | Each device's real native controls into its diagnostic ASM kernel | Correct per-voice values after locks/modulation and correct event translation | Completed kick timbre or another device adapter |
| Firmware/audio integration | One device/engine cell, known stock downstream configuration | Real routing, onset, controls, persistence and coexistence | Completion of the other five cells |
| Physical qualification | Exact firmware on target hardware with timing/audio capture | Device operation and measured worst-case deadlines | A claim of original Roland hardware fidelity |

These are separate test entry points, not separate new frameworks. Reuse existing
upstream fixtures and emulator facilities where they fit. Tests must consume
the production C declarations and assembled instructions, not duplicate their
behavior in a mock and call that tested.

Each CPU backend must pass against the independent oracle before pairwise
agreement is accepted; two implementations can share an error. Exercise long
tails, parameter extremes, rapid retriggers, state reset, interleaved voices,
fixed-point overflow/limit cycles and floating-point non-finite values. Use
fixed-seed noise for repeatable kernel tests and statistical comparisons for
independently phased reference noise. Compare raw kernels separately from
device AMP/filter/mixer output. Instruction execution evidence does not establish
physical worst-case timing.

### 6.4 Parameter semantics to decide before persistence

The research intentionally does not assign permanent machine IDs or a saved
parameter layout. Those choices affect persisted sounds and need a concrete
review before becoming stable.

The first mapping should cover the original control set and a clearly defined
accent/trigger-strength mechanism. In stock mode, ordinary MIDI note changes
must not silently turn the 808 into a chromatic bass instrument. Likewise,
909 Tune must not be redefined as static semitone tuning. Decide how unused
native pitch/modulation behavior is handled and test it.

All three devices require the combined mod and saved MODEL selector. DN2 has
an approved exact layout and standalone C reference-policy tests; revised
combined DT/DN layouts remain proposals. Transition semantics still require
native/DSP integration tests:
quantization of a smoothed value, whether model changes apply at the next trigger,
and which old states are cleared. Do not let interpolation accidentally blend
two engines or reinterpret a saved value mid-note. The approved rule quantizes
at raw 16384, latches at START and clears the old model's tail on a model change;
same-model retrigger and native ownership remain separate work.

The eventual contract review should distinguish reset, fresh trigger, same-voice
retrigger, voice reassignment, silence and model change. Do not introduce a
public API, generated schema or persisted format without review. DN2's exact
saved-control layout has that user approval; DT/DN layouts remain proposals.

### 6.5 Retrigger and shared-state constraints

The original instruments each have one bass-drum circuit with residual analog
state. The inspected DN2 callback provides a slot and START but no track identity
or distinct retrigger event. Preserving old state blindly can import another
track's history; resetting everything blindly can erase the behavior being
modeled. Verify each device's allocator and monophonic behavior early; do not
assume Digitakt tracks, Digitone voices and DN2 slots are interchangeable.
A faithful repeated-hit mode may need an upstream signal or a documented
voice-allocation policy.

Fresh-hit fidelity can progress independently. Keep repeated-hit fidelity an
explicit later gate with a real dependency if needed, not an undocumented
shortcut. For the 909, continuous noise also needs a scheduling decision: its
state must not run faster with more allocated voices or be reset unintentionally
at every hit.

## 7. Proposed incremental delivery sequence

This is the research-to-backlog ordering, not a set of completed experiments.
The [implementation plan](implementation-plan.md) links the concrete issues and
their dependencies. Each implementation ticket has one inspectable output,
explicit prerequisites, independent tests and a small integration observation
when it changes the working sound.

1. **Reference and measurement foundations:** select reproducible stock-oriented
   VSTs, prove the analyzer with known defects, and establish each instrument's
   capture corpus and tolerances before timbre fitting. These can run alongside
   infrastructure work.
2. **Shared contract and fixture design:** define physical controls, event times,
   reset/retrigger semantics, state ownership and expected output. Pin each
   device's upstream interface in its own adapter work. Review numeric and ABI boundaries before
   committing production interfaces or persisted layouts.
3. **CPU harnesses and device proofs:** establish reproducible builds and actual
   instruction tests for ColdFire and SHARC+ independently. Give each device its
   C adapter tests and silent/diagnostic transport integration. Verify one control
   and one trigger through that device before adding its kick engine.
4. **First 808 body on both CPUs:** derive one analytically checked body oracle;
   implement the ColdFire and SHARC+ forms against it and compare raw outputs.
   Integrate early on at least one ColdFire device and DN2, then connect the other
   ColdFire adapter to the same kernel. Expose numeric and CPU-cost problems
   while this slice is small, before committing to expensive full models. This
   is a scheduling priority, not a gate on another device's progress.
5. **Advance each ready cell in small slices:** for the 808, add decay, excitation,
   attack/sigh behavior and tone/output separately. For the 909, add the triangle
   oscillator/shaper, pitch/CV, tonal envelope/VCA and noise/pulse attack branch
   separately. Reuse the shared oracle work and CPU/engine kernels, while testing
   each device's control mapping and audible integration for every relevant slice.
6. **Qualify each cell independently:** accumulate reference fidelity, accent,
   retrigger/history, save/reload, coexistence, aliasing, code/data/stack use and
   physical timing evidence. Cross-CPU comparison supplies additional evidence
   when both matching slices exist; an unavailable peer does not block an otherwise
   passing cell. It replaces neither oracle tests nor device qualification.

The active delivery matrix is:

| Device | 808 cell | 909 cell | Shared DSP implementation |
| --- | --- | --- | --- |
| Digitakt | DT + 808 | DT + 909 | ColdFire 808 and ColdFire 909 |
| Digitone | DN + 808 | DN + 909 | The same ColdFire 808 and ColdFire 909 |
| Digitone II | DN2 + 808 | DN2 + 909 | SHARC+ 808 and SHARC+ 909 |

A cell starts when its shared contract/tests, CPU harness and device adapter
are ready, plus the prerequisites of its next engine slice. It does not wait for
unrelated device adapters or another cell's complete engine. Likewise, a shared
kernel change needs regression checks in both ColdFire consumers without making
their device-specific work a single inseparable ticket. Start with 808 feasibility;
909 work does not require full qualification of all three 808 cells.

The scaffold includes C control boundaries, diagnostic ASM, host test tools,
latest-only SDK builds and accepted installed silent mods on all three devices.
C controls and actual ASM remain independently testable. The DN delivered-control
gap investigated in superseded #75 is resolved for the installed mod in #40;
the DT reset bug is deferred to #78. The [development guide](development.md)
records current evidence boundaries.
The first uncalibrated [808 body](808-body.md) is audible on all three emulators;
the complete kick circuits remain future work. The issue backlog uses engine
labels **808** and **909**,
device/CPU labels and explicit blocking relationships. Shared work may carry
both engine labels. UI, DSP, reference, test and integration work remain
identifiable independently. Digitakt II has no active cell or delivery dependency.

The [source/code alignment audit](reference-alignment.md) records the current
#79 baseline: archived MIT Plaits code is useful for inspecting an 808 model,
while its synthetic drum is only 909-like and does not replace the original
909 schematic. This inspected-code evidence does not imply a compiled reference,
measured comparison or faithful circuit implementation.

## 8. Open questions and research limits

- Which installed VST versions give controllable, reproducible stock-oriented
  baselines? No candidate was installed, licensed or rendered in this work.
- What are the agreed numeric fidelity gates after reference repeatability is
  measured? A visually similar waveform is not a sufficient acceptance rule.
- Which original 909 circuit revision and pot curves should define the nominal
  model? The schematic is stronger evidence than generalized sound descriptions.
- Can each device's native voice policy express original monophonic retrigger
  history without state leakage between tracks? This needs an early experiment.
- On DN2, will two models share one registered program, use separate builds, or
  depend on expanded upstream registration? Do not treat memory expansion as
  proof that this separate registration constraint has disappeared.
- Which nonlinear blocks need oversampling or a different discretization? There
  is no measured x0x CPU, aliasing, memory or stack result yet. What fidelity and
  voice count can each device sustain, especially the main-CPU ColdFire paths?
- What exact original-component substitutions matter audibly? Neither modern
  datasheets nor matching a published SPICE model settle that question.

The 808 has directly applicable peer-reviewed modeling literature. This search
did not verify a peer-reviewed paper deriving a complete 909 BD digital model;
that is a search limit, not proof that none exists. The Padua thesis [L01] is an
unread full-text lead, not evidence for any equation here. Erica/Moritz Klein's
guide [S35] and Tiptop's manual [S36] are useful derivative-circuit explanations,
not stock 909 calibration sources.

The initial research performed no circuit simulation, audio capture, ASM execution,
firmware flash or hardware timing test. Subsequent synthetic tests and bounded
assembly execution are recorded in the [development guide](development.md).
VST captures, complete kick models and physical qualification remain open.

## 9. Annotated bibliography and archive map

Page numbers below are printed pages unless identified as PDF pages. For the
Werner dissertation, printed Arabic page +18 equals the one-based PDF page.
The local archive manifest distinguishes successful downloads from failed
downloads and web-only reads; a URL in this bibliography is not a claim that its
PDF was successfully saved.

| ID | Source and relevant location | Local source filename / status |
| --- | --- | --- |
| [S01] | Roland, TR-808 Service Notes, 1981/1983; pp.4–5 trigger/BD explanation, pp.8–9 legend/schematic | roland-tr808-service-notes.pdf |
| [S02] | Roland, TR-909 Service Notes, 15 June 1984; pp.2–6 parts/control/block/noise, p.9 traces, p.11 BD schematic | roland-tr909-service-notes.pdf |
| [S03] | Werner, Abel, Smith, DAFx-14, pp.159–166; PDF pp.3–7 modeling/results | werner-2014-tr808-bass-drum.pdf |
| [S04] | Werner, Stanford dissertation, 2016; pp.81–89 output, 122–128 resonator, 140–145 pulse, 166–178 envelope/nonlinear core, 181–188 full model, 205–207 simplified output | werner-2016-dissertation.pdf |
| [S05] | Whittle, TR-909 Sound Modifications, 10 October 2018; pp.2–3 and original BD schematic p.12 | whittle-tr909-sound-mods.pdf |
| [S06] | Wiltshire / Electric Druid, A look at the TR-909's noise generator, 2019/2020; shift-register/clock/startup sections | electric-druid-909-noise.html |
| [S10] | Parker, Zavalishin, Le Bivic, DAFx-16, Reducing the Aliasing of Nonlinear Waveshaping Using Continuous-Time Convolution, §§2–4 | parker-2016-adaa.pdf |
| [S11] | Bilbao, Esqueda, Parker, Välimäki, IEEE SPL 24(7), 1049–1053, 2017; DOI 10.1109/LSP.2017.2675541 | Web-read; PDF download failed |
| [S12] | Holters, DAFx-19, Antiderivative Antialiasing for Stateful Systems, §§2–3 | holters-2019-stateful-adaa.pdf |
| [S13] | Rest, Dunkel, Werner, Smith, DAFx-16, RT-WDF—A Modular Wave Digital Filter Library with Support for Arbitrary Topologies and Multiple Nonlinearities, §§2–4 | rest-2016-rt-wdf.pdf |
| [S14] | Germain, DAFx-20in21, Practical Virtual Analog Modeling Using Möbius Transforms, §4.1 / PDF pp.4–5 | germain-2021-integration.pdf |
| [S15] | Ducceschi, Bilbao, Webb, DAFx-20in21, Non-Iterative Schemes for the Simulation of Nonlinear Audio Circuits, §§1–2 and circuit examples | ducceschi-2021-noniterative.pdf |
| [S16] | Werner, Germain, Applied Sciences 6(10), 306, 2016; Sinusoidal Parameter Estimation Using Quadratic Interpolation around Power-Scaled Magnitude Spectrum Peaks; DOI 10.3390/app6100306 | werner-germain-2016-frequency.pdf |
| [S17] | ITU-R BS.1116-3, February 2015; subjective assessment of small audio impairments | itu-bs1116-3.pdf |
| [S20] | ADI ADSP-21562/3/5/6/7/9 Data Sheet Rev. D, June 2023; architecture/memory | adsp-2156x-datasheet.pdf; distributor mirror |
| [S21] | ADI SHARC+ Core Programming Reference Rev.1.5, June 2023 | Web-read; direct PDF download failed |
| [S22] | ADI EE-412 Rev.2, 2019; processor-system optimization | Web-read; direct PDF download failed |
| [S23] | Renesas UPC258/UPC4558, R03DS0145EJ0200 Rev.2, 2025; electrical table p.3 | upc4558-datasheet.pdf |
| [S24] | NEC/Renesas 2SA733, D10868EJ7V0DS00, 2004; electrical data and curves | 2sa733-datasheet.pdf |
| [S25] | NEC/Renesas 2SC945A, D17117EJ3V0DS00, 2005; related later part | 2sc945a-datasheet.pdf |
| [S26] | Mitsubishi M5218AL/P/FP; later variant despite download URL | m5218l-datasheet.pdf |
| [S27] | Mitsubishi 2SC2603; ratings, F gain grade and curves | 2sc2603-datasheet.pdf |
| [S28] | ROHM 1SS133 Rev.C; pp.1–2 characteristics | 1ss133-datasheet.pdf |
| [S29] | TI/Harris CD4006B, SCHS017; stage layout and clock behavior | cd4006b-datasheet.pdf |
| [S30] | Roland TR-808 Owner's Manual; sound controls/specifications | roland-tr808-owner-manual.pdf |
| [S31] | Roland TR-909 Owner's Manual; sound controls p.8 | roland-tr909-owner-manual.pdf |
| [S32] | Roland TR-808 Software Rhythm Composer manual; main window and extra PANEL controls p.3 | roland-cloud-tr808-manual.pdf |
| [S33] | Mitsubishi General Purpose ICs Data Book, 1984; M5218L/P section 2-45–2-49, PDF pp.86–90 | mitsubishi-1984-data-book.pdf |
| [S34] | Roland TR-909 Software Rhythm Composer manual; controls, outputs and MIDI | roland-cloud-tr909-manual.pdf |
| [S35] | Erica Synths / Moritz Klein, FM Drum guide, 2025; 909-style VCO, waveshaper, VCA and attack explanations | erica-fm-drum.pdf; deliberately a derivative |
| [S36] | Tiptop Audio, BD909 manual, pp.2–3 | tiptop-bd909-manual.pdf; deliberately a derivative |
| [S37] | Mitsubishi 2SA1115; D/E/F/G grades, original Roland parts list specifies F | 2sa1115-datasheet.pdf |
| [S38] | Nexperia/NXP 1N4148/1N4448; published-model substitute, not original 1S2473 | Located; PDF download failed |
| [S39] | onsemi 2N3904; published-model substitute, not original 2SC945 | 2n3904-datasheet.pdf |
| [S40] | D16 Nepheton 2 manual; capture setup and processing controls | d16-nepheton2-manual.pdf |
| [S41] | D16 Drumazon 2 manual; capture setup and processing controls | d16-drumazon2-manual.pdf |
| [U197] | Elekloader PR 197, inspected head 65cfa95089fae9daf8ac57dc2d04e051ad8da067 | upstream/pr-197.json |
| [U200] | Elekloader PR 200, inspected head 2ab5f424c4721e4277d2112a5ae755d9938f50d6 | upstream/pr-200.json; matching voice docs/headers |
| [UCF] | NXP MCF5441x Reference Manual Rev.5, May 2018; Table 3-9 FPU/EMAC configuration, §5.3 EMAC precision | Web-read for CPU comparison; not archived |
| [UDT], [UDTRENDER] | Elekloader at c150ac583a4b7e6d64680d5592f4a40f409193f7; Digitakt buffer and render-event contracts | Inspected source links; not archived |
| [UDN], [UDNAMP] | Elekloader at c150ac583a4b7e6d64680d5592f4a40f409193f7; Digitone main-CPU custom rendering and AMP ownership | Inspected source links; not archived |
| [L01] | Fortuna, University of Padua, 2024/25, Studio, simulazione e progettazione di una drum machine | Abstract lead only; full thesis not obtained |

Original-source links:

[S01]: https://www.florian-anwander.de/roland_tr808/roland_TR-808_service-manual.pdf
[S02]: https://www.polynominal.com/site/studio/gear/drum/roland-tr909/roland-tr909-service-manual.pdf
[S03]: https://dafx.de/paper-archive/2014/dafx14_kurt_james_werner_a_physically_informed%2C_ci.pdf
[S04]: https://stacks.stanford.edu/file/druid:jy057cz8322/KurtJamesWernerDissertation-augmented.pdf
[S05]: https://www.firstpr.com.au/rwi/tr-909/TR-909-Sound-Mods.pdf
[S06]: https://electricdruid.net/tr-909-noise-generator/
[S10]: https://www.dafx.de/paper-archive/2016/dafxpapers/20-DAFx-16_paper_41-PN.pdf
[S11]: https://aaltodoc.aalto.fi/items/470aab15-1702-4ccf-a148-24e6173079fb
[S12]: https://www.dafx.de/paper-archive/2019/DAFx2019_paper_4.pdf
[S13]: https://dafx.de/paper-archive/2016/dafxpapers/40-DAFx-16_paper_35-PN.pdf
[S14]: https://www.dafx.de/paper-archive/2021/proceedings/papers/DAFx20in21_paper_43.pdf
[S15]: https://mdphys.org/PDF/dafx_2021_NIT-VA.pdf
[S16]: https://www.mdpi.com/2076-3417/6/10/306
[S17]: https://www.itu.int/rec/R-REC-BS.1116-3-201502-I/en
[S20]: https://www.analog.com/media/en/technical-documentation/data-sheets/adsp-21562-21563-21565-21566-21567-21569.pdf
[S21]: https://www.analog.com/media/en/dsp-documentation/processor-manuals/sc58x-2158x-prm.pdf
[S22]: https://www.analog.com/media/en/technical-documentation/application-notes/ee412v02.pdf
[S23]: https://www.renesas.com/en/document/dst/upc258-upc4558-datasheet
[S24]: https://www.renesas.com/en/document/dst/2sa733-data-sheet-d10868ej7v0ds00
[S25]: https://www.renesas.com/en/document/dst/2sc945a-data-sheet-d17117ej3v0ds00
[S26]: https://www.datasheets.com/mitsubishi/m5218l/datasheet.pdf
[S27]: https://www.myon98.net/memo/datasheet/2sc2603.en.pdf
[S28]: https://www1.futureelectronics.com/doc/ROHM/1SS133T-72.pdf
[S29]: https://www.ti.com/lit/gpn/CD4006B-MIL
[S30]: https://cdn.roland.com/assets/media/pdf/TR-808_OM.pdf
[S31]: https://cdn.roland.com/assets/media/pdf/TR-909_OM.pdf
[S32]: https://www.rolandcloud.com/getattachment/29827606-079c-4cf0-9777-e81ef9769868/TR-808-Manual-E.pdf
[S33]: https://ftpmirror.your.org/pub/misc/bitsavers/components/mitsubishi/_dataBooks/1984_Mitsubishi_General_Purpose_ICs.pdf
[S34]: https://www.rolandcloud.com/getmedia/a88fc05f-0b9f-4ba2-8266-b2272ba31572/TR-909-Manual-E.pdf?ext=.pdf
[S35]: https://www.ericasynths.lv/service/file/download/product_id/796/file_id/585/
[S36]: https://www.tiptopaudio.com/manuals/Tiptop_Audio_BD909_ns.pdf
[S37]: https://elparts.mekweb.eu/ds/2SA1115-G.pdf
[S38]: https://assets.nexperia.com/documents/data-sheet/1N4148_1N4448.pdf
[S39]: https://www.onsemi.com/pdf/datasheet/2n3904-d.pdf
[S40]: https://d16.pl/pub/manuals/Nepheton%202-manual-gb.pdf
[S41]: https://d16.pl/pub/manuals/Drumazon%202-manual-gb.pdf
[U197]: https://github.com/irpina/elekloader/pull/197
[U200]: https://github.com/irpina/elekloader/pull/200
[UVOICE]: https://github.com/simonjohansson/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/docs/MACHINES-DN2-VOICE.md
[UHEADER]: https://github.com/simonjohansson/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/elekloader/sdk/include/digitone-mk2/voice.h
[UCF]: https://www.nxp.com/docs/en/reference-manual/MCF54418RM.pdf
[UDT]: https://github.com/irpina/elekloader/blob/c150ac583a4b7e6d64680d5592f4a40f409193f7/elekloader/sdk/include/digitakt-mk1/core3.h#L17-L24
[UDTRENDER]: https://github.com/irpina/elekloader/blob/c150ac583a4b7e6d64680d5592f4a40f409193f7/docs/ADAPTING.md#L1115-L1120
[UDN]: https://github.com/irpina/elekloader/blob/c150ac583a4b7e6d64680d5592f4a40f409193f7/docs/ADAPTING.md#L1747-L1770
[UDNAMP]: https://github.com/irpina/elekloader/blob/c150ac583a4b7e6d64680d5592f4a40f409193f7/docs/ADAPTING.md#L1824-L1839
[V808]: https://www.roland.com/global/products/rc_tr-808/
[V909]: https://www.roland.com/global/products/rc_tr-909/
[VD16]: https://d16.pl/manuals
[L01]: https://hdl.handle.net/20.500.12608/92498
