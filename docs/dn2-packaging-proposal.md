# DN2 packaging and persistence proposal

**Approved packaging and saved-control contract for
[#23](https://github.com/simonjohansson/x0x/issues/23), 26 October 2026.**
The user selected one synth with a selector and explicitly approved ID 20
and switching at START with old-model tail clearing. The later explicit
revision removes LEVEL, moves the sound controls to A/B/C and keeps MODEL
in F; the table below is the current approved layout/defaults.
Production declarations and tests are implemented separately in #6/#24; this
decision is distinct from native persistence, lifecycle or audio qualification.
The subsequent #7 silent milestone passes native coupled boot, controls, mixed
tracks and project save/reload. Restart persistence, broader lifecycle and kick
audio remain #9/#25/#20 work. The [private contract](render-contract.md) still applies.

## Selected packaging direction

This is the DN2 binding of the [one-mod requirement on all three devices](render-contract.md#one-combined-mod-on-every-device).

The selected direction is **one registered synth with an 808/909 selector**.
Each sound saves its model selection and controls, so both models can coexist
on different allocated voices in one firmware image. This uses the pinned
single-registration path and puts both kernels in one SHARC payload. Start
with the 808 implementation, retaining this packaging direction for the 909.

The approved contract uses **ID 20**, the name, FM TONE host type, slots/defaults and switching
policy below. IDs 18/19 were earlier review candidates only and were never
adopted; there is no existing production format to migrate.

## Current upstream SDK

The 28 October 2026 dependency update pins PR #211 head
`3ce40f6faaf87166c4a34ad1f6f48bafc3085991`, assuming its merge. The owner is
64 KiB, with a guarded L1 callback stack and an appended callback state pointer.
Its `mk2_synth` descriptor no longer
has a `clone` field: all custom SHARC synths use FM TONE as their stock host.
x0x retains that same host behavior and requires Core 0.2. ID 20, names,
parameter slots/defaults and MODEL/START policy are unchanged. Current runtime
qualification is recorded in [development](development.md).

## Original PR200 implementation audit — historical

Inspected Elekloader PR #200 head
`2ab5f424c4721e4277d2112a5ae755d9938f50d6`, DN2 OS **1.12** only:

- `mk2_synth` registers ID **5..31**, clone/default type, name and label.
  `machines-dn2` can represent multiple voice descriptors on the C side, but
  `link.check` requires each SHARC payload to have exactly one matching native
  voice registration, and allows only one voice payload per firmware. One
  separate SHARC filter may coexist. A stock clone supplies no custom DSP.
- `voice_artifact` and `module_payload` carry one `machine_id` and render entry.
  The linker writes that pair at `0x20093e00`. The actual bridge compares the
  voice frame's machine type with that single ID before invoking that entry.
  Adding a second C descriptor or a second branch inside the kernel alone
  cannot admit another native SHARC machine ID.
- A declared page has eight knobs, with integer defaults **0..127**. Page `p`,
  knob `k` persists in sound slot `25 + 8p + k`, and arrives as
  `param[8p+k]`, unsigned 8.8 **0..32512**, after native processing. The current
  companion allocates **five custom pages in total**, through `used_pages` and
  `ADDED=40`; x0x's one shared page fits that capacity. Empty positions have
  stored data too; they are not safe implicit
  version markers or guaranteed-zero future controls.
- A callback receives one of sixteen voice slots, pitch, START and forty knob
  words, without a track ID, logical ownership token, model ID or separate
  accent field. Its trigger-edge block is silent; START arrives in the next
  settled block. Native control edits can be fractional, smoothed and modulated.

## Packaging decision

| Design | Status for x0x |
| --- | --- |
| One registered machine containing both engines, with a saved selector per sound | Required on DT, DN and DN2; mixed 808/909 voices share one installed build. |
| Separate one-engine firmware variants or separate 808/909 machines | Superseded and excluded from the delivery plan. |

The earlier alternative IDs 18/19 were never adopted. They are not future
registrations for x0x. Both kernels belong in the same ID-20 SHARC payload.

With `machines-dn2` retained, an absent synth ID 5..31 is preserved on load,
reported as MISSING by name accessors and mapped to silent MIDI DSP type.
Missing synth CC/NRPN lookups do not target MIDI-track values. Removing the
companion restores stock loading behavior, which may clamp the unknown ID to
FM TONE. These are inspected implementation paths, not a completed x0x
project/sound round-trip qualification. Do not overwrite the only saved copy
while checking missing registrations.

## Approved layout

Approved **ID 20**, name **`X0X KICKS`**, short label **`KICKS`**,
host type **0 (FM TONE)** and one SYN page. Upstream now fixes that host
without a descriptor field. It supplies stock defaults, permissions and
positional MIDI mapping; the kick still renders in the custom SHARC kernel. Native assignment and stock-track coexistence pass in #7; audible
AMP/filter behavior remains qualification work once the kick engines exist.

| SYN1 knob | Sound slot / callback parameter | Static label and meaning | Integer default |
| --- | --- | --- | --- |
| A | 25 / 0 | `TNTUN`, 808 Tone / 909 Tune | 64 |
| B | 26 / 1 | `DECAY`, selected model's decay control | 64 |
| C | 27 / 2 | `ATTK`, 909 attack branch; ignored in 808 | 64 |
| D | 28 / 3 | undeclared | no declaration |
| E | 29 / 4 | undeclared | no declaration |
| F | 30 / 5 | `MODEL`, 808/909 selector | 0 |
| G–H | 31–32 / 6–7 | undeclared | no declaration |

These are initial positions, not calibrated Roland factory presets: 64 means
64/127 of the eventual physical control mapping. Native track level handles
volume; the renderer uses fixed internal output calibration, with no separate
x0x LEVEL knob or saved gain. Trigger strength
is deferred to native velocity/accent and downstream AMP research; E stays
undeclared. Fixed strength belongs in test fixtures only and does not establish
a production strength policy. Ordinary note pitch must not turn the 808 into a
tuned bass engine. `TNTUN` is an explicit five-character compromise: `TONE/TUNE`
exceeds the SDK label limit, and the current page API supplies static labels.
Check ID conflicts against every selected mod before approval; no global
allocator establishes that ID 20 is universally free. MIDI numbers must be
verified from FM TONE's actual slot mappings, not invented here.

Approved combined-selector policy:

- Quantize the **delivered** MODEL word to 808 for raw `0..16383` and 909 for
  `16384..32512` (threshold 64.0). Default 0 selects 808. No interpolation or
  hysteresis. Fractional values and LFO/lock/MIDI crossings follow the same rule.
- Latch that choice only at a delivered START, after the settled controls.
  A selector edit during a tail takes effect at the next START on that voice;
  unrelated active voices retain their own selected model. At the boundary
  that changes a voice's model, discard its old model state and initialize the
  new model before excitation. Do not render a crossfade or both tails.
- Same-model retriggers retain the shared circuit model's residual-state
  policy. START alone cannot prove fresh ownership or distinguish reassignment;
  native identity/reuse work remains a prerequisite to claiming that behavior.
  A slot without an established model must not expose stale state.

These are block-delivery semantics, not sample-accurate encoder timing. Persist
the selector word with the sound; do not serialize live DSP tails. Repeated
note locks, model changes during release and slot reuse require explicit tests.

## Preserving the first 808 sounds

No released x0x sounds require migration. The explicitly approved compact-layout
revision supersedes the earlier development-only LEVEL/B/C/D layout; existing
local development sounds must be recreated rather than silently reinterpreted.
IDs 18/19 remain unadopted alternatives. Preserve the current approved ID, selector encoding,
slots, ranges and meanings when adding the 909. In particular, keep MODEL 0
meaning 808. Do not reinterpret empty slots or assume their saved contents
equal a newly added default. Defaults run on synth selection, which does not
prove migration of old sounds. Future layout changes need separate review.

Switching the native synth or loading another sound has separate host voice
allocation/tail behavior that is not established by the isolated bridge tests.
Do not promise tail preservation there. Firmware replacement always ends the
running performance. The installed combined mod switches per voice through MODEL.

## Memory growth and registration

The one-mod selector design requires no multiple-registration extension. Keep
one native identity while adding both kernels to its payload. The earlier
multi-ID extension discussion is superseded and is not implementation work.

The SDK default provides 30 KiB code including a 64-byte guard and 31 KiB data
including all sixteen voice states. The existing
[x0x private allocation](dn2-private-layout.md) instead provides
**8,128 usable author-code bytes** (8 KiB minus the same 64-byte guard) and
**53 KiB author data**, including all per-slot state, retaining legacy ASM
addresses. Both partitions fit the 64 KiB voice owner. The separate filter
owner is now `0x200a0000..0x200b0000`. Saved layout, one-ID bridge, linker
cardinality and page allocation are unchanged. Actual code/data
usage and workload qualification remain separate; this allocation change does
not establish realtime or reference-fidelity acceptance.

## Acceptance and unresolved decisions

The single-synth direction, exact ID/name/host type, slots/defaults, selector encoding
and tail-switch policy are approved. Strength research remains open; no strength
control is declared.
Then test incrementally: C declarations and exact raw conversions; SHARC dispatch,
per-slot state and guards; coupled-emulator selection/locks/modulation; sound
save/reload/copy and missing-mod round trips; active tails and model/slot changes;
stock-track coexistence and downstream AMP/filter behavior. Keep reference
timbre comparisons and physical deadline qualification separate. Current tests
execute host C traces and the actual bridge with synthetic DSP frames; they do
not establish native persistence or allocator behavior.

## Original inspected sources — historical

All upstream links below are pinned to PR #200 head, not a moving branch:

- [SDK artifact producer](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/elekloader/sdk/sharc.py): `machine_layout`, `voice_artifact`, `_machine_artifact`.
- [Artifact validator](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/elekloader/sharc.py): `module_payload`.
- [Linker](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/elekloader/link.py): `check` registration/cardinality checks and `link` binding writes.
- [DN2 profile](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/elekloader/devices/digitone_mk2.py): voice/filter ranges and reservations.
- [Machine companion](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/mods/machines-dn2/machines.c): `dn2_ensure`, `build_pages`, `valid_pages`, missing-ID/type/MIDI paths.
- [Actual bridge assembly](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/mods/machines-dn2/voice-bridge.s): single-ID compare, settled START, forty words, `stock_slot` cleanup.
- [Native declarations](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/elekloader/sdk/include/mk2/machines.h), [voice ABI](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/elekloader/sdk/include/digitone-mk2/voice.h), [voice documentation](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/docs/MACHINES-DN2-VOICE.md), [missing-mod behavior](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/docs/MACHINES-DN2.md).
- [Upstream registration/link tests](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/tests/test_sharc_voice.py) and [C companion checks](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/tests/test_dn2_machines.c); local [current evidence boundaries](development.md) and [private contract candidates](render-contract.md). Sources were inspected; no new save/load or audio experiment was performed for this proposal.
