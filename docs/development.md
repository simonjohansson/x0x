# Development and verification

The scaffold has independent host, C adapter and assembled CPU tests.
The synthetic probe is test equipment, not an 808/909 implementation or a VST
reference. Production audio will use assembly; native pages and full firmware
adapter tests remain separate work.

The product is one combined x0z mod per device, containing both engines behind
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
mise run test:emulators    # all four bounded instruction suites
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

The three `test:dt`, `test:dn` and `test:dn2` tasks currently return JSON status
`unavailable` and exit **77**. They must not look successful until their native
firmware adapters have actual integration coverage. CPU tests also use 77 for
missing tooling; validation failures use 1 and passing checks use 0. Host tests
remain runnable when unrelated target tooling or firmware is absent.

digiemu's native JIT needs executable-memory permission. In the Codex sandbox
used during setup, the ColdFire process terminated with SIGILL; the same bounded
command passed when run with the executor's required native-code permission.
Digikit's instruction interpreter and the host/C tests ran inside the sandbox.

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
mise run test:dn:transport  # 40 ms of standard non-strict full-OS Core event observation
```

Each command emits a JSON report on stdout; use `> out/<name>.json` to retain it.
Failures return 1 and unavailable prerequisites return 77. These commands cover
different layers and do not replace the full firmware gates:

| Device | Implemented evidence | Still required for its adapter foundation |
| --- | --- | --- |
| DT, OS 1.54 | C-to-ASM component; 105 bounded stock/SDK routine calls with 53 edit/smoothing/lock/LFO observations; full OS PLAY-to-START-to-C/ASM observer | Machine selection/replacement routing, native lifecycle/onset and downstream audio |
| DN, OS 1.44 | C-to-ASM component and pinned companion; bounded native edits; final-frame observer through existing Core events, tested in bounded native stages and a standard full-OS Session | Production adapter consumption of final controls, native UI/MIDI/lock sources, allocator/lifecycle and audio timing; strict-model qualification |
| DN2, OS 1.12 | Host C trace fed to the actual SHARC diagnostic; 82 executions of the pinned upstream bridge with synthetic stock DSP frames across sixteen slots | Coupled OS encoder/MIDI/lock/smoothing transport, native identity and downstream processing |

The DT native test executes real routines from the verified Core/companion
baseline but supplies bounded initial state itself. DN's companion test compiles
the actual pinned `machines.c`, supplies synthetic voice frames, and reads ranges
from the verified stock parameter table. Its native live-edit test exercises the
actual target buffer; it does not establish that this is the final modulated
render frame. The native smoother/Core event probe observes
`370, 730, 1078, 1416, 1744, 2062, 2370, 2670` while the adapter reads target
`12345` throughout. Its passing diagnostic explicitly reports
`render_frame_delivered: false`; [#75](https://github.com/simonjohansson/x0z/issues/75)
tracks the missing delivered-control route. Neither bounded routine test boots
the full OS.

The DN final-frame harness builds its own verified Core/companion and generated
observer under `out/dn/transport`; earlier prototype artifacts are not required.
`test:dn:frame` runs six native sequences with explicit target, controller and
LFO-state injection. The observer consumes the captured bank only inside the
same render interrupt, then invalidates it; entry and exit also invalidate it.
Five final-frame copies pass, while one deliberately missing capture leaves the
previous snapshot untouched. The run checks 3,166 frame reads inside the 1264-byte
view and observer writes inside its own state/stack. Real native final values
are `2402, 2761, 3109, 3447, 3775, 4093`, distinct from target 12345.

The separate `test:dn:transport` boots OS 1.44 and observes 59 complete standard
`Session(hle=False)` cycles over 40 ms, with 37,347 guarded reads, alternating
banks and exact in/pre/controller/LFO/final/late/out order. It uses non-strict
emulator settings. The earlier strict baseline and observer both flag a stock
read at `0x4009de90` of `0x12a` with A0=0; that model/setup limitation remains
explicitly unavailable in the report. Neither mode feeds the production adapter
yet or proves native lock/allocator behavior. The reports retain
`production_adapter_consumption: false`; #75 remains open.

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
reach SHARC directly through the SDK bridge; actual ASM selector execution is
tracked in #76, not established by these C reference tests.

### Coupled DN2 setup blocker

The pinned Digikit coupled emulator also needs the complete ADSP-2156x hardware
manual text at `vendor/digikit/out/refs/adsp-2156x-hwr/all.txt` to construct cold
MMR reset state. The public source is the
[ADI hardware reference](https://www.analog.com/media/en/dsp-documentation/processor-manuals/adsp-2156x_hwr.pdf).
The download failed in this environment; the located mirror failed certificate
validation. No incomplete reset table was substituted. The manual and extracted
text belong in ignored research/build storage, not Git.
Its recovery URL and failed retrieval status are retained in the tracked
[component manifest](../research/manifest-components.json), source S42.

The firmware-free strict transpilation completed with 338 functions translated,
zero untranslated functions and 185 explicit trap sites. The subsequent
`tools.emulator.ready` command stopped on that missing text before native build
or OS boot. To resume with the complete manual available, follow the pinned
Digikit [source preparation](../vendor/digikit/docs/sharc/SOURCES.md) and
[emulator commands](../vendor/digikit/README.md#run-the-emulator). Preserve the
full reset-table validation and bounded execution; a generated core is not a
passing coupled-emulator test. Foundation [#7](https://github.com/simonjohansson/x0z/issues/7)
remains open for that work.

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
SDK-verified `out/<target>/x0z-baseline.syx`, tagged `X0Z0`, for later emulator
integration. These images contain no x0z machine, and packaging does not prove
an emulator boot. The build records the output hash and refuses unexpected stale
dependency artifacts. Older profiles inside
Elekloader do not expand the supported OS set. New official firmware requires
an explicit baseline/profile update rather than a fallback to an old version.

VST selection, plugin captures and calibrated kick-fidelity gates remain deferred.
All runs in this phase use host test equipment or the required emulators; no
real device is operated.
