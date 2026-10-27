# Development and verification

The [silent three-device milestone](implementation-plan.md) is accepted in
closed issues #39, #40 and #7. Digitakt reset shortcuts remain a known bug
deferred to #78. The first audible increment of #9 now runs in all three
emulators; its [body model and current evidence](808-body.md) record the exact
scope. The detailed checks below preserve earlier evidence, not a prerequisite
queue. Historical #75 and matrix links are superseded provenance.


The scaffold has independent host, C adapter and assembled CPU tests.
The synthetic probe is test equipment, not an 808/909 implementation or a VST
reference. The current 808 body uses actual ASM and an independent analytical
oracle; the full 808 circuit and 909 remain unimplemented. Native pages, packaging
and full-OS coverage are recorded per device below.

The product is one combined x0x mod per device, containing both engines behind
a saved MODEL selector. Different tracks can run 808 and 909 concurrently.
Model-specific test commands and incomplete diagnostic builds are development
slices; they do not define separate products or releasable one-engine variants.

## Setup

Start from the repository root on macOS with mise and Homebrew available:

```sh
git submodule update --init
mise trust
mise bootstrap
```

Mise selects Python 3.12.13, Clang 23.1.3, CMake 4.4.4, uv 0.11.8 and Rust
1.98.1. Its package bootstrap installs the `m68k-elf` GNU tools. The bootstrap
task prepares digiemu's locked Python environment and patched Unicorn, then
builds Digikit's pinned public SHARC assembler/linker locally. No proprietary
toolchain is required. Re-running `mise run bootstrap` prepares the environments
again after the tools are installed.

The dependency revisions are Git submodule pins, not floating branches:

| Dependency | Pin | Purpose |
| --- | --- | --- |
| Elekloader | `2ab5f424c4721e4277d2112a5ae755d9938f50d6` (PR 200) | Firmware profiles, build/patch tools and matching DN2 voice interface |
| digiemu | `f57c2f237e84b8ff91bc3adb2a2931bccf9928e9` | Digitakt/Digitone ColdFire instruction and later firmware tests |
| Digikit | `d0a4d76d533d7181ea5eee548ca68edaa8d49c35` | Digitone II SHARC instruction and later firmware tests |

Selache is built at Digikit's pinned revision
`2b26d3b75c53063575bc5c820fa0d38879335187` under its ignored `out/tools/`.
The CPU report records tool versions/hashes, emulator and SDK revisions, source
and image hashes, and the project revision/dirty state. Never substitute a
different emulator installation for the pinned submodule.

## Independent checks

```sh
mise run test              # host tests and all compiled C adapter boundaries
mise run test:host         # no assembler, firmware, emulator or native pages
mise run test:ui           # common controls plus DT, DN and DN2 C adapters
mise run test:ui:dt        # Digitakt C alone, no assembler/emulator/firmware
mise run test:ui:dn        # Digitone C alone
mise run test:ui:dn2       # Digitone II C alone
mise run test:ui:dn2:controls  # approved combined pages/selector; fake DSP, no renderer
mise run test:ui:coldfire  # no unsupported runtime imports in the target object
mise run test:coldfire     # assemble and execute in digiemu
mise run test:sharc        # assemble and execute in Digikit
mise run test:coldfire:arithmetic  # fixed point, full EMAC context and event fixtures
mise run test:sharc:callback       # pinned callback input, context and slot state
mise run test:coldfire:selector   # shared DT/DN per-lane model selection, no audio
mise run test:sharc:selector      # actual DN2 selector callback against host C policy
mise run test:emulators    # all six bounded instruction suites
```

The C boundary forwards declared stock controls as exact normalized fractions
`raw/maximum`, retaining delivered fractional values and rejecting invalid
ranges/undeclared controls before calling the receiver. The backend chooses its
numeric representation; C requires no software floating-point runtime helpers.
It does not register native pages, reserve machine IDs or assign saved slots.

Both CPU diagnostics write a 32-sample block for silence and positive/negative
quarter scale. They check buffer guards and selected preserved registers, and
reject reassembled skipped-output, overrun and register-corruption variants.
The stronger ColdFire arithmetic suite runs a handwritten saturated Q1.31
multiply/accumulate probe against independent integer expectations, including
40-bit product and 32-bit extraction ties. It checks all four accumulators,
extension words, MACSR, MASK, callee registers, stack and every guest write.
Sixteen diagnostic state lanes and event fixtures test reset, retrigger,
reassignment, parameter ordering and muted-state continuity; this is not a
claim of sixteen native hardware voices. The shared probe matches the host
oracle within its declared two-LSB error bound, with measured error reported
for each run. Eight reassembled defective programs must fail.

