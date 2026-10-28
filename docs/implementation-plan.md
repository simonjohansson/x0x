# Implementation plan: one combined mod, silent first

Current 808 DSP is `53c4e66`: the [lower-interior duration correction](808-lower-duration.md)
changes the existing lower shape from 1.5 to 1.33 with a no-new-level-failures
training guard. Duration checks rise 432→456 of 486 per CPU; 24 of 27 short-tail
misses are resolved. Darkest Tone/Decay32 still misses t99 by .167 ms on three
takes, and the default t90 failures remain. No previously passing duration or
level check is lost; level passes remain 1,380/1,890. Preserve the .185% mean
whole-waveform error increase and broad-band regressions. 203 host tests, guarded
components, both fresh full 81-setting/243-take/12-second grids and seven histories
pass numerical limits. All 54 unaffected settings and seven histories per CPU
remain byte-identical, including minimum/default/upper sounds. Instructions,
state, ABI, controls, gain and dependency pins are unchanged. Next continue
onset/body-shape/Tone work and measurement/listening protocols in #79/#2; #9
remains complete and final #20 stays open. No fresh OS/physical or held-out
acceptance. Website work is paused and its files are preserved.

Previous 808 DSP is `7716145`: the [upper-middle Decay correction](808-upper-decay.md)
brings all 162 affected duration checks per CPU within the agreed margin; mean
absolute duration error falls 80.43→15.69 ms. Whole-surface duration checks rise
270→432 of 486, leaving Decay32 t99 and default t90 failures. Level checks rise
1,206→1,380 of 1,890; settings meeting all eligible levels rise 18→27 of 81.
202 host tests, guarded components and both fresh full 81-setting/243-take/12-second
grids plus seven histories pass numerical limits. All 54 unaffected settings and
seven histories per CPU remain byte-identical. Gain stays 1.601664543; no public,
saved, state-extent or dependency changes. Preserve the tradeoffs: whole-waveform
error rises about 4.1%, 21 peak checks per CPU newly miss by +2.003 to +2.019 dB,
and the existing broad-band ratio diagnostic worsens. This is a duration/level
increment, not full fidelity. Next continue remaining onset/body-shape/Tone and
measurement/listening work in #79/#2; held-out audio and HTML stay untouched.
No fresh full-OS/physical evidence; #9 remains complete and #20 stays open.

Previous 808 DSP is `e0adf4e`: the [minimum-Decay correction](808-minimum-decay.md)
shortens the minimum effective tau to 19.22924 ms in a C1 segment below raw4096
(reference 32/255, native 16/127). All 27 minimum takes improve duration and raw
6/25/150/500 ms/full-tail error on both actual CPUs; t99 moves 70→40 ms against 38 ms.
All 72 later settings and seven histories per CPU remain byte-identical. 199 host
tests, both guarded CPU suites and the full 81 settings / 243 takes comparison pass
unchanged numerical/headroom limits. Gain stays 1.601664543. Eligible level checks
rise 1,134→1,206 of 1,890; all-setting level passes rise 9→18 of 81. Tiny SHARC quiet
late regressions remain recorded. Next address upper-middle Decay sequentially
in #79/#2. Held-out audio, HTML, public/saved boundaries and #9's accepted scope
stay unchanged; no fresh native OS or physical-device proof is claimed.

Previous 808 output calibration at `0f7ef30`: [fixed output scaling](808-output-calibration.md)
uses one 1.601664543 (+4.091431 dB) factor across settings/CPUs, with native LEVEL
unchanged. The level windows/floor/objective are frozen. 198 host tests, six C/UI
checks, both actual CPU suites, full 81-setting / 243-take tails and seven
histories pass their numerical gates. Raw error improves at 72 settings and
regresses at all nine minimum-Decay settings. 1,134 of 1,890 eligible level checks
pass, but only nine settings meet every level check: full fidelity stays open.
Next address envelope balance sequentially in #79/#2 and finish other metric
protocols before held-out use. The earlier gain freeze is superseded by explicit
human approval; [starting targets](808-fidelity-target.md) remain unchanged.
Held-out audio and HTML are untouched. Accent and faithful residual-state
retrigger remain separate refinements; #9 stays complete.

