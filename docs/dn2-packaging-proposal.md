# DN2 packaging and persistence proposal

**Nonbinding review draft for [#23](https://github.com/simonjohansson/x0z/issues/23),
26 October 2026.** No ID, native layout, selector policy, schema or production
registration is adopted by this document. Approval is required before making
these persisted choices. The [private contract](render-contract.md) still applies.

## Recommendation and its limit

Use separate **808 and 909 firmware variants** for the first independent slices,
with candidate synth IDs **18 and 19** respectively. Start with 808. This uses
the exact pinned SDK without changing its registration ABI and avoids adding a
model switch to the first sound format. Keep each ID and its control meanings
stable once approved; never make the 909 variant reuse the 808 ID.

This is suitable for incremental development, but **one installed variant cannot
play both models**. A project may retain sounds with both IDs while the absent
model stays silent. If playing 808 and 909 together is required for the first
combined release, choose the combined selector before publishing the first
saved layout, or implement the upstream registration extension described below.
Separate variants do not solve that product requirement.

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
| One registered machine, model selector | One candidate ID, with each sound saving its selector and knobs; both models can run on different allocated voices in one image. | Supported by the current packaging. Requires both DSPs in one payload, a permanent selector slot, per-voice model state and reviewed switching semantics. One static page cannot change its labels with the model through the current page API. |
| Separate firmware variants | 808 saves ID 18; 909 saves ID 19. Only the installed model renders. | Smallest current-pin implementation and simplest first persistence contract. Switching firmware interrupts all audio. Keep both sound backups and the companion when exchanging variants. |
| Upstream multiple native SHARC registrations | Separate stable IDs 18/19 and independent pages; both models coexist in one image. | Clearest native user experience, but unavailable at this pin. Requires coordinated artifact, linker, bridge and test changes, rather than disabling one linker refusal. |

With `machines-dn2` retained, an absent synth ID 5..31 is preserved on load,
reported as MISSING by name accessors and mapped to silent MIDI DSP type.
Missing synth CC/NRPN lookups do not target MIDI-track values. Removing the
companion restores stock loading behavior, which may clamp the unknown ID to
FM TONE. These are inspected implementation paths, not a completed x0z
project/sound round-trip qualification. Do not overwrite the only saved copy
while checking missing registrations.

## Concrete layout candidates for review

Both variants propose clone/default type **0 (FM TONE)**, one SYN page and the
following positions. Clone 0 selects stock defaults, permissions and positional
MIDI mapping; it does not make the kick use FM DSP. Its AMP/filter defaults and
track assignment behavior still need emulator checks.

| SYN1 knob | Sound slot / callback parameter | ID 18, name `X0Z 808`, label `808` | ID 19, name `X0Z 909`, label `909` | Integer default |
| --- | --- | --- | --- | --- |
| A | 25 / 0 | `LEVEL` | `LEVEL` | 100 |
| B | 26 / 1 | `TONE` | `TUNE` | 64 |
| C | 27 / 2 | `DECAY` | `DECAY` | 64 |
| D | 28 / 3 | empty | `ATTK` | empty / 64 |
| E | 29 / 4 | `STR` candidate | `STR` candidate | 127 |
| F–H | 30–32 / 5–7 | empty | empty | no declaration |

These are initial positions, not calibrated Roland factory presets: 64 means
64/127 of the eventual physical control mapping. LEVEL 100 is 100/127 of the
declared linear level range, not a change to digital full scale. `STR` proposes
an explicit trigger-strength setting, latched at a trigger; approve it only
after deciding its relation to native velocity/accent and downstream AMP gain.
If deferred, leave E undeclared and use an explicitly documented fixed test
strength. Ordinary note pitch must not turn the 808 into a tuned bass engine.
Check ID conflicts against every selected mod before approval; no global
allocator establishes that 18/19 are universally free. MIDI numbers must be
verified from the chosen clone's actual slot mappings, not invented here.

For a **combined alternative**, review a distinct candidate **ID 20**, name
`X0Z KICKS`, label `KICKS`, clone 0. Keep A/C/E as above, B labelled `TNTUN`
(Tone for 808, Tune for 909), D `ATTK` ignored in 808, and add F `MODEL`, default
**0**. Static labels and both sets of saved values are unavoidable with this
single-page proposal. ID 20 avoids silently changing a previously approved
ID-18 sound's meaning; it is not reserved by this document.

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

There are currently no adopted x0z DN2 production IDs/layouts to migrate. Once
an 808 layout is approved, preserve ID 18, slots, ranges and meanings across
versions; do not reinterpret its empty slots or assume their saved contents
equal a newly added default. Defaults run on synth selection, which does not
prove migration of old sounds. A later combined ID 20 would require explicit
copy/import or a separately reviewed migration; it must not silently convert
ID 18. The upstream two-ID option can retain the original ID-18 layout directly.

Switching the native synth or loading another sound has separate host voice
allocation/tail behavior that is not established by the isolated bridge tests.
Do not promise tail preservation there. Firmware replacement always ends the
running performance; separate variants offer no live model-switch facility.

## Concrete upstream extension, separate from memory growth

A minimal multi-registration design would package **one shared voice payload**
containing both kernels and an explicit binding list for IDs 18/19. It would:

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

Before persisted implementation, review the variant/coexistence choice, candidate
IDs/names/clone, slots/defaults, strength policy and any selector/tail policy.
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
