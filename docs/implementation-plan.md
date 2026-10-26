# Implementation plan: two CPU backends, six device cells

Planning baseline: 26 October 2026. The shared contract, host fixtures, analyzer/comparisons and isolated C adapter tests are implemented. Bounded ColdFire arithmetic/EMAC, DN2 callback/state and all three C-to-ASM adapter components pass in the required emulators. DT additionally executes native edit/smoothing/lock/LFO routines and a full-OS PLAY-to-START-to-C/ASM observer; DN executes its companion and bounded native live edits. DN2 executes the upstream bridge with synthetic stock frames. Complete device transport/replacement acceptance and both kick engines remain unimplemented. The [research](kick-drum-research.md) defines the circuit basis; [development and verification](development.md) records commands and emulator limitations, and [roadmap #1](https://github.com/simonjohansson/x0z/issues/1) tracks execution.

Completed foundation scope: [shared semantics #4](https://github.com/simonjohansson/x0z/issues/4), [fixtures/test entry points #36](https://github.com/simonjohansson/x0z/issues/36), [known-signal analyzer #3](https://github.com/simonjohansson/x0z/issues/3), [oracle/CPU comparisons #38](https://github.com/simonjohansson/x0z/issues/38), [ColdFire harness #37](https://github.com/simonjohansson/x0z/issues/37) and [SHARC callback harness #5](https://github.com/simonjohansson/x0z/issues/5). These are emulator/test-equipment results, not device or kick-fidelity qualification. VST captures and calibrated timbre gates remain deferred. Firmware support is restricted to the [latest official baseline](../firmware/README.md); builds use the pinned Elekloader PR #200 revision.

## Architecture and scope

**One x0z mod on every supported device contains both 808 and 909 engines.**
Each device has one native x0z machine identity and a saved MODEL selector per
sound/track. Different tracks/voices can play both models concurrently in the
same installed build. Target-specific firmware builds package this same product.
Separate engine registrations and single-engine delivery variants are superseded.
The [common product contract](render-contract.md#one-combined-mod-on-every-device)
is authoritative. The earlier approval of two Digitakt machines is withdrawn by
the user's correction; revised DT/DN combined positions/IDs remain proposals.

Support Digitakt (DT), Digitone (DN) and Digitone II (DN2). Digitakt II is outside the active scope. Each instrument has one behavioral/mathematical definition and independent high-precision host oracle. Production audio has two handwritten assembly implementations: ColdFire shared by DT/DN, and SHARC+ for DN2. Three thin C adapters own firmware callbacks, native controls, voice identity and output integration.

Share physical units, event semantics, reference fixtures and fidelity criteria. Keep arithmetic formats, state layouts, coefficient encoding and scheduling inside each CPU backend. Select the target at build time. Do not create a portable assembly language, per-operation dispatch or independently fitted copies of the instrument.

## Foundations first

Start the shared behavior/interface review, measurement checks and VST selection now. Then implement the necessary test infrastructure and per-target diagnostics before developing that cell's engine. The shared foundation does not wait for every device adapter or for DN2 upstream merges.

| Foundation | Deliverable | Prerequisites |
| --- | --- | --- |
| [#4](https://github.com/simonjohansson/x0z/issues/4) Foundation: Define shared instrument and render semantics | Define one instrument behavior per drum, independent of CPU arithmetic and device callbacks. | Ready |
| [#36](https://github.com/simonjohansson/x0z/issues/36) Foundation: Add shared render fixtures and independent test entry points | Make the agreed interface executable as minimal private test infrastructure before implementing kicks. | [#4](https://github.com/simonjohansson/x0z/issues/4) |
| [#3](https://github.com/simonjohansson/x0z/issues/3) Test: Validate kick measurements with known signals | Build the smallest trustworthy analyzer before it judges any synth. | Ready |
| [#38](https://github.com/simonjohansson/x0z/issues/38) Foundation: Validate oracle and cross-CPU audio comparisons | Use one independent oracle and trustworthy tolerances for both CPU implementations. | [#36](https://github.com/simonjohansson/x0z/issues/36), [#3](https://github.com/simonjohansson/x0z/issues/3) |
| [#37](https://github.com/simonjohansson/x0z/issues/37) ColdFire foundation: Test actual assembled instructions without UI | Provide one ColdFire kernel runner reused by Digitakt and Digitone. | [#36](https://github.com/simonjohansson/x0z/issues/36) |
| [#5](https://github.com/simonjohansson/x0z/issues/5) SHARC foundation: Test actual assembled instructions without UI | Provide the SHARC backend test runner independently of native controls and kick models. | [#36](https://github.com/simonjohansson/x0z/issues/36) |
| [#39](https://github.com/simonjohansson/x0z/issues/39) Digitakt foundation: Pin and test the C adapter with diagnostic ASM | Prove the Digitakt device boundary before any complete kick engine. | [#36](https://github.com/simonjohansson/x0z/issues/36), [#37](https://github.com/simonjohansson/x0z/issues/37) |
| [#40](https://github.com/simonjohansson/x0z/issues/40) Digitone foundation: Pin and test the C adapter with diagnostic ASM | Prove the Digitone device boundary before any complete kick engine. | [#36](https://github.com/simonjohansson/x0z/issues/36), [#37](https://github.com/simonjohansson/x0z/issues/37) |
| [#7](https://github.com/simonjohansson/x0z/issues/7) Digitone II foundation: Pin and test the C adapter with diagnostic ASM | Prove the Digitone II device boundary before any complete kick engine. | [#36](https://github.com/simonjohansson/x0z/issues/36), [#5](https://github.com/simonjohansson/x0z/issues/5) |

808 reference selection [#2](https://github.com/simonjohansson/x0z/issues/2) and 909 reference selection [#21](https://github.com/simonjohansson/x0z/issues/21) can run in parallel. Their capture/tolerance work is [#8](https://github.com/simonjohansson/x0z/issues/8) and [#22](https://github.com/simonjohansson/x0z/issues/22). DN2 packaging review [#23](https://github.com/simonjohansson/x0z/issues/23) is local to DN2 and does not block ColdFire. The user approved one synth with an 808/909 selector, ID 20 and its [saved-control contract](dn2-packaging-proposal.md). Implement its production C declarations and independent selector tests in #6/#24; native save/load and lifecycle qualification remain separate.

The shared interface is a private development contract. Concrete permanent IDs and saved control layouts need review before becoming stable. Pin each device's actual firmware/core/headers in its adapter work. DN2 development uses the exact Elekloader PR #200 head rather than waiting for a merge; changing that revision requires matched header/adapter checks.

Selector infrastructure is explicit for both CPU backends:
[ColdFire #77](https://github.com/simonjohansson/x0z/issues/77) serves DT/DN,
and [SHARC #76](https://github.com/simonjohansson/x0z/issues/76) serves DN2.
These test per-voice model selection and state isolation before sound models;
they do not depend on VST captures or complete engines.

The adapter foundations #39, #40 and #7 remain open. Their C boundaries and
diagnostic assembly components are now independently executable; each issue
retains its missing native transport/lifecycle gates. Next, establish complete
event-to-render traces per device without reserving permanent IDs. DT's bounded
routine/observer results and DN's target-buffer results do not close their complete integration gates.
The measured DN target-versus-smoothed-frame gap has a bounded follow-up,
[#75](https://github.com/simonjohansson/x0z/issues/75), before delivered controls
can satisfy #40.
DN2 coupled setup currently stops on the missing complete hardware-manual reset
table input; its bridge component can continue independently. See the
[adapter evidence and setup blocker](development.md#device-adapter-slices).

## Independent delivery matrix

Each row is a model-specific test/development slice within the combined mod,
not a separate package. Start a slice once its fixtures/comparator, CPU harness,
adapter and next prerequisites are ready; do not wait for the other complete
engine or another device. DT and DN share the ColdFire kernels and selector.

| Cell tracker | C controls | First audible body and continuing integration | Device qualification |
| --- | --- | --- | --- |
| [#58](https://github.com/simonjohansson/x0z/issues/58) Digitakt + 808 | [#55](https://github.com/simonjohansson/x0z/issues/55) | [#56](https://github.com/simonjohansson/x0z/issues/56) | [#57](https://github.com/simonjohansson/x0z/issues/57) |
| [#62](https://github.com/simonjohansson/x0z/issues/62) Digitakt + 909 | [#59](https://github.com/simonjohansson/x0z/issues/59) | [#60](https://github.com/simonjohansson/x0z/issues/60) | [#61](https://github.com/simonjohansson/x0z/issues/61) |
| [#66](https://github.com/simonjohansson/x0z/issues/66) Digitone + 808 | [#63](https://github.com/simonjohansson/x0z/issues/63) | [#64](https://github.com/simonjohansson/x0z/issues/64) | [#65](https://github.com/simonjohansson/x0z/issues/65) |
| [#70](https://github.com/simonjohansson/x0z/issues/70) Digitone + 909 | [#67](https://github.com/simonjohansson/x0z/issues/67) | [#68](https://github.com/simonjohansson/x0z/issues/68) | [#69](https://github.com/simonjohansson/x0z/issues/69) |
| [#72](https://github.com/simonjohansson/x0z/issues/72) Digitone II + 808 | [#6](https://github.com/simonjohansson/x0z/issues/6) | [#71](https://github.com/simonjohansson/x0z/issues/71) | [#20](https://github.com/simonjohansson/x0z/issues/20) |
| [#74](https://github.com/simonjohansson/x0z/issues/74) Digitone II + 909 | [#24](https://github.com/simonjohansson/x0z/issues/24) | [#73](https://github.com/simonjohansson/x0z/issues/73) | [#35](https://github.com/simonjohansson/x0z/issues/35) |

The six cell issues are progress trackers, not large implementation tickets. Their native children cover controls, early integration and qualification. Shared CPU/model tasks remain under the main roadmap and are linked by dependencies. Labels `808`/`909`, `cpu:coldfire`/`cpu:sharc`, `device:dt`/`device:dn`/`device:dn2` and `type:*` make the ownership explicit.

Completed DN2 #6/#24 C control work implements the approved shared ID-20 descriptor and
page, with per-slot START-latched selection and explicit tail-clear metadata.
It requires neither kick renderer; fake DSP tests cover both models' exact
control mappings and the host reference selector policy. Production C owns the
page declarations; the SHARC bridge calls ASM directly, so these C helpers do
not establish an installed C-to-SHARC selector path. This does not qualify native
registration/save/load, ownership or audible model switching. DT's
[control proposal](dt-controls-proposal.md) remains unadopted pending review.
DN's corresponding [control proposal](dn-controls-proposal.md) is also pending
review; it uses verified full-range SYN2 positions without extra saved slots.
The [DN delivered-control investigation](dn-delivered-controls-proposal.md)
prioritizes existing Core events and a tested same-interrupt bank lifetime over
a new public hook.

## Small sound slices

Prioritize a tiny 808 body on both CPUs and audible integration on at least one ColdFire device and DN2 before investing in expensive complete models. This is a scheduling priority, not a dependency on DN2 completion: ready ColdFire work and independent 909 work can continue. Bring up the other ColdFire device using the same kernel.

| Shared model slice | Oracle | ColdFire | SHARC+ |
| --- | --- | --- | --- |
| 808 body | [#9](https://github.com/simonjohansson/x0z/issues/9) | [#42](https://github.com/simonjohansson/x0z/issues/42) | [#10](https://github.com/simonjohansson/x0z/issues/10) |
| 808 Decay | [#41](https://github.com/simonjohansson/x0z/issues/41) | [#43](https://github.com/simonjohansson/x0z/issues/43) | [#11](https://github.com/simonjohansson/x0z/issues/11) |
| 808 excitation/attack | [#12](https://github.com/simonjohansson/x0z/issues/12) | [#44](https://github.com/simonjohansson/x0z/issues/44) | [#13](https://github.com/simonjohansson/x0z/issues/13) |
| 808 feedback/pitch sigh | [#14](https://github.com/simonjohansson/x0z/issues/14) | [#45](https://github.com/simonjohansson/x0z/issues/45) | [#15](https://github.com/simonjohansson/x0z/issues/15) |
| 808 Tone/Level/output | [#16](https://github.com/simonjohansson/x0z/issues/16) | [#46](https://github.com/simonjohansson/x0z/issues/46) | [#17](https://github.com/simonjohansson/x0z/issues/17) |
| 909 triangle/reset/shaper | [#25](https://github.com/simonjohansson/x0z/issues/25) | [#47](https://github.com/simonjohansson/x0z/issues/47) | [#26](https://github.com/simonjohansson/x0z/issues/26) |
| 909 Tune/pitch | [#27](https://github.com/simonjohansson/x0z/issues/27) | [#48](https://github.com/simonjohansson/x0z/issues/48) | [#28](https://github.com/simonjohansson/x0z/issues/28) |
| 909 tonal amplitude/Decay/Level | [#29](https://github.com/simonjohansson/x0z/issues/29) | [#49](https://github.com/simonjohansson/x0z/issues/49) | [#30](https://github.com/simonjohansson/x0z/issues/30) |
| 909 pulse/noise attack | [#31](https://github.com/simonjohansson/x0z/issues/31) | [#50](https://github.com/simonjohansson/x0z/issues/50) | [#32](https://github.com/simonjohansson/x0z/issues/32) |

| Backend acceptance | ColdFire | SHARC+ |
| --- | --- | --- |
| 808 history | [#51](https://github.com/simonjohansson/x0z/issues/51) | [#18](https://github.com/simonjohansson/x0z/issues/18) |
| 808 fidelity | [#52](https://github.com/simonjohansson/x0z/issues/52) | [#19](https://github.com/simonjohansson/x0z/issues/19) |
| 909 history | [#53](https://github.com/simonjohansson/x0z/issues/53) | [#33](https://github.com/simonjohansson/x0z/issues/33) |
| 909 fidelity | [#54](https://github.com/simonjohansson/x0z/issues/54) | [#34](https://github.com/simonjohansson/x0z/issues/34) |

Every kernel slice exports direct fixture results immediately. Each ready cell consumes it through the continuing adapter regression command established by its first-body issue; retain a small audible observation for relevant control/attack changes. A blocked device does not prevent kernel acceptance or another device's progress. Its missing integration evidence remains visible in its own tracker. Final qualification checks the accumulated per-slice evidence rather than introducing the complete pipeline.

Bring up both models incrementally in this same mod. As soon as both first
bodies are available on a device, test mixed 808/909 tracks, saved MODEL values,
voice isolation and switching during tails. Keep those tests through every
later slice. A partial cell can progress independently; a releasable device
artifact must contain and qualify both engines. Per-device qualification waits
for the other model's first integration, not its complete fidelity work, so
coexistence is exercised early rather than as a final integration project.

## What each test proves

| Test | Owns | Remains separate |
| --- | --- | --- |
| C UI tests with native-service fakes | Production declarations, defaults and control mapping | Sound synthesis and physical controls |
| Independent high-precision oracle | Circuit/model behavior and discretization | Production instruction behavior |
| Actual assembled CPU runner | Numeric accuracy, ABI preservation, state and buffer bounds | Hardware instruction qualification and deadlines |
| Cross-CPU report | Matched raw outputs against the oracle and each other | Native routing, AMP and device timing |
| Per-device integration | Delivered events/values, raw-to-native conversion, routing | Full timbre or hardware qualification |
| Physical cell qualification | Exact firmware, workload, persistence, coexistence and measured timing margin | Original Roland hardware fidelity |

Compare physical settings and event times, not identical native knob words. Preserve raw onset and gain; report any alignment separately. Use fixed-seed noise for deterministic kernel checks and statistical comparisons for uncontrolled reference noise. Each backend passes against the independent oracle even when its peer is missing. Cross-CPU results are required when both matching slices are available, but an unavailable peer is not a blocker to an independently passing cell.

Digitone's custom path runs on the main ColdFire and overwrites stock FM audio; explicitly handle the machine companion's AMP/velocity reapplication. DN2 has stock AMP/filter processing downstream and its documented trigger-edge latency. Keep intrinsic kick decay and shared semantic events separate from these device behaviors.

Current DN2 code/data allocation can be expanded if it obstructs fidelity. Record usage and concrete upstream needs, while measuring CPU time separately. Neither a host pass, emulator pass nor a larger allocation establishes sustainable polyphony. Required failing checks stay open; fixes are bounded follow-up issues, not silent tolerance widening.

The backlog retains native GitHub blocked-by links and parent/sub-issue relationships. Current implementation uses private test interfaces, with firmware integration still separately gated. No release or real-device operation has occurred.