The DN2 callback suite compiles static layout assertions against the pinned
20-byte header, checks the SDK code/data bounds and executes the short-word C
return. It exercises 16 persistent slots, START, fractional delivered controls,
interleaving, guarded input/output and modeled register/stack/accumulator state.
Every guest write is checked, including low RAM and memory-mapped controls.
Seven defective callbacks must fail. Instructions are independently decoded,
and the known malformed negative-immediate shift is rejected while its
register-count workaround is executed. The initial diagnostic uses 150 code
bytes, 128 state bytes and no additional kernel stack beyond the caller's
eight-byte frame. Instruction counts describe emulator work, not CPU time.

These suites establish the private kernel boundary under the pinned emulators.
The native allocator, UI-to-DSP transport and downstream firmware processing
remain device-adapter work. Digikit does not model every 40-bit register
extension behavior; physical instruction behavior and timing remain unqualified.

### Combined-model selector diagnostics

The ColdFire selector is a shared private C-stack-callable ASM primitive for
DT/DN. Its eight lanes hold initialized/model/diagnostic-tail words. It emits
model/initialize/change/clear metadata, renders no audio and never infers native
freshness: fresh/missing/stale is supplied by the caller. The 160-case suite
checks threshold 16384, trigger-only latching, pending tail edits, same-model
retention, per-lane clearing, invalid inputs, every write, callee registers and
all eight EMAC snapshot words. Eight reassembled defective variants fail.
The test image is 472 bytes including its context wrapper, the state bank is
96 bytes, and combined wrapper/nested stack extent is 32 bytes. Worst case is
116 emulated instructions including the wrapper, under a 1,000-instruction bound.
Valid, aligned, disjoint caller-owned pointer extents are private ABI preconditions.

The SHARC selector callback executes directly on 189 synthetic SDK frames,
compared with the compiled host C policy. It covers all sixteen slots, 148
initialized callbacks and 25 invalid frames. Invalid or inactive deliveries
permit no selector-state writes, even transient writes later restored; a
reassembled write-before-validation defect verifies this guard. Six defective
variants fail. For a supplied input/output frame the diagnostic writes 32 floats;
its checksum/tail signal is test equipment, not either kick model. The callback
uses 440 code bytes, 128 state bytes and no additional kernel stack beyond the
existing eight-byte bridge call frame. Worst case is 351 instructions under a
1,000-instruction bound. Required modeled context and all writes are checked.

These counts use the latest approved A TNTUN/B DECAY/C ATTK/F MODEL layout.
No LEVEL control is delivered; native track level handles volume. D/E/G/H are
ignored. Four formerly invalid-D cases disappeared because D is now blank;
malformed blank-D words are explicitly covered as ignored inputs.

These diagnostics implement the common selection behavior in actual ASM;
their private state/status encodings differ by CPU. They do not install the
selector into firmware, establish logical ownership, or qualify native control
transport, persistence, upstream bridge integration or render deadlines. Neither
kick engine is implemented by these diagnostics.

The three `test:dt`, `test:dn` and `test:dn2` tasks now run each device's native
silent-mod acceptance scenario. DN and DN2 pass; DT returns1 for its recorded
native reset failures. These tests cover plumbing, not implemented kick engines
or release qualification. Missing supported prerequisites use unavailable/77;
validation failures use1 and passing checks use0. Host/CPU checks remain
independent of native firmware setup.

digiemu's native JIT needs executable-memory permission. In the Codex sandbox
used during setup, the ColdFire process terminated with SIGILL; the same bounded
command passed when run with the executor's required native-code permission.
Digikit's instruction interpreter and the host/C tests ran inside the sandbox.

## Current first-body checks

```sh
mise run test:808:body  # actual ColdFire and SHARC bodies, oracle and cross-CPU comparison
mise run test:dt        # actual DT audio; retains the known #78 reset failures
mise run test:dn        # actual DN audio and native controls/locks/LFO/persistence
mise run test:dn2       # coupled DN2 audio and native controls/locks/LFO/persistence
```

The current native runners build the production 808 body and capture downstream
PCM. 808 output must be finite and nonzero; the 909 branch remains zero and
unrelated stock output is preserved. DECAY now changes the body feedback loss
on each delivered block. Tone and 909 Attack do not yet shape the body. Existing `:silent` task/module names are retained
as compatibility aliases; they now exercise the first-body mod. Direct body
reports/samples live in `out/coldfire/body808` and `out/sharc/body808`; native
captures remain under `out/{dt,dn,dn2}/silent`. See [808-body.md](808-body.md).

The silent milestone counts below describe the completed pre-audio versions.
Current commands regenerate reports for the first-body implementation instead.

## Silent Digitakt mod