The historical [full training-grid baseline](full-reference-grid-baseline.md) compares
243 808 and 2,187 909 recordings against accepted commit `65aeaf7` on both
actual CPUs, plus seven declared-voice histories per engine. This is component
diagnostic evidence; held-out/native fidelity gates remain open and the HTML
report is unchanged. Previous DSP-only 808 qualification is `5963a34`, the
[lower-interior Decay correction](808-decay-shape.md), after the
[main-pulse](808-main-pulse-time.md), [Tone](808-tone-shape.md) and
[feedback](808-feedback-calibration.md) corrections. Both actual CPU suites,
81-setting / 243-take full tails and seven histories pass. All 27 affected
settings improve cumulative/whole raw residuals; 54 settings and all histories
are byte identical. Mean whole-tail error falls 2.536%, with late-window and
peak-slope regressions retained. Prior full-device evidence remains `9e78ca9`,
with known #78/#20 distinctions; this DSP-only increment has no fresh OS run.

On 28 October the human accepted **#9 complete as the supported fixed-strength,
reset-on-START 808 baseline**. Intrinsic circuit accent, retained-state retrigger,
full feedback/output loading and calibrated/held-out fidelity remain explicit
#79/#2 work. DN2's current SDK lacks intrinsic strength and logical lifecycle
identity; do not invent those inputs or change public boundaries without review.

The three silent native milestones are complete. The current 808 has a
reference-calibrated settled pole/Decay range, switched capacitor state,
main/companion excitation, Q43 leakage, Tone RC and output coupling on both
CPUs. See [808 leakage](808-leakage.md) for the current waveform evidence and
retained default/long pitch-trajectory regressions. The [lower-half Decay correction](808-decay-lower-half.md) now improves the
measured interior response on both CPU components, retaining the entire upper
law and all anchors. Raw display32 regressions remain explicit; full feedback,
loading, control taper and faithful residual-state retrigger remain incomplete
in #79/#2. Native and paired full-grid qualification of this correction is
recorded separately in that document.

The [continuing-pitch investigation](808-pitch-sigh-investigation.md) attributes
the earlier long-kick error to Q43. Rejected isolated source corrections remain
unadopted. The [effective feedback calibration](808-feedback-calibration.md)
now changes only two coefficients on both CPUs: long late pitch moves from
49.72 to 47.65 Hz against 47.78 Hz recorded, with the quiet pole unchanged.
Fresh 81-setting / 243-take / full 12 s paired comparison reduces mean error
15.62%, and all seven history diagnostics improve. All 32 regressing settings
and the 0.67% early-25-ms regression remain explicit. Host/C UI, both guarded
CPU suites and installed numeric checks pass unchanged limits; these are not
whole-engine fidelity acceptance. Next investigate remaining Tone/onset and
short-Decay residuals before adopting another correction. Omitted output and
faithful residual-state behavior remain open; held-out audio remains unused.

The [Tone control-shape correction](808-tone-shape.md) replaces the nominal
linear-position C15 approximation with one reference-calibrated sqrt-position
curve. All 189 isolated interior transfer comparisons improve; both endpoints
remain exact. Both guarded CPU suites, full 81-setting / 243-take tails, seven
histories and installed numeric checks pass. Whole-engine improvement is small
(.0194% mean full-tail), with 25 whole-tail settings and four histories regressing;
these remain explicit. The standalone initial-frequency and updated soft-knee
trials are rejected for their early-window/full-waveform regressions. Continue
existing excitation and declared-same-voice retention experiments using this
qualified source; no native owner identity or gain calibration is inferred.
The qualified [main-pulse timescale calibration](808-main-pulse-time.md) changes
only C40's effective source evolution. Its bounded host screen improves all
81 settings at 6/25/150/500 ms; nine late minimum-Decay regressions remain.
Both actual raw-body checks preserve the tight .25 FS bound. Full component,
paired 12-second tails / seven histories and installed scenarios are complete.
All 81 cumulative-window/full-tail settings and all seven histories improve;
mean whole error falls .796%. Nine minimum-Decay settings regress slightly in
the isolated 150–500 ms window. The body-bound-limited fit is not a stationary
optimum; raw headroom and SHARC numeric margins remain tight.

