# DN2 packaging and persistence proposal

**Nonbinding review draft for [#23](https://github.com/simonjohansson/x0z/issues/23),
26 October 2026.** No ID, native layout, selector policy, schema or production
registration is adopted by this document. Approval is required before making
these persisted choices. The [private contract](render-contract.md) still applies.

## Selected packaging direction

The selected direction is **one registered synth with an 808/909 selector**.
Each sound saves its model selection and controls, so both models can coexist
on different allocated voices in one firmware image. This uses the pinned
single-registration path and puts both kernels in one SHARC payload. Start
with the 808 implementation, retaining this packaging direction for the 909.

The exact candidate **ID 20**, name, clone, slots/defaults and switching policy
below still require user review before production registration or a persisted
layout is implemented. Choosing the packaging direction does not approve those
details. IDs 18/19 were earlier review candidates only and were never adopted;
there is no existing production format to migrate.

## What the pinned implementation actually permits

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
  `ADDED=40`; a future multi-registration solution must account for that shared
  capacity. Empty positions have stored data too; they are not safe implicit
  version markers or guaranteed-zero future controls.
- A callback receives one of sixteen voice slots, pitch, START and forty knob
  words, without a track ID, logical ownership token, model ID or separate
  accent field. Its trigger-edge block is silent; START arrives in the next
  settled block. Native control edits can be fractional, smoothed and modulated.

## Options

| Option | Save/load identity and coexistence | Work and tradeoff |
| --- | --- | --- |
| One registered machine, model selector — selected | One candidate ID, with each sound saving its selector and knobs; both models can run on different allocated voices in one image. | Supported by the current packaging. Requires both DSPs in one payload, a permanent selector slot, per-voice model state and reviewed switching semantics. One static page cannot change its labels with the model through the current page API. |
| Separate firmware variants — alternative only | Separate candidate IDs 18/19; only the installed model renders. | Simpler first persistence contract, but cannot play both models in one image. Switching firmware interrupts all audio. These IDs were never adopted. |
| Upstream multiple native SHARC registrations — alternative only | Separate stable IDs and independent pages; both models coexist in one image. | Unavailable at this pin. Requires coordinated artifact, linker, bridge and test changes, rather than disabling one linker refusal. |

With `machines-dn2` retained, an absent synth ID 5..31 is preserved on load,
reported as MISSING by name accessors and mapped to silent MIDI DSP type.
Missing synth CC/NRPN lookups do not target MIDI-track values. Removing the
companion restores stock loading behavior, which may clamp the unknown ID to
FM TONE. These are inspected implementation paths, not a completed x0z
project/sound round-trip qualification. Do not overwrite the only saved copy
while checking missing registrations.

## Concrete layout candidate for review

Review candidate **ID 20**, name **`X0Z KICKS`**, short label **`KICKS`**,
clone/default type **0 (FM TONE)** and one SYN page. Clone 0 selects stock
defaults, permissions and positional MIDI mapping; it does not make the kick
use FM DSP. Its AMP/filter defaults and track assignment behavior still need
emulator checks.

| SYN1 knob | Sound slot / callback parameter | Static label and meaning | Integer default |
| --- | --- | --- | --- |
| A | 25 / 0 | `LEVEL`, linear instrument gain | 100 |
| B | 26 / 1 | `TNTUN`, 808 Tone / 909 Tune | 64 |
| C | 27 / 2 | `DECAY`, selected model's decay control | 64 |
| D | 28 / 3 | `ATTK`, 909 attack branch; ignored in 808 | 64 |
| E | 29 / 4 | undeclared | no declaration |
| F | 30 / 5 | `MODEL`, 808/909 selector | 0 |
| G–H | 31–32 / 6–7 | undeclared | no declaration |

These are initial positions, not calibrated Roland factory presets: 64 means
64/127 of the eventual physical control mapping. LEVEL 100 is 100/127 of the
declared linear level range, not a change to digital full scale. Trigger strength
is deferred to native velocity/accent and downstream AMP research; E stays
undeclared. Fixed strength belongs in test fixtures only and does not establish
a production strength policy. Ordinary note pitch must not turn the 808 into a
tuned bass engine. `TNTUN` is an explicit five-character compromise: `TONE/TUNE`
exceeds the SDK label limit, and the current page API supplies static labels.
Check ID conflicts against every selected mod before approval; no global
allocator establishes that ID 20 is universally free. MIDI numbers must be
verified from the chosen clone's actual slot mappings, not invented here.

Proposed combined-selector policy for review:

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

There are no adopted x0z DN2 production IDs/layouts to migrate; IDs 18/19 remain
unadopted candidates from the alternatives. Approve the combined layout before
publishing the first 808 sounds, then preserve that ID, selector encoding,
slots, ranges and meanings when adding the 909. In particular, keep MODEL 0
meaning 808. Do not reinterpret empty slots or assume their saved contents
equal a newly added default. Defaults run on synth selection, which does not
prove migration of old sounds. Future layout changes need separate review.

Switching the native synth or loading another sound has separate host voice
allocation/tail behavior that is not established by the isolated bridge tests.
Do not promise tail preservation there. Firmware replacement always ends the
running performance; separate variants offer no live model-switch facility.

## Alternative upstream extension, separate from memory growth

The selected single-synth direction needs no multi-registration extension.
For comparison, a minimal alternative would package **one shared voice payload**
containing both kernels and an explicit binding list for candidate IDs 18/19:

1. Extend/version the artifact contract and producer/validator to describe that
   list; retain strict duplicate-ID, clone-conflict, entry-range and stack checks.
2. Teach the linker to match all declared native registrations to bindings and
   generate a bounded dispatch table, instead of the current single entry/ID.
3. Rebuild and qualify the bridge so frame type dispatches to the corresponding
   entry. Each entry can identify its own model, preserving the current input
   structure if that is the agreed upstream design. Recheck per-slot trigger
   bookkeeping across registered-model transitions: current `stock_slot` cleanup
   only handles types outside the one accepted ID. Model reassignment/reset
   cannot be inferred from an unchanged callback slot.
4. Keep two separate one-page layouts within the companion's five-page total;
   preserve missing-ID behavior, positional MIDI/locks and original 808 slots.
   Test both models concurrently and every saved/missing registration combination.

This is a proposed upstream shape, not an available API. A second independent
payload would additionally need placement/relocation and ownership rules.

Current voice allocation gives **6,080 usable author-code bytes** (6 KiB minus
the 64-byte guard) and **7 KiB author data**, including all per-slot state.
Treat expansion as solvable if needed, as requested, while recording actual
usage. Increasing those ranges does **not** change the one-ID bridge, linker
cardinality or five-page allocation. Conversely, supporting two IDs does not
create memory or CPU time. Larger code/data ownership must be reviewed against
the adjacent filter reservation and profile/loader limits; registration,
capacity and render deadlines are three separate checks.

## Acceptance and unresolved decisions

The single-synth packaging direction is selected. Before persisted implementation,
review the exact candidate ID/name/clone, slots/defaults, selector encoding and
tail policy. Strength research remains open; no strength control is proposed.
Then test incrementally: C declarations and exact raw conversions; SHARC dispatch,
per-slot state and guards; coupled-emulator selection/locks/modulation; sound
save/reload/copy and missing-mod round trips; active tails and model/slot changes;
stock-track coexistence and downstream AMP/filter behavior. Keep reference
timbre comparisons and physical deadline qualification separate. Current tests
execute host C traces and the actual bridge with synthetic DSP frames; they do
not establish native persistence or allocator behavior.

## Inspected sources

All upstream links below are pinned to PR #200 head, not a moving branch:

- [SDK artifact producer](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/elekloader/sdk/sharc.py): `machine_layout`, `voice_artifact`, `_machine_artifact`.
- [Artifact validator](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/elekloader/sharc.py): `module_payload`.
- [Linker](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/elekloader/link.py): `check` registration/cardinality checks and `link` binding writes.
- [DN2 profile](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/elekloader/devices/digitone_mk2.py): voice/filter ranges and reservations.
- [Machine companion](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/mods/machines-dn2/machines.c): `dn2_ensure`, `build_pages`, `valid_pages`, missing-ID/type/MIDI paths.
- [Actual bridge assembly](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/mods/machines-dn2/voice-bridge.s): single-ID compare, settled START, forty words, `stock_slot` cleanup.
- [Native declarations](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/elekloader/sdk/include/mk2/machines.h), [voice ABI](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/elekloader/sdk/include/digitone-mk2/voice.h), [voice documentation](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/docs/MACHINES-DN2-VOICE.md), [missing-mod behavior](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/docs/MACHINES-DN2.md).
- [Upstream registration/link tests](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/tests/test_sharc_voice.py) and [C companion checks](https://github.com/irpina/elekloader/blob/2ab5f424c4721e4277d2112a5ae755d9938f50d6/tests/test_dn2_machines.c); local [current evidence boundaries](development.md) and [private contract candidates](render-contract.md). Sources were inspected; no new save/load or audio experiment was performed for this proposal.