The real ID80 `X0X KICKS` registration now builds from `machines/digitakt`.
It uses the approved A TNTUN/B DECAY/C ATTK/F MODEL layout, existing ColdFire
selector and a 32-sample ASM zeroing routine. Native track level handles volume;
D/E/G/H have no semantic control. Hidden D retains the SDK's `CM_NOT_SAMPLE`
flag so SRC does not cycle into the stock sample view.

```sh
mise run test:ui:dt              # declarations and dispatch with host fakes
mise run test:dt:silent          # compiled C + actual ASM, fake native services
mise run test:dt:silent:full-os  # build firmware, native panel/UART smoke
```

Eight component scenarios pass, including mixed tracks, next-START switching,
invalid delivery and leaving/re-entering x0x. The standard full-OS run boots
the latest-OS mod and selects ID80 through the native menu. Across 21,260 real
callbacks, 19,745 with x0x selected, selected buffers are zero and other track
buffers are unchanged. Native UART controls and next-START MODEL switching pass.
The native LFO yields 1,101 distinct delivered values over 0..32512; a sequencer
DECAY lock delivers 21504 while preserving base 16384. Native project save and
pattern/kit reload retain all four controls and ID80. Two x0x tracks retain
different models without changing each other's sound.

The user explicitly approved `machines/digitakt/legacy-defaults.patch` on
26 October 2026. It applies only to ID80 in a build copy of the pinned companion;
vendor files/SHA and saved storage remain unchanged. Selection now loads the
approved `[16384, 16384, 16384, 0]` defaults. Reports record the patch SHA and
base/patched source hashes. Separate bounded actual-helper tests verify IDs80,
3 and122 and preservation of every other sound byte; these are not UI tests.

