# Implementation plan: one combined mod, silent first

Priority reset: 26 October 2026. First get **one selectable x0z mod running in
all three emulators**, with controls, p-locks and LFO targets connected to silent
ASM callbacks. Sound synthesis is the next milestone. Existing component tests
are useful groundwork, but none of the three installed-mod milestones is complete.

The product remains one mod per device containing 808 and 909 behind a saved
per-sound/track MODEL selector. Different tracks/voices can select different
models in the same build. Digitakt II is outside scope. C owns UI/plumbing;
ColdFire ASM serves DT/DN and SHARC+ ASM serves DN2. The
[render contract](render-contract.md) and [research](kick-drum-research.md) retain
the behavior and circuit details.

## The working backlog

Eight working issues replace the previous 66. Small increments are commits and
checklist steps inside these issues, rather than a ticket for every control,
model stage, CPU implementation and matrix cell.

| Order | Issue | Deliverable |
| --- | --- | --- |
| Track | [#1](https://github.com/simonjohansson/x0z/issues/1) | Roadmap and milestone status |
| Now | [#39](https://github.com/simonjohansson/x0z/issues/39) | Digitakt: select and exercise the silent combined mod in digiemu |
| Done | [#40](https://github.com/simonjohansson/x0z/issues/40) | Digitone: select and exercise the silent combined mod in digiemu |
| Now | [#7](https://github.com/simonjohansson/x0z/issues/7) | Digitone II: select and exercise the silent combined mod in Digikit |
| Next | [#9](https://github.com/simonjohansson/x0z/issues/9) | Implement the 808 on both CPUs and integrate each increment into working mods |
| Then | [#25](https://github.com/simonjohansson/x0z/issues/25) | Implement the 909 on both CPUs alongside the 808 in those same mods |
| Deferred by user | [#2](https://github.com/simonjohansson/x0z/issues/2) | Reference VST captures and fidelity comparisons for both models |
| After sound | [#20](https://github.com/simonjohansson/x0z/issues/20) | Combined-mod emulator regression and readiness review |

The three device issues are independent. Start with DT, whose existing full-OS
observer already reaches the render hook. Use subagents for non-overlapping
work. A blocked device does not stop useful work on another device. Once all
currently actionable silent bring-up work is done, sound work can proceed on
working devices while the blocked device retains its open gate.

## First milestone: silent mods in all three emulators

Each device issue owns the same short, end-to-end acceptance scenario:

- Build the latest supported firmware with one registered `X0Z KICKS` machine;
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
| DT, OS 1.54 | Real ID80 mod boots; selection defaults, native controls, p-lock/LFO, save/reload, mixed models and silent owned output pass | Native knob/page reset still restores stock defaults; #39 remains open |
| DN, OS 1.44 | Silent milestone passes: native controls/screen, p-lock/LFO, save/reload, mixed tracks and owned output | Actual kick models and broader qualification follow in #9/#25/#20 |
| DN2, OS 1.12 | ID20 boots in coupled Digikit; native defaults, MIDI notes, pending MODEL and concurrent 808/909 voices pass | Ordinary A/B/C edits, native p-lock/LFO, mixed tracks and save/reload |

The user explicitly approved the combined DT/DN saved layouts on 26 October:
ID 80 `X0Z KICKS`. The subsequently approved compact layout on all three
devices is A TNTUN=64, B DECAY=64, C ATTK=64, F MODEL=0; D/E/G/H blank.
There is no x0z LEVEL knob: native track level handles volume and the renderer
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

In #9, start with an analytically checked 808 body and level/decay, then add the
excitation, pitch/feedback and tone/output behavior as small tested commits.
Each ready increment runs through the already-installed mod. #25 follows with
909 body/tune, envelope and pulse/noise attack. Keep the same registration and
saved controls throughout; both models must coexist, not become separate mods.

Each instrument has one independent high-precision model and two actual ASM
implementations. Reuse the existing analyzers, fixtures and CPU runners. Compare
each backend to that model and compare matching outputs across CPUs. Record
bounds, fixed-point overflow/limit cycles, floating-point stability and state
isolation as part of the engine issue. Initial research-based sound is explicitly
uncalibrated until deferred #2 reference comparisons pass.

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
