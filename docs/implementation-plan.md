# Implementation plan: one combined mod, silent first

The silent-first priority set on 26 October 2026 is complete: all three native
mod milestones are accepted, with the DT reset bug deferred to #78. In #9, the
[first audible 808 body](808-body.md) now runs in all three emulators. It is a
provisional damped sine, now with [settled pitch calibrated to 47.65 Hz](808-pitch.md).
Live Decay uses a [reference-informed three-point range](808-decay.md),
with actual CPU and native-control checks. This remains a provisional mapping. The existing
[source-derived Tone RC filter](808-tone.md) also passes both CPU and all three
native integration checks, with provisional knob mapping. The
[C47/VR4 coupling RC](808-coupling.md) is also integrated and tested on all three
devices, fixed internally at full level; native track level still controls
volume. A [nominal 1 ms rectangular excitation](808-excitation.md) now replaces
the instantaneous oscillator reset; edge shaping and physical forcing remain
provisional. Current component and native functional checks pass. Full acceptance still
retains known DT resets in #78 and the DN silence-baseline gate in #20.

#25 now adds the first unshaped [909 triangle body](909-body.md) to those same
mods. Its fixed pitch and START phase remain provisional audition values;
live Decay now uses unloaded C8/VR5/R58 with a provisional resistance-linear taper.
The source baseline establishes the triangle topology, not a faithful complete
909. Shaping and the remaining stock control/envelope circuits follow as integrated increments.
Actual 909 audio is captured on all three devices. A separate late DN2 T2
MODEL edit did not reach a 909 START; [#80](https://github.com/simonjohansson/x0x/issues/80)
owns that native transition. Probes show the immediate CC does not survive into
T2's stored MODEL, and the selector correctly follows the delivered 808 value.
Tracing native CC handling versus STOP cleanup is still needed. The successful
saved-909 T1 capture does not close this failed path. A one-PCM16-count DN
baseline between captures is separately retained as a failed acceptance check
in #20. Historically, the finite-excitation build passed DN's complete scenario and
all three exact-zero baselines. The later pitch build reproduced the one-count
residue; changing waveforms does not establish a general fix. Keep #20 open.
DT retains only #78 and DN2's tested scenario passes. These gates do not block
independent engine work.

The product remains one mod per device containing 808 and 909 behind a saved
per-sound/track MODEL selector. Different tracks/voices can select different
models in the same build. Digitakt II is outside scope. C owns UI/plumbing;
ColdFire ASM serves DT/DN and SHARC+ ASM serves DN2. The
[render contract](render-contract.md) and [research](kick-drum-research.md) retain
the behavior and circuit details.

## The working backlog

Eight consolidated issues replaced the previous 66; #78 records the deferred DT
reset bug, #79 owns reference-model/schematic alignment, and #80 investigates
the newly observed late DN2 MODEL transition. Small increments
are commits and checklist steps inside these issues, rather than a ticket for
every control, model stage, CPU implementation and matrix cell.

| Order | Issue | Deliverable |
| --- | --- | --- |
| Track | [#1](https://github.com/simonjohansson/x0x/issues/1) | Roadmap and milestone status |
| Done, reset bug deferred | [#39](https://github.com/simonjohansson/x0x/issues/39) | Digitakt: select and exercise the silent combined mod in digiemu |
| Done | [#40](https://github.com/simonjohansson/x0x/issues/40) | Digitone: select and exercise the silent combined mod in digiemu |
| Done | [#7](https://github.com/simonjohansson/x0x/issues/7) | Digitone II: select and exercise the silent combined mod in Digikit |
| In progress | [#9](https://github.com/simonjohansson/x0x/issues/9) | Implement the 808 on both CPUs and integrate each increment into working mods |
| In progress | [#25](https://github.com/simonjohansson/x0x/issues/25) | Implement the 909 on both CPUs alongside the 808 in those same mods |
| Investigating | [#80](https://github.com/simonjohansson/x0x/issues/80) | Immediate post-STOP CC does not survive into the stored MODEL; trace native CC/store handling before assigning SDK/firmware/emulator responsibility |
| Alongside engines | [#79](https://github.com/simonjohansson/x0x/issues/79) | Align both engines with sources; initial 808 VST diagnostic now prioritizes missing stages |
| Deferred by user | [#78](https://github.com/simonjohansson/x0x/issues/78) | Digitakt native reset defaults; fix upstream in Elekloader and consume here |
| Initial five-setting 808 comparison complete; fidelity open | [#2](https://github.com/simonjohansson/x0x/issues/2) | Fixed-level reference corpora; both-model fidelity comparisons remain open |
| After sound | [#20](https://github.com/simonjohansson/x0x/issues/20) | Combined-mod emulator regression and readiness review |

The three silent device issues are closed. The 808 engine in #9 is underway:
the basic body is integrated and audible on all three devices' emulators. The DT reset
correction in #78 remains deferred. The [initial five-setting 808 comparison](808-reference-baseline.md)
in #2 is complete; pitch/Decay calibration now uses the training recordings; full fidelity remains unqualified. Use
subagents for non-overlapping work when authorized; one blocked device does
not stop useful work on another device.

## First milestone: silent mods in all three emulators

Each device issue owns the same short, end-to-end acceptance scenario:

- Build the latest supported firmware with one registered `X0X KICKS` machine;
  boot it in the required emulator and select it using the native machine UI.
- Show TNTUN, DECAY, ATTK and MODEL with their approved defaults. Verify
  each control reaches the actual render callback. ATTK is ignored in 808 mode.
- Exercise a native sequencer p-lock and one ordinary LFO assignment, including
  MODEL selection at the next delivered START. Check two tracks selecting
  different models and that changing one track leaves the other alone.
- Execute the real ASM callback and write zero to every owned output sample.
  Trace callback entry, delivered values and selected model: silence alone is
  not evidence that the callback ran. Preserve unrelated stock-track audio.
- Save/reload a sound or kit and retain MODEL and control values. Keep C control
  tests and direct ASM tests independently runnable.

There is no oscillator, reference capture or timbre target in this milestone.
Use the existing SDK registration, native controls and test runners. Do not add
another generic harness or invent a public transport API. Fix concrete failures
encountered by this scenario; do not exhaust every combination of controller,
LFO, MIDI source, tail history or allocation before trying the installed mod.
Existing tests stay, but adding more edge-case coverage is not the priority.

### Current starting points and blockers

| Device | Useful evidence already available | Work still needed for this milestone |
| --- | --- | --- |
| DT, OS 1.54 | Real ID80 mod boots; selection defaults, native controls, p-lock/LFO, save/reload, mixed models and silent owned output pass | Native knob/page reset still restores stock defaults; deferred to #78 when the user accepted #39 |
| DN, OS 1.44 | Silent milestone passes: native controls/screen, p-lock/LFO, save/reload, mixed tracks and owned output | Actual kick models and broader qualification follow in #9/#25/#20 |
| DN2, OS 1.12 | Silent milestone passes: native controls, p-lock/LFO, persistent project reload, mixed tracks and stock audio | Actual kick models and broader qualification follow in #9/#25/#20 |

The user explicitly approved the combined DT/DN saved layouts on 26 October:
ID 80 `X0X KICKS`. The subsequently approved compact layout on all three
devices is A TNTUN=64, B DECAY=64, C ATTK=64, F MODEL=0; D/E/G/H blank.
There is no x0x LEVEL knob: native track level handles volume and the renderer
uses fixed internal output calibration. DT uses SRC and DN uses SYN2. See the
[DT contract](dt-controls-proposal.md) and [DN contract](dn-controls-proposal.md)
for exact native slots. [DN2 ID 20 and its layout](dn2-packaging-proposal.md)
remain approved. MODEL changes latch at the next START and clear only that
voice's old model state. The DN-only endpoint policy is also already approved.
Approval is not a claim that native defaults or save/reload have passed.

DN2's complete reset-table input is now recovered from the supplied working
example and coupled boot passes. The [setup record](development.md#coupled-dn2-setup-blocker)
documents the exact manual revision and ordinary upstream emulator startup.
The mod has no special boot requirement or boot shim. DN's known strict
emulator failure remains recorded; the first milestone may use the working
standard non-strict configuration, labelled accurately.

## Add sound without another integration project

The first #9 increment supplies an analytically checked fixed 808 body on both
CPUs and native audio captures from every device. Live Decay and the passive
Tone and C47 coupling RC stages and the finite rectangular drive are implemented.
Settled pitch and short/default/long Decay now have training-reference calibration.
The first [initial-frequency switch](808-initial-pitch.md) now follows the
source pole ratio for a nominal 6 ms window. Next derive the companion C39
retrigger/forcing and pulse shaper, followed by nonlinear pitch sigh, stock
feedback/pot response and loaded output as small commits.
Each ready increment runs through the already-installed mod. #25 is underway
with the unshaped triangle and live unloaded RC Decay; diode shaping, body/tune,
complete VCA/envelope and pulse/noise
attack follow. Keep the same registration and
saved controls throughout; both models must coexist, not become separate mods.

Get the engines working before performance tuning. Instruction counts are
informational; there is no per-callback instruction budget. Test watchdogs catch
hangs, while measured workload/performance qualification comes later.

[#79](https://github.com/simonjohansson/x0x/issues/79) makes the source-to-code
alignment explicit: inspect published reference implementations and primary
schematics, choose each stock circuit baseline, audit provisional/missing stages,
and correct the engines incrementally in #9/#25. Reference recordings are now
available: use the training settings to prioritize and calibrate each increment
while retaining circuit-model gaps. #2 owns broader and held-out fidelity
validation; source alignment is not a reason to postpone all measurements. The
[first source/code audit](reference-alignment.md) pins the available reference
code, selects schematic baselines and records the missing/provisional blocks.
The first source-derived slice implements the 808 Tone RC network on both CPUs,
checked against an independent capacitor voltage/current reference. Its native
knob taper remains provisional. The 1 ms drive duration is implemented; pulse
shaping, the full feedback network and
the other circuit rows remain open. The pinned Plaits classes now have
[executable host renders](reference-renders.md), including deterministic repeated
captures, control changes, retained retrigger history and sanitized builds.
Their control/gain mappings are not stock calibration, and this host evidence
does not qualify production ASM or native firmware.

Build each instrument increment around one independent high-precision model and
two actual ASM implementations. Reuse the existing analyzers, fixtures and CPU runners. Compare
each backend to that model and compare matching outputs across CPUs. Record
bounds, fixed-point overflow/limit cycles, floating-point stability and state
isolation as part of the engine issue. Initial research-based sound is explicitly
uncalibrated until #2 reference comparisons pass.

The six device/model combinations remain rows in the integration results, not
six issue trees. #20 checks the accumulated mixed-model, persistence, routing,
retrigger/lifecycle and declared workload results. It must not become the first
time the engines are integrated. Hardware timing and real-device qualification
are outside this emulator-only phase and are never inferred from emulator passes.

## Consolidation and evidence

The following unfinished issues are closed as **superseded / not planned**, not
completed. Their historical bodies and evidence remain available; their work is
owned by the surviving issue's checklist.

| Surviving issue | Superseded issues |
| --- | --- |
| #1 | #58, #62, #66, #70, #72, #74 |
| #39 | #55, #59 |
| #40 | #63, #67, #75 |
| #9 | #10–18, #41–46, #51, #56, #64, #71 |
| #25 | #26–33, #47–50, #53, #60, #68, #73 |
| #2 | #8, #19, #21, #22, #34, #52, #54 |
| #20 | #35, #57, #61, #65, #69 |

Previously completed foundation issues remain completed: #3–6, #23–24,
#36–38 and #76–77. The [development guide](development.md) retains their
commands and the distinctions between host, component, native-routine and
full-OS evidence. Historical issue links there are provenance, not the current
work queue.

Use mise, pinned Elekloader PR #200, digiemu for DT/DN and Digikit for DN2.
Only the [latest supported firmware](../firmware/README.md) is in scope.
Commit small increments directly to main and push, with evidence on the owning
issue. Do not close a milestone on partial proof or widen tolerances to conceal
failures. Other stable API or saved-layout changes still require review.

## Initial 808 reference diagnostic — 27 October 2026

[#2](https://github.com/simonjohansson/x0x/issues/2) now compares the current
808 ASM at the default and four Tone/Decay corners, using fifteen verified
fresh software-reference takes. The [baseline report](808-reference-baseline.md)
links the portable HTML with plots and audio, measured differences and limitations.
ColdFire and SHARC agree within 8.122e-7 FS; both differ substantially from the
software reference. This is raw component output, not a fresh native-OS test.

Prioritize #9/#79's source-derived resonator/pitch path, then Decay feedback and
knob mapping, then attack shaping/loaded Tone-output stages and global scaling.
The reference default is 47.64 Hz with a 143 ms descriptive decay fit;
the initial x0x baseline was 55 Hz / 250 ms. That diagnostic did not change DSP;
the subsequent settled-pitch correction is recorded below. The full grid,
held-out validation, strength/history/live-control comparisons, aliasing and
blind listening remain open in #2. Keep held-out recordings unused while making
model decisions; these five settings do not freeze a fidelity tolerance.

## Settled 808 pitch — 27 October 2026

The [47.65 Hz body calibration](808-pitch.md) in #9/#2 replaces the provisional
55 Hz rotation on both CPUs. This is one settled-body target from the five
training settings, not the complete initial pitch path or circuit alignment.
The default raw waveform residual roughly halves; both long-corner residuals
get slightly worse and remain recorded mismatches. Native DT/DN/DN2 audio has the
new pitch; DT still fails known #78 resets and DN reproduces the historical
one-count silence gate in #20. DN2 passes its tested native scenario with no
halt/missing blocks. The original HTML report remains unchanged.

Keep #9/#79 open for initial pitch/forcing, stock Decay feedback/control curves,
loaded Tone/output stages and faithful retrigger. The subsequent Decay increment
corrects the coarse range; the full curve remains unqualified. Full-grid/held-out fidelity and #80 stay open. Component
precision does not qualify reference or native acceptance gates.

## Reference-informed 808 Decay — 27 October 2026

The next existing #9/#2 increment replaces the excessive Decay range with
[three reference-informed anchors](808-decay.md) on both CPUs: raw body
33.3/143/366 ms, giving composed output fits near 29/143/367 ms at fixed Tone.
The three training anchors and five-setting comparisons are separate from
held-out validation. The two-segment radius curve remains approximate at
interior positions and does not implement the stock feedback shelf/pot.

Continue the existing model work, not new features or ticket trees: initial
excitation/pitch, stock feedback/control mapping, loaded output and retrigger.
The HTML stays unchanged at the user's request. Keep emulator/component, native
control/audio and reference-fidelity evidence separate, with #78/#20/#80 open.

The Decay increment passes both CPU suites and all three native functional
scenarios. DT retains only #78 resets; DN currently passes all zero baselines
without resolving its historical #20 failure; DN2 passes with no halt/missing
blocks. All five raw reference residuals improve. The dark/short fit still
differs (29.4 vs 25.4 ms), and interior knob positions remain approximate.
Keep those in #9/#2/#79 while proceeding with the missing initial pitch/forcing
and stock feedback/control model. See [current evidence](808-decay.md).

## Initial 808 frequency switch — 27 October 2026

The next #9/#79 slice adds a nominal 6 ms high-frequency window on both CPUs,
retaining the existing 1 ms drive, state size and controls. The S03 Eq.7 pole
ratio gives about 131.006 Hz before returning to 47.65 Hz. S01's roughly 4 ms
description and S03's 6 ms baseline are both retained in
[the model/evidence](808-initial-pitch.md). This does not implement the companion
C39 retrigger, pulse shaper or nonlinear leakage/pitch sigh.

The analytical trial improves long-setting raw residuals but worsens default
and short settings. Keep those as explicit regressions and prioritize the
missing forcing/retrigger stages next. Component agreement is not reference
fidelity; do not close the full initial-pitch/excitation workstream on this
isolated switch. The HTML remains unchanged. The continuation loop now
advances existing ready work until concrete human input is required.

Both CPU suites and all three native functional scenarios exercise the new
initial stage. DT retains only known #78 resets; DN's current zero baselines
pass without resolving historical #20; DN2 passes with no halt/missing blocks.
Actual-CPU reference measurements confirm the trial: first 6 ms residuals
improve, all first 25/150 ms windows worsen, and whole-clip default/short errors
increase while long errors decrease. Keep the source switch as an incomplete
development slice; companion retrigger/forcing is the next planned work.

## C39 companion reference — 27 October 2026

The next existing #9/#79 foundation is a checked, isolated
[C39/R161/D52 host reference](808-retrigger.md). Its ideal positive clamp
updates capacitor charge and produces a negative falling pulse; the model
retains the ground-loading and diode/envelope approximations explicitly.
125 host tests and C/UI suites pass. Production DSP/native audio is unchanged,
so the initial-switch reference regressions remain open.

Next derive the correct band-pass forcing and consistent voltage/state scale,
then integrate that input on both CPUs and rerun all three native scenarios and
the five training settings. Do not add a raw pulse to the current y input or fit
away phase/gain errors. The HTML and held-out recordings remain untouched.

## Physical 808 bridge inputs — 27 October 2026

The [host reference](808-retrigger.md) now derives both main and companion
forcing channels from C41/C42 capacitor voltages, including the resistance
switch without a state reset. Exact held-input transitions pass independent
inverse-Laplace and switched-ODE checks; 130 host tests and C/UI suites pass.
This advances #9/#79's forcing derivation, without changing production audio.
Next integrate the derived forcing/state with a documented fixed audio scale
on both CPUs, then rerun native/five-setting checks. Feedback/loading remain
explicit approximations for later planned increments. Existing regressions, #78/#20/#80 and all
fidelity gates remain open. HTML and held-out recordings remain untouched.

## 808 state at the initial switch — 27 October 2026

The [next #9/#79 increment](808-switch-state.md) carries C41/C42 voltage through
the initial frequency switch on both CPUs. It changes the modal quadrature
without resetting the output or adding excitation. The current calibrated
pitch/Decay, finite drive, internal scale, private state size and controls stay
unchanged. Source-separated companion forcing remains the next planned step;
full feedback/pulse-shaper/leakage alignment is still open. 131 host tests and C/UI suites, both actual CPU suites and fresh five-setting
training comparisons are recorded with that increment. DT retains only #78
resets; DN reproduces #20's one-count silence baseline; DN2's tested scenario
passes. Default/short raw residuals improve slightly but both long settings
worsen; retain those regressions without changing acceptance limits. The
original HTML and held-out recordings remain untouched.