Two subsequent output/Decay diagnostics do not justify another production
change: fixed physical output division worsens every screened take; a unit-HF
output-pair replacement has a tiny mixed improvement with minimum-Decay
regressions. All 135 upper-Decay quiet-pole windows fail frozen inference
criteria; this neither changes nor confirms the current upper law. Preserve
these findings rather than refitting rejected windows. See the
[remaining source/model work](808-pitch-sigh-investigation.md).
The human's earlier gain freeze is superseded by explicit approval of
[fixed DSP output calibration](808-output-calibration-proposal.md). Existing
qualification retains its original gain and raw comparison provenance. The
[lower-interior Decay correction](808-decay-shape.md) now has a reviewed
fixed-gain model/full-tail screen and complete actual CPU/reference qualification.
The supported baseline is delivered; remaining source/fidelity work stays in
#79/#2 rather than leaving #9 open for further parameter experiments.
All three anchors and the upper law stay fixed. Retain its late/peak-slope
regressions; rejected quiet-pole estimates are not calibration targets.

For DSP-only sound changes, actual ColdFire/SHARC execution and reference
comparison are the increment gate. Repeat full-device integration when device
plumbing, parameter mapping, voice-state layout, calling conventions, firmware
dependencies or packaging changes, and at integration/release milestones.
Stock firmware and Elekloader handle native controls/modulation, allocation and
mixing; rerunning their complete scenarios for every sound coefficient is not
required. Preserve previous native results as previous evidence, and keep #20
whole-product acceptance separate.