**The full-OS task still returns 1:** native knob+NO and SRC+PLAY reset actions
bypass the corrected range helper and restore stock B=768/C=0. Parameter/page
reset failures remain explicit in the report. The user accepted #39 and deferred
this bug to [#78](https://github.com/simonjohansson/x0x/issues/78). No additional SRC
UI routing or on-switch overwrite was introduced to conceal that SDK gap.

Reports, firmware and screenshots are regenerated under `out/dt/silent/`.
This is silent integration evidence, not kick synthesis or physical qualification.

## Silent Digitone mod

```sh
mise run test:ui:dn       # adapter and real descriptor with host-service fakes
mise run firmware:dn:silent
mise run test:dn:silent  # standard full-OS native panel/encoder smoke
```

The real ID80 machine uses the approved SYN2 A/B/C/F controls and the existing
same-interrupt final-frame reader around the companion's render callback.
Native menu selection loads the exact defaults. Native encoder edits move all
three sound controls; real panel-triggered notes latch 808 then 909, keeping a
MODEL edit pending until the next START. The first smoke observes 538 actual
callbacks with zero owned output and unchanged other voice buffers.

A small OS1.44-gated screen overlay follows the inspected OB-1 pattern, because
stock SYN envelope artwork is not replaced by parameter metadata. It draws only
the x0x SYN2 first page and leaves native input delivery intact. The smoke enters
SYN1 then SYN2: pressing SYN2 again would toggle to the deliberately unused
second page. No SDK/vendor or saved-layout change is involved.

The completed smoke observes 12,305 callbacks. A held step shows DECAY94 and
delivers raw24064 while preserving base74/raw18944. One native LFO produces
2,371 samples over17911..23026 without changing the saved base. Native project
save-as and temporary pattern save/change/reload restore ID80 and all A/B/C/F
words. Overlapping tracks0/1 select808/909 in the same build. All owned outputs
remain zero and other voice buffers remain unchanged per callback.

Reports and screenshots regenerate under `out/dn/silent/`. This completes #40's
silent milestone. Cross-boot persistence, strict timing, broader recording/copy/
PAGE modifier flows and actual kick synthesis remain later qualification; UART
input is not claimed by this panel/encoder smoke.

## Silent Digitone II mod

```sh
mise run test:dn2:silent      # actual SHARC callback, synthetic SDK frames
mise run firmware:dn2:silent  # build and verify latest-OS firmware, no OS boot
mise run test:dn2:silent:full-os  # native coupled emulator; prepared inputs required
```

The approved ID20 page declarations live in `machines/digitone2/page.c`,
separately from the host-reference delivery helper. The mod contributes one
synth/page registration and packages `targets/sharc/silence.s` through the pinned
voice artifact format. The silent callback passes 189 synthetic SDK-frame cases
across sixteen slots, with next-START selection, zero output and state/buffer
guards. It uses 390 code bytes, 128 state bytes and at most 335 instructions in
the modeled runner. SDK link validation and the installed ID20/PC16 binding pass.

The separate full-OS command now boots the installed mod through Digikit's
documented public emulator API with the verified stock base hash. Native menu
selection shows ID20 and exact A/B/C/F defaults. A held 808 voice keeps its model
after a native MODEL edit; the next note starts a 909 voice while the old 808
counter continues. Both active voice outputs are zero; final CF ready/error and
DSP halt/missing-block checks pass.

Ordinary A/B/C MIDI edits now reach both the packed native frame and actual
callback as `[25599,2562,20480]` after300frames. These are observed native-smoothed
values for requested targets `[25600,2560,20480]`; the test preserves fractions
and compares the two real delivery points rather than assuming instant settling.
T1 909 and T2 808 run concurrently. A stock T3 note uses machine0, has nonzero
finite output and leaves its x0x state clear; all selected x0x buffers remain zero.
Native temporary pattern/kit save-edit-restore retains the controls/model on a
new note. This is not persistent disk or cross-boot save/load evidence.

The completed native scenario runs14,981 DSP frames without CF error, DSP halt
or missing blocks. Native LFO changes A to25824/25733/25641/25547, matching the
actual callback exactly and preserving B/C/F. A real project save, change to
stock FM and project reload restore ID20 plus `[25600,2560,20480,32512]` and a
909 callback. T2's held lock displays74 and delivers18944 to an actual808
sequencer voice; a fresh unlocked note returns the exact64/base16384 values.

Reports and screenshots regenerate under `out/dn2/silent/`. This completes #7's
silent milestone. Persistence across emulator/device restart, actual kick audio
and physical timing remain unqualified. Packaging, synthetic callback tests and
coupled native evidence remain distinct.
Prepared upstream inputs are documented in the [setup record](#coupled-dn2-setup-blocker).

## Device adapter slices

The private adapters live under `machines/`. Callers supply control bindings;
these files reserve no permanent machine IDs or saved sound positions. They
preserve exact delivered fractions and reject a malformed frame before any
receiver notification. Native START/fresh metadata is retained without claiming
it identifies a particular analog retrigger or a newly allocated note.

```sh
mise run test:adapters       # all three firmware-independent C-to-ASM components
mise run test:dt:component   # compiled C + ColdFire ASM, native-service fakes
mise run test:dn:component   # compiled C + ColdFire ASM, native-service fakes
mise run test:dn2:component  # host-compiled C snapshots + SHARC ASM and bridge

# Require the latest local stock firmware; native calls also require the baseline:
mise run firmware:dt
mise run test:dt:native
mise run test:dt:transport  # boot OS, native PLAY -> START -> C -> ASM observer
mise run test:dn:companion
mise run firmware:dn
mise run test:dn:native
mise run test:dn:frame      # actual native stages, explicitly injected control state
mise run test:dn:machine    # generated test machine, actual companion callbacks, injected native state
mise run test:dn:endpoints  # approved final overshoot + canonical MODEL through existing ASM
mise run test:dn:transport  # 40 ms of standard non-strict full-OS Core event observation
```

Each command emits a JSON report on stdout; use `> out/<name>.json` to retain it.
Failures return 1 and unavailable prerequisites return 77. These commands cover
different layers and do not replace the full firmware gates:

| Device | Current native silent-mod evidence | Remaining scope |
| --- | --- | --- |
| DT, OS 1.54 | Real ID80 mod: native controls, p-lock/LFO, save/reload, mixed tracks and zero owned output | Native knob/page reset deferred to #78; actual audio and broader qualification later |
| DN, OS 1.44 | Real ID80 mod: complete native silent milestone in standard full-OS digiemu | Actual audio and broader qualification in #9/#25/#20 |
| DN2, OS 1.12 | Real ID20 mod: complete coupled native silent milestone, including persistent project reload and stock FM coexistence | Actual audio and broader qualification in #9/#25/#20 |

The detailed bounded/component results below are retained provenance. They do
not replace or overstate the separate full-OS results above.

The DT native test executes real routines from the verified Core/companion
baseline but supplies bounded initial state itself. DN's companion test compiles
the actual pinned `machines.c`, supplies synthetic voice frames, and reads ranges
from the verified stock parameter table. Its native live-edit test exercises the
actual target buffer; it does not establish that this is the final modulated
render frame. The native smoother/Core event probe observes
`370, 730, 1078, 1416, 1744, 2062, 2370, 2670` while the adapter reads target
`12345` throughout. Its passing diagnostic explicitly reports
`render_frame_delivered: false`; this was the gap investigated in superseded
[#75](https://github.com/simonjohansson/x0x/issues/75), subsequently resolved for
the installed silent mod in #40. Neither bounded routine test boots the full OS.

The DN final-frame harness builds its own verified Core/companion and generated
subscriber under `out/dn/transport`; earlier prototype artifacts are not required.
`test:dn:frame` runs six native sequences with explicit target, controller and
LFO-state injection. The private production reader opens at render entry,
captures the existing parameter pointer once, and permits reads only after the
late voices observer (order 40). An order-60 callback closes the view after the
companion; render exit clears it again. Parameter IDs resolve to sound slots and
ranges through the pinned SDK's documented stock records, without production
firmware addresses or a copied knob lookup table. Missing/duplicate capture,
early access and expired views fail closed; there is no target fallback.

The diagnostic maps parameter 119 to one semantic control and reads parameter
124 as raw MODEL metadata. These are test bindings, not adoption of the proposed
DN saved layout. It feeds final words through the production C adapter into
actual diagnostic ColdFire ASM, using explicitly injected voice metadata at
order 40. It does not yet exercise the companion's order-50 machine callback.
Five deliveries/copies pass; the omitted observer and production capture leaves
the previous receiver/ASM output untouched and recovers next block. The run
checks 3,176 frame reads inside the 1264-byte view, immutable frame/stock audio
and subscriber writes inside its own state/stack. Final values are
`2402, 2761, 3109, 3447, 3775, 4093`, distinct from target 12345. A recompiled
adapter substituting the target buffer is rejected by the read guard.
Host-only C tests independently cover both banks, all eight slots, exact
fractions, MODEL boundary words, invalid records/ranges and view lifetime.

The separate `test:dn:transport` boots OS 1.44 and observes 59 complete standard
`Session(hle=False)` cycles over 40 ms, with 37,465 guarded reads, alternating
banks and exact in/pre/controller/LFO/final/late/end/out order. It also executes
the production adapter with the same diagnostic bindings and injected metadata.
Its settings are non-strict. The earlier strict baseline and observer both flag
a stock read at `0x4009de90` of `0x12a` with A0=0; that model/setup limitation
remains explicitly unavailable. Reports now record
`production_adapter_consumption: true` with this narrow scope. These diagnostic
modes do not establish native sources, locks, allocator/START ownership, selector
integration or audio timing. The later #40 silent-mod scenario establishes the
listed native plumbing checks; broader lifecycle, timing and kick fidelity remain
#9/#25/#20 work.

`test:dn:machine` adds a separate bounded registered-machine proof. It reuses the
self-contained build, contributing ID 127 only to ignored diagnostic firmware
under `out/dn/machine`. The existing Core dispatcher runs ready at order 40,
the actual companion and its registered callback at order 50, then invalidates
at order 60. All eight slots consume final parameter 119 plus raw parameter 124
through the production adapter; actual ASM writes each selected native voice
buffer. Seven blocks produce 55 callbacks, 47 successful deliveries and 94
mapped-frame reads. Checks include exact fractions, four interleaved tracks,
same-track retrigger, observed track reassignment, gate release, an unselected
FM lane and missing-frame recovery. Callback registers/stack, readonly metadata
and parameters, and each lane's writes are guarded. A recompiled transient
MODEL store/restore without a valid frame is rejected by the write guard; expired frame reads are
forbidden even if their values are discarded.

The same bounded test now calls the real SDK `core_sound_set(2, 27, 20001)`
between blocks 0 and 1. With injected kit/ownership state, it executes the stock
live setter and checks exactly three non-stack writes: the kit word and target
words for track 2's lanes 2 and 6. Every other target/kit byte and both cached
sound and smoother-pointer tables stay unchanged. Subsequent registered
callbacks preserve a strictly increasing fractional smoothing ramp below the
new target. Lane 2's pre-controller/final words begin `377/2409`, then
`966/2997`, `1537/3568`; lane 6 begins `391/2423`, then `979/3010`,
`1550/3581`. Replacing the verified stock live-target store with two NOPs is
rejected even though its kit write still occurs. This proves a bounded native
SDK edit route; panel/MIDI input, locks and timing remain separate.

The same command applies a prepared native lock list to voice 1, slot 27,
value 17003 before block 2, then restores 12458 from its sound record before
block 4. It executes the reviewed stock apply/restore routines, with bounded
reads and exactly three non-stack writes each: one target word, its lock-bitmap
word and its Q16 smoother word. Full target/bitmap/smoother/kit snapshots preserve
other voices and the kit; the prepared list is readonly. Unlike live edits,
these helpers reset the smoother directly: voice 1's pre-controller/final words
change from `736/2767` to `17003/19034`, then `12458/14489` on restore. The other
voice on the same track stays isolated. Removing the stock lock target store
fails the intended validator even though the lock bit/smoother still update.
This is direct helper execution with a prepared SDK-format list, not native
sequencer/p-lock event dispatch or editor qualification.

The bounded fixture also routes decoded CC1 value 127 for track 0 through the
stock MIDI CC router and Core dispatcher. Stock code writes raw controller 32767
and its MSB cache; it does not write the render control table or voice targets.
The stock controller producer then runs after controllers/LFOs, preserving
its native ordering. Its Q31 states start at the stock image's `0x40000000`,
without an injected settled value. The test checks the exact recurrence,
rounding, table ownership and all 32 producer writes per pass. Produced values
start `983, 1936, 2861, 3758`; the current controller pass consumes the previous
pass's value, starting at zero. Registered callbacks receive the resulting
fractional contribution only on voices currently owned by track 0, including
isolation when a voice changes tracks. Omitting the producer fails the intended
next-block table check even though decoded CC input still updated raw state.

CC2 breath now runs alongside CC1 on track 0 with a distinct input: CC2=64
produces raw 16513. Its independent settled sequence starts
`495, 976, 1442, 1894, 2333, 2758, 3171`, with the same later-pass consumption.
The native controller stage sums separately truncated mod-wheel (1/8) and
breath (1/16) contributions before the registered callback; reassigned voices
stop receiving both track-0 sources. Independent raw/cache/Q31/table checks
reject a mutated breath record that reads the mod-wheel source. The fixture's
55 callbacks, 47 deliveries and 94 mapped-frame reads are unchanged.

Channel pressure adds a separate prepared-message path: bytes `D0 20` enter the
actual handler at `0x400ea1ee`. The bounded slice performs its first channel
lookup, scaling and raw setter, then stops at `0x400ea294` before UI telemetry.
Configured channel 0 maps to track 0; auto channel is 15 and the other configured
channels differ. The readonly message/arguments and exact stack displacement
are checked; the only non-stack write is raw pressure 8256 at `0x80004630`.
Its independent producer table at `0x80004670` yields
`248, 488, 721, 947, 1166, 1379, 1585`; descriptor offset 68 contributes 1/32
alongside mod wheel and breath. A mutation that feeds pressure from breath's
raw source is rejected. The fourth normal-DN producer record is channel
pressure; the first record (`0x80004648` to `0x800046a0`) is pitch bend.

This covers one prepared channel-pressure message through a native handler
prefix and registered callbacks. It does not complete the handler, execute its
UI telemetry or qualify byte-stream parsing, other channel-routing paths,
polyphonic aftertouch or full-OS input timing.

This is decoded-router/native-stage evidence with injected receive and mapping
configuration. It does not exercise raw MIDI byte parsing, USB/DIN input,
other controllers, or full-OS MIDI-to-audio latency. The producer's control-table
delay and the separate stock DSP/audio delay remain distinct.

This fixture uses `DNM_OWN_ENV` to isolate transport from companion gain; it
adopts no production envelope flag, machine ID or saved layout. Initial targets, the
legacy per-voice controller/LFO state, pitch/track/gate and companion note
events are injected.
In the real OS, `core_voice_on` follows `core_render_voices`; calling
`dnm_voice_on` before the diagnostic dispatch therefore does not qualify native
START/frame alignment. The standard full-OS observer above still uses its
order-40 diagnostic receiver, not this registered machine. Complete mappings,
MODEL latching, native sources/locks, allocation and audible timing remain open.

The separate DT transport test follows ModelDigi's full-OS test pattern:
`Session(hle=False)` with `never_fake_set_posts`, native panel PLAY/STOP and a
generated `ev_render_voices` subscriber. It boots the latest firmware and calls
the production C adapter and assembled diagnostic from the real render event.
The initial run checked 1,020 callbacks, nine START snapshots and 10,026 guest
writes; guards passed and every observer left stock track audio unchanged.
The first START was render block 153 after PLAY was requested at block 149.
Session chunk timestamps are not sample-accurate onset measurements. This is an
observer test, not replacement-audio integration. Generated descriptors, firmware,
snapshots and `out/dt/transport/report.json` stay ignored; no machine ID or saved
layout is introduced. Missing machine selection, MIDI, live edits and lifecycle
tests remain explicit in that report.

DN's raw encodings must come from `dnm_knob_range`: for example, the stock HARM
record has raw bounds 9472..22784 even though its display uses -26..26. The adapter
does not apply AMP or velocity. The companion test checks their default
application once and verifies that `DNM_OWN_ENV` bypasses **both**, so intrinsic
kick decay alone is not sufficient reason to enable that flag.

DN2's C plumbing runs on ColdFire; SHARC receives the settled callback frame.
Its component serializes the host-compiled C receiver output before executing
the SHARC callback. A separate test executes the actual upstream bridge with
synthetic packed frames, including all forty halfwords, undeclared `0xffff`
values and stock-caller pass-through. It observes a silent trigger-edge block
followed by START in the next settled block. This is bridge evidence, not native
OS control delivery. Test-only machine 31 exists only in emulator memory.
Faulty C variants must be rejected: fraction loss, wrong slot and unwanted level
scaling on DN2; fraction loss, unconditional reassignment and overwritten velocity
on DN.

The approved DN2 ID-20 production declarations and C reference selector live in
`machines/digitone2/controls.c`. Their standalone C tests check the actual SDK
descriptor/pages, both models' distinct endpoint/fractional values and the
START-latched threshold at raw 16384. An edit during a tail stays pending until
START; first initialization or a model change requests tail clearing, while a
same-model START preserves residual state. Controls precede the notice. The
fake DSP tests this metadata and per-slot isolation; no DSP reset or excitation
is implemented in C. Blank E/G/H have no strength meaning. Native ownership,
save/load and downstream processing remain integration work. Settled frames
reach SHARC directly through the SDK bridge. The separate #76 ASM diagnostic
now conforms to this C reference; installed bridge/selector integration remains
part of the device work.

### Coupled DN2 setup blocker

**Resolved on 26 October 2026.** The supplied working example exposed the
complete Rev.1.0 ADSP-2156x HWR (December2020,2331pages) that pinned Digikit
expects. The unchanged extraction/parser accepts3558 reset rows,586 nonzero.
The user-provided complete Rev.1.1 is preserved too; the current parser rejects
conflicting DDE_CFG/DMA35_CFG rows in that edition. No rows were edited or
suppressed. [Source S42](../research/manifest-components.json) records both file
hashes, locations and provenance; PDFs/text remain ignored.

A fresh machine needs the pinned Digikit [shared core and source preparation](../vendor/digikit/docs/sharc/SOURCES.md)
first. The native test checks the generated fingerprint, exact stock ready-input
hash and daemon binary; missing prerequisites return unavailable/77. These are
ordinary upstream tool inputs, not x0x firmware boot code. The working preparation
commands below run from x0x root with that shared core generated:

```sh
mkdir -p out/dn2/hwr-source
ln -sf "$PWD/research/sources/adsp-2156x-hwr-rev1.0.pdf" out/dn2/hwr-source/adsp-2156x-hwr.pdf
mise exec -- env PYTHONPATH="$PWD/vendor/digikit" uv run --no-project --python "$(mise which python)" --with pymupdf python -m tools.devtools.refstext "$PWD/out/dn2/hwr-source/adsp-2156x-hwr.pdf" --out "$PWD/vendor/digikit/out/refs"
mise exec -- env PYTHONPATH="$PWD/vendor/digikit" SHARC_GEN_DIR="$PWD/vendor/digikit/out/native/shared-core/gen" uv run --frozen --project vendor/digikit --python "$(mise which python)" python -m tools.emulator.ready dn2 --syx "$PWD/firmware/Digitone_II_OS1.12.syx" --out "$PWD/out/dn2/stock-ready"
mise exec -- env PYTHONPATH="$PWD/vendor/digikit" SHARC_GEN_DIR="$PWD/vendor/digikit/out/native/shared-core/gen" uv run --frozen --project vendor/digikit --python "$(mise which python)" python -m tools.emulator.native_emu --daemon --auto-coupled --build-only "$PWD/firmware/Digitone_II_OS1.12.syx"
```

The initial direct `ready.py` attempt rejected the modified firmware's unknown
hash before CF execution. That stock-oriented helper is not the patched-image
loader. The normal documented `Emu.load` API accepts the SDK output with its
verified stock base SHA and performs the emulator reset itself. Native x0x boot
now passes using that API, as in the supplied example. The mod has no special
cold-load requirement, loader implementation, boot shim or vendor alteration.
Actual upstream boot failures will be reported rather than hidden in x0x.

## Fixtures, results and measurements

The [private contract](render-contract.md) defines settings and event meaning.
Fixture version 1 records a named model revision, sample rate/count, named voice
lanes, explicit initial reset, settings, ordered absolute-sample events and
provenance. Equal-time events retain list order. `expected_audible` is explicit
per lane: true requires nonzero output; false requires exact digital silence.
These flags validate synthetic/kernel routing, not an analog noise floor.

The diagnostic pole has a fixed sample-to-sample factor of one half. Its known
response to an impulse of strength `s` is `s * 2**(-age)` before Level. Retriggers
add excitation to residual state; reset retains settings. Diagnostic reassignment
clears state and records a new identity in the fixture provenance; it does not
prove a native allocator's ownership policy. The named lane continues to label
the output stream across that reset. Unsupported kick models/parameters fail.

Results carry the canonical fixture hash, model identity, rate/count, per-lane
raw samples, fixed full-scale convention and build provenance. Wrong routing,
truncation, non-finite values, missing provenance and fixture mismatches fail.
The oracle preserves finite over-range samples for analysis. PCM export rejects
over-range data rather than silently clipping or normalizing it.

```sh
mise run render -- tests/fixtures/diagnostic.json --out out/probe.json --wav out/probe.wav
mise run test:coldfire:arithmetic -- --result-out out/coldfire.json
mise run analyze -- out/probe.json --fixture tests/fixtures/diagnostic.json --out out/measurements.json
mise run analyze -- out/probe.wav
mise run compare -- tests/fixtures/diagnostic.json out/probe.json --coldfire out/coldfire.json --tolerances tests/fixtures/diagnostic-tolerances.json
```

The arithmetic task exports the actual assembled pole-probe output as a
fixture-matched result. The fill diagnostic and DN2 callback have their own
reports and are not implementations of that pole fixture. Comparisons fail on
mismatched provenance or an absent file. With no backend supplied the command
returns unavailable, not a passing comparison.

The analyzer accepts mono 16/24/32-bit integer PCM WAV or validated result arrays.
It reports raw onset, peak/DC/RMS/energy, clipping indicators, reliable body-cycle
frequency estimates, positive/negative decay fits and separate Hann-windowed
onset/body/tail bands. Pitch estimates exclude the first 10 ms and quiet cycles;
silence/insufficient evidence has unavailable pitch/decay rather than NaNs.
Decay applicability requires a negative approximate two-standard-error slope
interval; the report retains fit uncertainty and residuals. This ordinary
regression assumption can be violated by correlated/selected peaks and needs
later reference-specific calibration.

The comparator requires explicit tolerance values in the units named by
`TOLERANCE_KEYS`. The checked-in limits apply only to the synthetic probe and are
not timbre acceptance thresholds. Each backend is compared to the independent
oracle before pairwise comparison. Two identically wrong outputs still fail.
Missing peer output does not block a valid available backend. The Python API's
statistical mode omits waveform-null gates for uncontrolled noise; deterministic
fixtures use sample residuals. Contiguous 10 ms RMS and 100 ms band windows cover
the complete render, preventing middle dropouts or spectral changes from hiding
between the named measurement windows. Pitch/decay reports include coverage so
matching an early fragment does not imply matching a missing tail. These are
coarse measurement windows, not a complete timbre model. Explicit aligned
residuals are supplemental and never change raw timing/gain acceptance.

## Latest firmware only

The [firmware baseline](../firmware/README.md) supports only the latest official
OS for DT, DN and DN2. Its tracked manifest contains URLs/hashes; downloaded
images remain local and ignored. Obtain those images before SDK dependency
builds, then run:

```sh
mise run firmware:verify
mise run build:deps:dt
mise run build:deps:dn
mise run build:deps:dn2
```

Each build verifies the manifest image identity and matched SDK release first.
These commands build the existing core/companion dependencies under `out/`;
they do not package or boot an unimplemented kick machine. `mise run firmware:dt`,
`firmware:dn` and `firmware:dn2` additionally package those dependencies into an
SDK-verified `out/<target>/x0x-baseline.syx`, tagged `X0X0`, for later emulator
integration. These images contain no x0x machine, and packaging does not prove
an emulator boot. The build records the output hash and refuses unexpected stale
dependency artifacts. Older profiles inside
Elekloader do not expand the supported OS set. New official firmware requires
an explicit baseline/profile update rather than a fallback to an old version.

VST selection, plugin captures and calibrated kick-fidelity gates remain deferred.
All runs in this phase use host test equipment or the required emulators; no
real device is operated.

## Approved DN final-control endpoint policy

A separate bounded probe found a legitimate final control outside the stock UI
range: target 32512 plus native CC1 modulation yields final word 32634 when the
LFO targets another parameter. The ready production frame reader rejects it.
The user approved the
[DN-only endpoint policy](dn-final-control-endpoint-proposal.md) on 26 October
2026. The final reader now preserves observed raw/UI bounds while normalization
clamps only the position to its UI endpoint. `x0x_dn_frame_model` retains raw
MODEL and bounds only its canonical argument to the existing selector. The
target-accessor diagnostic stays strict, and shared ASM/SHARC contracts, DT,
DN2 and saved layouts are unchanged. Native acceptance is recorded separately
from complete model/ownership/timing qualification.

The independent `test:dn:endpoints` diagnostic replays two actual native cases
(raw 32512 and 32634) through registered callbacks, production C and the
unchanged actual selector ASM. It also runs 52 labelled synthetic/missing/invalid
MODEL cases over all eight lanes, preserving raw words above UI maximum while
passing canonical 32512 to the selector. Five recompiled defects reject clipped
raw observations, missing normalization, rescaled denominators and unbounded
MODEL. Memory/register/stack guards retain frame, voice and lane isolation.
This uses C markers, not kick audio; synthetic MODEL/START cases do not establish
native source or allocator timing. Existing target/component/control/selector
regressions and the separate standard non-strict OS observer remain independent.