The 909 [diode shaper](909-shaping.md), [C9/IC12 Tune path](909-tune.md) and
[loaded ENV1/Q12 VCA](909-vca.md) run on both CPUs and all three emulators.
Tune changes the initial sweep; settled pitch is separately training-calibrated
at52.58 Hz. Loaded finite C8 charging/base-current discharge improves all five
whole-waveform residuals and default decay duration, while onset/peak/level
regressions remain explicit. The initial wrong-sign Q11 trial remains rejected.
Independent Q10/IC11a source checks justify the [finite reset/negative-output
correction](909-trigger.md), now passing both CPU suites and all three native
regression paths plus a separate DN2first32sample witness. All five whole errors
improve, while default25/50ms windows regress. The remaining [Attack integration](909-attack-status.md) requires a supported
DN2 shared-noise clock, requested in
[Elekloader #108](https://github.com/simonjohansson/elekloader/issues/108).
No public API or clock workaround is adopted. A source-consistent joint passive
network fix is retained but still fails to improve on body-only output; a
conditional Q12 replacement also worsens the declared raw comparisons and is
rejected without a port. Complete known-truth/reference evidence is linked in
that status document. Do not repeat these candidates or land a numerically
passing branch with larger reference error.

DT retains only deferred reset #78. DN's [historical one-count investigation](dn-silence-residue.md)
proves exact-zero x0x inputs into stock filters with nonzero native downstream
output. The current main-pulse run passes its first zero 100 ms windows; the
earlier feedback-calibration run reproduced the residue through all sixty
windows. Neither intermittent result establishes a fix; #20 remains unresolved.
[DN2 MIDI delivery](dn2-late-model.md) is fixed in public Digikit draft PR200,
now pinned here. The unchanged-production candidate passes full and original
late-MODEL scenarios; the normal pinned daemon passes the new full Tune run.
The separate original-order late probe now also passes on the normal daemon,
completing #80's root-repository gates; the public PR remains draft.
The [private DN2 allocation](dn2-private-layout.md) now provides 8,128 usable
code bytes and 5 KiB data within the existing reservation. All 29 component
outputs remain byte identical; the full native and original-order late-MODEL
scenarios pass on the normal emulator. This does not adopt the pulse/noise
prototypes or close their fidelity gates.
These native gates do not block other ready engine work. HTML is unchanged;
training repetitions retain raw timing/gain, and held-out audio remains unused.

The product remains one mod per device containing 808 and 909 behind a saved
per-sound/track MODEL selector. Different tracks/voices can select different
models in the same build. Digitakt II is outside scope. C owns UI/plumbing;
ColdFire ASM serves DT/DN and SHARC+ ASM serves DN2. The
[render contract](render-contract.md) and [research](kick-drum-research.md) retain
the behavior and circuit details.

## The working backlog

Eight consolidated issues replaced the previous 66; #78 records the deferred DT
reset bug, #79 owns reference-model/schematic alignment, #80 records
the resolved late DN2 MODEL transition, and #81 tracks private DN2 capacity. Small increments
are commits and checklist steps inside these issues, rather than a ticket for
every control, model stage, CPU implementation and matrix cell.

| Order | Issue | Deliverable |
| --- | --- | --- |
| Track | [#1](https://github.com/simonjohansson/x0x/issues/1) | Roadmap and milestone status |
| Done, reset bug deferred | [#39](https://github.com/simonjohansson/x0x/issues/39) | Digitakt: select and exercise the silent combined mod in digiemu |
| Done | [#40](https://github.com/simonjohansson/x0x/issues/40) | Digitone: select and exercise the silent combined mod in digiemu |
| Done | [#7](https://github.com/simonjohansson/x0x/issues/7) | Digitone II: select and exercise the silent combined mod in Digikit |
| Done, supported baseline | [#9](https://github.com/simonjohansson/x0x/issues/9) | Fixed-strength/reset-on-START 808 on both CPUs; intrinsic accent, residual retrigger and fidelity remain in #79/#2 |
| In progress | [#25](https://github.com/simonjohansson/x0x/issues/25) | Implement the 909 on both CPUs alongside the 808 in those same mods |
| Done | [#80](https://github.com/simonjohansson/x0x/issues/80) | Upstream Digikit mask fix published/pinned; unchanged-production full and original late-MODEL probes pass on the normal runtime |
| Alongside engines | [#79](https://github.com/simonjohansson/x0x/issues/79) | Align both engines with sources and the full measured training surfaces |
| Done | [#81](https://github.com/simonjohansson/x0x/issues/81) | Private DN2 8 KiB code / 5 KiB data split; unchanged audio and full/late-MODEL native scenarios pass, without SDK/public-format changes |
| Deferred by user | [#78](https://github.com/simonjohansson/x0x/issues/78) | Digitakt native reset defaults; fix upstream in Elekloader and consume here |
| Full training grids complete for both engines; fidelity open | [#2](https://github.com/simonjohansson/x0x/issues/2) | Fixed-level reference corpora; both-model fidelity comparisons remain open |
| After sound | [#20](https://github.com/simonjohansson/x0x/issues/20) | Combined-mod emulator regression and readiness review |

The three silent device issues and supported 808 baseline #9 are closed:
the body is integrated and audible on all three devices' emulators. The DT reset
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

### Historical silent-milestone starting points

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
source pole ratio for a nominal 6 ms window. Companion C39
retrigger/forcing and the main pulse shaper are now implemented, along with Q43 leakage.
The supported 808 baseline is complete in #9. Further source/output and
retained-state refinements stay in #79/#2, with unsupported lifecycle/strength
inputs requiring review. DSP-only corrections use component/reference gates;
full-device checks run at integration changes and milestones. #25 is underway
with the shaped triangle, Tune CV, loaded VCA and finite reset. The full grid
now prioritizes missing Attack/transient behavior and body/level/Decay gaps.
Pulse/noise prototypes remain unadopted; their numeric passes do not establish
reference improvement. Keep the same registration and
saved controls throughout; both models must coexist, not become separate mods.

Get the engines working before performance tuning. Instruction counts are
informational; there is no per-callback instruction budget. Test watchdogs catch
hangs, while measured workload/performance qualification comes later.

[#79](https://github.com/simonjohansson/x0x/issues/79) makes the source-to-code
alignment explicit: inspect published reference implementations and primary
schematics, choose each stock circuit baseline, audit provisional/missing stages,
and refine the 808 in #79/#2 while completing the 909 implementation in #25. Reference recordings are now
available: use the training settings to prioritize and calibrate each increment
while retaining circuit-model gaps. #2 owns broader and held-out fidelity
validation; source alignment is not a reason to postpone all measurements. The
[first source/code audit](reference-alignment.md) pins the available reference
code, selects schematic baselines and records the missing/provisional blocks.
The first source-derived slice implements the 808 Tone RC network on both CPUs,
checked against an independent capacitor voltage/current reference. Its native
knob taper remains provisional. The 1 ms drive duration and main pulse shaping are implemented;
the full feedback network and
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

Use mise, the upstream Elekloader revision pinned in `firmware/manifest.json`,
digiemu for DT/DN and Digikit for DN2. The earlier PR #200 pin is superseded.
Only the [latest supported firmware](../firmware/README.md) is in scope.
Commit small increments directly to main and push, with evidence on the owning
issue. Do not close a milestone on partial proof or widen tolerances to conceal
failures. Other stable API or saved-layout changes still require review.

Historical checkpoints below retain their original next-step wording and
evidence. They do not reopen the accepted #9 baseline or override the
[current backlog](#the-working-backlog) and testing cadence above.

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

## 808 companion excitation — 27 October 2026

The [C39 companion input](808-companion.md) is integrated on both CPUs with one
new volatile state word per voice, consistent negative band-pass forcing and a
fixed private voltage encoding. 134 host/C tests, both CPU suites and all three
installed emulator scenarios ran. DT retains only #78 resets; DN's current
baselines pass without resolving #20; DN2 passes its tested scenario. #80 stays
unqualified. First-25-ms errors improve about 5–6% at all five training settings;
whole-clip short errors improve, default barely changes, and long errors worsen
about 7%. Retain those regressions. Next implement the existing main pulse-shaper
and proper bridge input on both CPUs, then compare again. Do not add another
research-only checkpoint or fit away the missing input physics. HTML and
held-out audio remain untouched; full fidelity and combined acceptance stay open.

## Qualified upstream SDK — 27 October 2026

The user replaced the PR200-only requirement with upstream Elekloader. The
submodule and firmware manifest now pin `b893c9317936633d7a32829b618c2867ee99277c`
(upstream main, verified current at refresh). DN2 uses the current descriptor
and Core 0.2 while retaining its approved saved contract. Firmware verification,
134 host/C checks, the actual SHARC suite and all three native emulator scenarios
ran; DN/DN2 pass, while DT retains only deferred #78 resets. #20/#80 retain their
separate gates. See [SDK evidence](development.md#setup). The continuation loop
uses the manifest's validated upstream pin; it must not restore PR200. Next is
the existing #9 main pulse-shaper/forcing step, with no DSP or HTML change in
this dependency refresh.

## Shaped 808 main input — 27 October 2026

The existing #9/#79 [main pulse-shaper and bridge input](808-main-input.md) now
run on both CPUs, replacing the provisional y injection with C40/D53 charge
state, main-channel forcing and direct feedthrough. The calibrated poles/Decay,
companion input, approved controls, IDs and MODEL policy remain. Full feedback,
pitch sigh, loaded output and faithful residual-state retrigger remain open.

136 host tests and C/UI suites, both actual CPU suites and supplemental midpoint
probes pass with the existing 1e-5 FS limit. [Native evidence](808-main-input-native.md)
records all three installed emulator scenarios: DT retains only #78 resets;
DN and DN2 pass their tested paths without closing historical #20 or separate
#80. Five-setting training error improves 37% at default and 74–75% at
short Decay, but regresses 7–8% at long Decay; first 6/25/150 ms improve at
every setting. Preserve those regressions. Next continue the existing feedback/
pitch-sigh alignment, using the default and long-tail errors to prioritize it. Do not close full fidelity or combined acceptance on these
bounded checks. The HTML report and held-out recordings remain untouched.

## 808 leakage and pitch sigh — 27 October 2026

The existing #9/#79 [Q43 leakage step](808-leakage.md) runs on both CPUs.
It adds a source-derived hard-knee collector current through nonsingular
capacitor KCL, retaining the settled 47.65 Hz calibration and saved contract.
142 host tests and independent C/UI suites, both actual CPU suites and the five-setting training
comparison pass their existing numeric bounds. Whole raw errors improve at all
five settings (default ~50%, short 23–28%, long ~39%). The first 6 ms is unchanged;
25/150-ms waveform errors improve. The long 150–300-ms frequency estimate worsens
from 47.648 to 49.722 Hz against 47.778 Hz reference: retain that regression, the
remaining amplitude/phase errors and the hard-knee/full-feedback approximations.

All three installed emulators ran. DT retains only #78 resets. DN reproduces
#20's one-count bright-Tone baseline with other tested paths passing. DN2's
nonlinear dark-Tone check passes, then note75 has no active bright-Tone lane;
its later checks are unexecuted. That missing-note failure is not yet proved
to share #80's late CC loss. The independent [upstream trace](dn2-late-model.md)
now identifies receive-callback reentry and reordered CC bytes due to missing
Digikit interrupt-mask semantics. An upstream fix/requalification remains; no
mod workaround was adopted.

Next continue the existing feedback/input/transistor alignment and native MIDI
investigation; do not repeat this completed leakage port, widen tolerances or
claim full fidelity/combined acceptance. Independent workers delivered the
SHARC port, model/tests and MIDI trace while the coordinator implemented
ColdFire and integrated the results. HTML and held-out recordings are untouched.

## 909 diode shaper and first comparison — 27 October 2026

The [source-derived diode stage](909-shaping.md) now runs on both CPUs before
the existing VCA, retaining state, approved controls and the fixed audition
scale. 145 host tests/C UI suites plus three new comparison tests pass. Both CPU suites
pass unchanged 1e-5 FS: peer difference ≤4.229e-7 FS; tested 808 outputs are byte-identical.
DT retains only #78; DN's new native run passes without resolving historical #20.
DN2's full new diode run passes on the INTC-fix candidate; vendor-pin adoption and
upstream delivery remain separate #80 work. The [first 909 training baseline](909-reference-baseline.md)
retains raw timing/gain/repeats, no held-out/HTML, and explicitly unused Tune/Attack.
It prioritizes stock Tune/pitch, then loaded ENV1/Q12 VCA and separate Attack work.
Workers are implementing Tune and modeling VCA independently while emulator
publication/qualification proceeds; shared DSP integration remains serial.

## 909 Tune and pitch CV — 27 October 2026

The [C9/IC12 increment](909-tune.md) is integrated on both CPUs with exact
native Tune delivery and interval-integrated phase. The independent RC/RK4
model, 155 current host tests/C UI suites, both actual CPU suites and installed
DT/DN/DN2 scenarios complete. SHARC uses 4,866 code / 1,024 private bytes;
maximum paired CPU difference is 4.58e-6 FS under unchanged 1e-5 FS.
DT retains #78; DN retains #20; DN2 passes on the normal adopted Digikit pin.
Default settled pitch now matches 52.58 Hz reference, with default waveform
RMS .10283→.08229 FS. Preserve low-short and both long regressions; current
unloaded VCA and trigger/reset are the next planned source-model corrections.
No saved layouts, public interfaces, HTML or held-out audio changed.

## Loaded 909 ENV1/Q12 — 27 October 2026

The [finite C8/base-current VCA](909-vca.md) replaces the unloaded envelope on
both actual CPUs, with161 relevant host tests/C UI suites and guarded CPU
comparisons. SHARC has5,534 code /1,664 private bytes; paired difference≤2.678e-6
FS under unchanged1e-5. All three installed scenarios complete: DT47,190callbacks
retains only#78; DN111,526callbacks proves62 audible mixed frames and retains
#20's one-count baseline; DN2 passes37,815audio/37,816DSPframes. Corrected mixed
scenes retain their timing while triggering both short sounds after setup.
Default audio decay fit181.825→52.866ms versus57.323reference; all five whole
residuals improve, but peak/global level mismatch and some onset windows worsen.
Keep full fidelity open. Hold the regressing finite-R51 prototype; proceed with
source-derived Attack pulse/noise work. HTML and held-out audio remain unchanged.

## Finite 909 reset and output polarity — 27 October 2026

The [source-verified combined correction](909-trigger.md) resolves the wrong
Q10type/output-sign assumption with fixed physical polarity, not fitted phase.
169 relevant host cases/C UI suites and both full CPU suites pass unchanged
1e-5FS. SHARC runs14,298calls,5,672code/1,664privatebytes, with nine808renders
byte-identical; peer error≤2.605e-6FS. All five whole training errors improve;
default first25/50ms and short/level/Attack gaps remain explicit. DT47,135 and
DN110,123callbacks retain only#78/#20 respectively. DN2original regression
passes37,815audio/37,816DSPframes; the first prefix observer was unqualified
from chunk overshoot, then a separate unchanged-firmware focused probe qualifies
age32/remaining64 inside the original24frame window. Keep those reports distinct.
The future combined observer uses exact step jobs and the original120s watchdog;
no claim of rerunning that revised full script. HTML and held-out audio unchanged.
